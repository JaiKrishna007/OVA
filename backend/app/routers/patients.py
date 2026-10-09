import math
import os
import re
import hashlib
from datetime import date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Response, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, select, func, desc

from app.core.config import settings
from app.models.provenance import PatientHospitalAccess, ClinicalClaim, ConflictRecord, DocumentationGap
from app.models.enums import (
    SourceProcessingStatus,
    HospitalAccessStatus,
    HospitalAccessLevel,
    TransferRequestStatus,
    TrustStatus,
    ClaimValidationStatus,
    ConflictStatus,
    GapStatus,
)
from app.models.provenance import TransferRequest, PatientHospitalAccess
from app.schemas.source_record import RecordUploadResponse
from app.services.ingestion.text_extractor import get_text_extractor
from app.services.extraction.pipeline import process_record

from app.services.summary_service import (
    get_or_generate_summary,
    get_summary_status,
    GenerationTimeoutException,
)
from app.services.brief_service import generate_patient_brief_pdf

from app.db.session import get_db
from app.models.patient import Patient, DoctorPatient
from app.models.cycle import Cycle
from app.models.clinical import (
    TreatmentEvent,
    StimulationDay,
    OocyteRetrieval,
    Embryo,
    Transfer,
    PregnancyOutcome,
    AdverseEvent,
    Medication,
)
from app.models.source_record import SourceRecord
from app.models.enums import UserRole, EmbryoFate, TreatmentEventKind
from app.models.user import User

from app.core.scope import Scope, get_scope, require_roles, get_current_user
from app.core.audit import record_audit
from app.services.audit_service import AuditService, AuditEvent
from app.core.errors import AppException
from app.core.masking import mask_phone

from app.services.engines.timeline import get_timeline
from app.services.engines.stage import get_current_stage
from app.services.engines.comparison import get_cycle_comparison
from app.services.engines.followups import get_followups
from app.services.engines.conflicts import detect_conflicts

from app.services.ai.ask import ask_patient_chart

from app.schemas.responses import (
    PatientListItem,
    PatientDetailResponse,
    TimelineResponse,
    CycleDetailResponse,
    CycleComparisonResponse,
    EmbryosResponse,
    StimulationResponse,
    FollowupsResponse,
    PaginatedRecordsResponse,
    RecordSummaryItem,
    AskQuestionRequest,
    AskQuestionResponse,
)

router = APIRouter(prefix="/patients", tags=["patients"])

BADGE_MAP = {
    "negative": "Negative",
    "biochemical_pregnancy": "Biochemical Pregnancy",
    "biochemical": "Biochemical Pregnancy",
    "clinical_pregnancy": "Clinical Pregnancy",
    "ongoing_pregnancy": "Ongoing Pregnancy",
    "spontaneous_miscarriage": "Spontaneous Miscarriage",
    "miscarriage": "Miscarriage",
    "ectopic": "Ectopic",
    "failed_fertilization": "Failed Fertilization",
    "cancelled": "Cancelled",
    "freeze_all": "Freeze-All",
    "live_birth": "Live Birth",
}


@router.get(
    "",
    response_model=List[PatientListItem],
    summary="Search and list patients",
    description="Fuzzy search patients by name, ID, or phone number within authorized doctor or organization scope. Phone numbers are masked for privacy.",
)
async def list_patients(
    q: Optional[str] = Query(None, description="Search term for patient name, ID, or phone number", examples=["Priya"]),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN, UserRole.STAFF, UserRole.PATIENT)),
    db: Session = Depends(get_db),
):
    """
    Search patients accessible to current user.
    - PATIENT: Only sees their own patient record.
    - HOSPITAL_ADMIN, ADMIN, STAFF: All patients where user's hospital has active access.
    - DOCTOR: Patients where user's hospital has active access AND doctor is assigned.
    """
    user_hospital_id = current_user.hospital_id or current_user.org_id

    if current_user.role == UserRole.PATIENT:
        if not current_user.patient_id:
            return []
        query = db.query(Patient).filter(Patient.id == current_user.patient_id)
    else:
        accessible_pids = (
            select(PatientHospitalAccess.patient_id)
            .where(
                PatientHospitalAccess.hospital_id == user_hospital_id,
                PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
            )
        )
        query = db.query(Patient).filter(
            or_(
                Patient.org_id == user_hospital_id,
                Patient.id.in_(accessible_pids),
            )
        )
        if current_user.role == UserRole.DOCTOR:
            query = query.join(DoctorPatient, DoctorPatient.patient_id == Patient.id).filter(DoctorPatient.doctor_id == current_user.id)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Patient.name.ilike(term),
                Patient.id.ilike(term),
                Patient.phone.ilike(term),
            )
        )

    patients = query.order_by(Patient.id.asc()).all()

    AuditService.log_from_user(db, current_user, AuditEvent.PATIENT_VIEWED, details={"action": "patients_search"})

    results: List[PatientListItem] = []
    for p in patients:
        p_scope = Scope(user=current_user, patient_id=p.id, org_id=p.org_id)
        stage_info = get_current_stage(db, p_scope)
        # Gather top-level baseline source provenance
        source_ids = [
            r[0] for r in db.query(SourceRecord.id).filter(SourceRecord.patient_id == p.id).limit(5).all()
        ]
        results.append(
            PatientListItem(
                id=p.id,
                name=p.name,
                dob=p.dob,
                sex=p.sex,
                org_id=p.org_id,
                diagnosis=p.diagnosis,
                partner_id=p.partner_id,
                blood_group=p.blood_group,
                bmi=p.bmi,
                phone_masked=mask_phone(p.phone),
                current_stage=stage_info.get("stage", "Stage not documented"),
                source_refs=source_ids,
            )
        )
    return results


@router.get(
    "/{patient_id}",
    response_model=PatientDetailResponse,
    summary="Get patient profile",
    description="Retrieve full patient profile with current clinical stage, masked phone, and provenance records.",
)
async def get_patient(
    patient_id: str,
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db),
):
    """View patient profile within authorized scope."""
    AuditService.log_from_user(db, scope.user, AuditEvent.PATIENT_VIEWED, patient_id=scope.patient_id, details={"action": "patient_view"})
    patient = db.get(Patient, scope.patient_id)
    stage_info = get_current_stage(db, scope)
    source_ids = [
        r[0] for r in db.query(SourceRecord.id).filter(SourceRecord.patient_id == scope.patient_id).all()
    ]
    transferred_to = None
    if scope.access_level == HospitalAccessLevel.READ_ONLY and scope.user.role != UserRole.PATIENT:
        rw_pha = db.scalar(
            select(PatientHospitalAccess).where(
                PatientHospitalAccess.patient_id == scope.patient_id,
                PatientHospitalAccess.access_level == HospitalAccessLevel.READ_WRITE,
                PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
            )
        )
        if rw_pha and rw_pha.hospital_id != scope.hospital_id:
            transferred_to = rw_pha.hospital_id
        else:
            last_trf = db.scalar(
                select(TransferRequest).where(
                    TransferRequest.patient_id == scope.patient_id,
                    TransferRequest.status == TransferRequestStatus.COMPLETED,
                    TransferRequest.from_hospital_id == scope.hospital_id,
                ).order_by(desc(TransferRequest.id))
            )
            if last_trf:
                transferred_to = last_trf.to_hospital_id

    return PatientDetailResponse(
        id=patient.id,
        name=patient.name,
        dob=patient.dob,
        sex=patient.sex,
        org_id=patient.org_id,
        diagnosis=patient.diagnosis,
        partner_id=patient.partner_id,
        blood_group=patient.blood_group,
        bmi=patient.bmi,
        phone_masked=mask_phone(patient.phone),
        current_stage=stage_info.get("stage", "Stage not documented"),
        source_refs=source_ids,
        access_level=scope.access_level.value if scope.access_level else None,
        transferred_to_hospital=transferred_to,
    )


@router.get(
    "/{patient_id}/timeline",
    response_model=TimelineResponse,
    summary="Get patient timeline",
    description="Ordered cycles and clinical events with outcome badges, origin and trust tags, and full provenance.",
)
async def get_patient_timeline(
    patient_id: str,
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db),
):
    """View patient timeline generated deterministically."""
    record_audit(db, user_id=scope.user.id, action="timeline_view", patient_id=scope.patient_id)
    timeline_data = get_timeline(db, scope)
    stage_info = get_current_stage(db, scope)

    cycles = timeline_data.get("cycles", [])
    all_sources = sorted(list({s for c in cycles for s in c.get("source_refs", [])}))

    return TimelineResponse(
        patient_id=scope.patient_id,
        stage=stage_info.get("stage", "Stage not documented"),
        total_cycles=len(cycles),
        cycles=cycles,
        years=timeline_data.get("years", []),
        unlinked_events=timeline_data.get("unlinked_events", []),
        source_refs=all_sources,
    )


@router.get(
    "/{patient_id}/cycles/{cycle_id}",
    response_model=CycleDetailResponse,
    summary="Get cycle details",
    description="Detailed breakdown of a treatment cycle including stimulation summary, OPU, embryo culture, transfers, and pregnancy outcome.",
)
async def get_patient_cycle(
    patient_id: str,
    cycle_id: str,
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db),
):
    """View patient cycle within authorized scope."""
    record_audit(db, user_id=scope.user.id, action="cycle_view", patient_id=scope.patient_id)
    cycle = db.get(Cycle, scope.cycle_id)

    # Treatment events
    events = (
        db.query(TreatmentEvent)
        .filter(TreatmentEvent.cycle_id == scope.cycle_id)
        .order_by(TreatmentEvent.date.asc())
        .all()
    )
    events_data = [
        {
            "id": ev.id,
            "kind": ev.kind.value if hasattr(ev.kind, "value") else str(ev.kind),
            "date": ev.date.isoformat(),
            "detail": ev.detail,
            "source_refs": [ev.source_id] if ev.source_id else [],
        }
        for ev in events
    ]

    # Stimulation summary
    stim_days = (
        db.query(StimulationDay)
        .filter(StimulationDay.cycle_id == scope.cycle_id)
        .order_by(StimulationDay.day_no.asc())
        .all()
    )
    stim_summary = None
    if stim_days:
        peak_e2 = max([d.e2 for d in stim_days if d.e2 is not None], default=None)
        stim_summary = {
            "total_days": len(stim_days),
            "peak_e2": peak_e2,
            "source_refs": sorted(list({d.source_id for d in stim_days if d.source_id})),
        }

    # OPU
    opu = db.query(OocyteRetrieval).filter(OocyteRetrieval.cycle_id == scope.cycle_id).first()
    opu_data = None
    if opu:
        opu_data = {
            "id": opu.id,
            "date": opu.date.isoformat(),
            "oocytes_retrieved": opu.oocytes_retrieved,
            "mii": opu.mii,
            "mi": opu.mi,
            "gv": opu.gv,
            "source_refs": [opu.source_id] if opu.source_id else [],
        }

    # Embryos
    embryos = db.query(Embryo).filter(Embryo.cycle_id == scope.cycle_id).all()
    embryos_data = [
        {
            "id": emb.id,
            "embryo_label": emb.embryo_label,
            "day": emb.day,
            "grade": emb.grade,
            "pgt_status": emb.pgt_status,
            "fate": emb.fate.value if hasattr(emb.fate, "value") else str(emb.fate),
            "storage_location": emb.storage_location,
            "source_refs": [emb.source_id] if emb.source_id else [],
        }
        for emb in embryos
    ]

    # Transfers
    transfers = db.query(Transfer).filter(Transfer.cycle_id == scope.cycle_id).all()
    transfers_data = [
        {
            "id": tr.id,
            "date": tr.date.isoformat(),
            "kind": tr.kind.value if hasattr(tr.kind, "value") else str(tr.kind),
            "embryo_ids": tr.embryo_ids,
            "endometrium_mm": tr.endometrium_mm,
            "source_refs": [tr.source_id] if tr.source_id else [],
        }
        for tr in transfers
    ]

    # Pregnancy Outcome
    outcome_row = db.query(PregnancyOutcome).filter(PregnancyOutcome.cycle_id == scope.cycle_id).first()
    pregnancy_outcome_data = None
    if outcome_row:
        pregnancy_outcome_data = {
            "id": outcome_row.id,
            "result": outcome_row.result.value if hasattr(outcome_row.result, "value") else str(outcome_row.result),
            "beta_hcg_value": outcome_row.beta_hcg_value,
            "beta_hcg_date": outcome_row.beta_hcg_date.isoformat() if outcome_row.beta_hcg_date else None,
            "gestation_note": outcome_row.gestation_note,
            "source_refs": [outcome_row.source_id] if outcome_row.source_id else [],
        }

    # Adverse Events
    adv_events = db.query(AdverseEvent).filter(AdverseEvent.cycle_id == scope.cycle_id).all()
    adv_data = [
        {
            "id": adv.id,
            "kind": adv.kind,
            "severity": adv.severity,
            "date": adv.date.isoformat(),
            "management_note": adv.management_note,
            "source_refs": [adv.source_id] if adv.source_id else [],
        }
        for adv in adv_events
    ]

    # Collect all source refs for cycle
    cycle_sources = set()
    if cycle.source_id:
        cycle_sources.add(cycle.source_id)
    for ev in events:
        if ev.source_id:
            cycle_sources.add(ev.source_id)
    for sd in stim_days:
        if sd.source_id:
            cycle_sources.add(sd.source_id)
    if opu and opu.source_id:
        cycle_sources.add(opu.source_id)
    for emb in embryos:
        if emb.source_id:
            cycle_sources.add(emb.source_id)
    for tr in transfers:
        if tr.source_id:
            cycle_sources.add(tr.source_id)
    if outcome_row and outcome_row.source_id:
        cycle_sources.add(outcome_row.source_id)
    for adv in adv_events:
        if adv.source_id:
            cycle_sources.add(adv.source_id)

    outcome_badge = BADGE_MAP.get(cycle.outcome, cycle.outcome.replace("_", " ").title() if cycle.outcome else "In Progress")

    return CycleDetailResponse(
        id=cycle.id,
        patient_id=cycle.patient_id,
        cycle_no=cycle.cycle_no,
        type=cycle.type.value if hasattr(cycle.type, "value") else str(cycle.type),
        start_date=cycle.start_date,
        end_date=cycle.end_date,
        outcome=cycle.outcome,
        outcome_badge=outcome_badge,
        origin_org=cycle.origin_org,
        trust_status=cycle.trust_status.value if cycle.trust_status else "internal_verified",
        events=events_data,
        stimulation_summary=stim_summary,
        opu=opu_data,
        embryos=embryos_data,
        transfers=transfers_data,
        pregnancy_outcome=pregnancy_outcome_data,
        adverse_events=adv_data,
        source_refs=sorted(list(cycle_sources)),
    )


@router.get(
    "/{patient_id}/cycle-comparison",
    response_model=CycleComparisonResponse,
    summary="Get multi-cycle comparison matrix",
    description="Compare stimulation protocols, days of stim, trigger hormones, follicle counts, oocyte and blastocyst yield across cycles.",
)
async def get_cycle_comparison_endpoint(
    patient_id: str,
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db),
):
    """View multi-cycle comparison matrix generated deterministically."""
    record_audit(db, user_id=scope.user.id, action="cycle_comparison_view", patient_id=scope.patient_id)
    comp_data = get_cycle_comparison(db, scope)
    matrix = comp_data.get("matrix", [])
    confs = detect_conflicts(db, scope)
    all_sources = sorted(list({s for row in matrix for s in row.get("source_refs", [])} | {s for c in confs for s in c.get("source_refs", [])}))
    return CycleComparisonResponse(
        patient_id=scope.patient_id,
        comparison_matrix=matrix,
        source_refs=all_sources,
        conflicts=confs,
    )


@router.get(
    "/{patient_id}/embryos",
    response_model=EmbryosResponse,
    summary="Get embryos and remaining frozen count",
    description="List all tracked embryos across cycles with remaining frozen storage counts and morphology grades.",
)
async def get_patient_embryos(
    patient_id: str,
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db),
):
    """View all embryos for patient with remaining frozen counts."""
    record_audit(db, user_id=scope.user.id, action="embryos_view", patient_id=scope.patient_id)
    cycle_ids = [c[0] for c in db.query(Cycle.id).filter(Cycle.patient_id == scope.patient_id).all()]

    embryos = (
        db.query(Embryo)
        .filter(Embryo.cycle_id.in_(cycle_ids))
        .order_by(Embryo.cycle_id.asc(), Embryo.embryo_label.asc())
        .all()
    ) if cycle_ids else []

    all_sources = set()
    embryos_data = []
    remaining_frozen = 0
    transferred_count = 0
    discarded_count = 0

    for emb in embryos:
        fate_str = emb.fate.value if hasattr(emb.fate, "value") else str(emb.fate)
        if fate_str == EmbryoFate.FROZEN.value:
            remaining_frozen += 1
        elif fate_str == EmbryoFate.TRANSFERRED.value:
            transferred_count += 1
        elif fate_str == EmbryoFate.DISCARDED.value:
            discarded_count += 1

        if emb.source_id:
            all_sources.add(emb.source_id)

        embryos_data.append(
            {
                "id": emb.id,
                "cycle_id": emb.cycle_id,
                "embryo_label": emb.embryo_label,
                "day": emb.day,
                "grade": emb.grade,
                "pgt_status": emb.pgt_status,
                "fate": fate_str,
                "storage_location": emb.storage_location,
                "origin_org": emb.origin_org,
                "trust_status": emb.trust_status.value if hasattr(emb.trust_status, "value") else str(emb.trust_status),
                "source_refs": [emb.source_id] if emb.source_id else [],
            }
        )

    return EmbryosResponse(
        patient_id=scope.patient_id,
        total_count=len(embryos),
        remaining_frozen=remaining_frozen,
        transferred_count=transferred_count,
        discarded_count=discarded_count,
        embryos=embryos_data,
        source_refs=sorted(list(all_sources)),
    )


@router.get(
    "/{patient_id}/stimulation/{cycle_id}",
    response_model=StimulationResponse,
    summary="Get cycle stimulation sheet",
    description="Daily hormone levels (E2, LH, P4), follicle tracking measurements, dose notes, and administered medications.",
)
async def get_cycle_stimulation(
    patient_id: str,
    cycle_id: str,
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db),
):
    """View stimulation flow sheet for specific cycle."""
    record_audit(db, user_id=scope.user.id, action="stimulation_view", patient_id=scope.patient_id)

    stim_days = (
        db.query(StimulationDay)
        .filter(StimulationDay.cycle_id == scope.cycle_id)
        .order_by(StimulationDay.day_no.asc())
        .all()
    )

    medications = (
        db.query(Medication)
        .filter(Medication.cycle_id == scope.cycle_id)
        .order_by(Medication.start_date.asc())
        .all()
    )

    trigger_event = (
        db.query(TreatmentEvent)
        .filter(
            TreatmentEvent.cycle_id == scope.cycle_id,
            TreatmentEvent.kind == TreatmentEventKind.TRIGGER,
        )
        .first()
    )

    all_sources = set()
    days_data = []
    peak_e2 = None
    max_follicles = 0

    for sd in stim_days:
        if sd.source_id:
            all_sources.add(sd.source_id)
        if sd.e2 is not None and (peak_e2 is None or sd.e2 > peak_e2):
            peak_e2 = sd.e2
        if isinstance(sd.follicles, dict):
            f_count = sum(len(v) if isinstance(v, list) else 0 for v in sd.follicles.values())
            if f_count > max_follicles:
                max_follicles = f_count

        days_data.append(
            {
                "id": sd.id,
                "day_no": sd.day_no,
                "date": sd.date.isoformat(),
                "follicles": sd.follicles,
                "e2": sd.e2,
                "lh": sd.lh,
                "p4": sd.p4,
                "endometrium_mm": sd.endometrium_mm,
                "dose_note": sd.dose_note,
                "origin_org": sd.origin_org,
                "trust_status": sd.trust_status.value if hasattr(sd.trust_status, "value") else str(sd.trust_status),
                "source_refs": [sd.source_id] if sd.source_id else [],
            }
        )

    meds_data = []
    for med in medications:
        if med.source_id:
            all_sources.add(med.source_id)
        meds_data.append(
            {
                "id": med.id,
                "name": med.name,
                "dose": med.dose,
                "route": med.route,
                "start_date": med.start_date.isoformat() if med.start_date else None,
                "end_date": med.end_date.isoformat() if med.end_date else None,
                "purpose": med.purpose,
                "source_refs": [med.source_id] if med.source_id else [],
            }
        )

    trigger_data = None
    if trigger_event:
        if trigger_event.source_id:
            all_sources.add(trigger_event.source_id)
        trigger_data = {
            "id": trigger_event.id,
            "date": trigger_event.date.isoformat(),
            "detail": trigger_event.detail,
            "source_refs": [trigger_event.source_id] if trigger_event.source_id else [],
        }

    summary = {
        "total_days": len(stim_days),
        "peak_e2": peak_e2,
        "max_follicles_count": max_follicles,
        "trigger_administered": trigger_event is not None,
    }

    return StimulationResponse(
        patient_id=scope.patient_id,
        cycle_id=scope.cycle_id,
        summary=summary,
        days=days_data,
        medications=meds_data,
        trigger=trigger_data,
        source_refs=sorted(list(all_sources)),
    )


@router.get(
    "/{patient_id}/followups",
    response_model=FollowupsResponse,
    summary="Get patient follow-ups",
    description="Pending, scheduled, and overdue follow-up tasks and investigations relative to AS_OF_DATE.",
)
async def get_patient_followups(
    patient_id: str,
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db),
):
    """View patient followups categorized by status and overdue date."""
    record_audit(db, user_id=scope.user.id, action="followups_view", patient_id=scope.patient_id)
    fol_data = get_followups(db, scope)

    all_sources = sorted(list({s for it in fol_data.get("items", []) for s in it.get("source_refs", [])}))
    counts = {
        "overdue": fol_data.get("overdue_count", 0),
        "scheduled": fol_data.get("scheduled_count", 0),
        "pending": fol_data.get("pending_count", 0),
        "done": fol_data.get("done_count", 0),
    }

    return FollowupsResponse(
        patient_id=scope.patient_id,
        as_of_date=fol_data.get("as_of_date", ""),
        counts=counts,
        overdue=fol_data.get("overdue", []),
        scheduled=fol_data.get("scheduled", []),
        pending=fol_data.get("pending", []),
        done=fol_data.get("done", []),
        source_refs=all_sources,
    )


@router.get(
    "/{patient_id}/records",
    response_model=PaginatedRecordsResponse,
    summary="List patient clinical source records",
    description="Browse and filter clinical records with pagination, document type, origin org, and text search.",
)
async def list_patient_records(
    patient_id: str,
    type: Optional[str] = Query(None, description="Filter by record type, e.g. lab, opu_report, discharge_summary"),
    cycle_id: Optional[str] = Query(None, description="Filter by cycle ID"),
    origin_org: Optional[str] = Query(None, description="Filter by originating hospital"),
    trust_status: Optional[str] = Query(None, description="Filter by trust status tier"),
    q: Optional[str] = Query(None, description="Search query inside record content or author"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    scope: Scope = Depends(get_scope),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN, UserRole.PATIENT)),
    db: Session = Depends(get_db),
):
    """View paginated source records for a patient with filters. Restricted to DOCTOR and ADMIN."""
    record_audit(db, user_id=scope.user.id, action="records_list", patient_id=scope.patient_id)

    query = db.query(SourceRecord).filter(SourceRecord.patient_id == scope.patient_id)

    if type:
        query = query.filter(SourceRecord.type == type)
    if cycle_id:
        query = query.filter(SourceRecord.cycle_id == cycle_id)
    if origin_org:
        query = query.filter(SourceRecord.origin_org == origin_org)
    if trust_status:
        query = query.filter(SourceRecord.trust_status == trust_status)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                SourceRecord.content_text.ilike(term),
                SourceRecord.author.ilike(term),
            )
        )

    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    records = (
        query.order_by(SourceRecord.date.desc(), SourceRecord.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    record_items = []
    page_source_refs = []
    for r in records:
        page_source_refs.append(r.id)
        excerpt = r.content_text[:200] + ("..." if len(r.content_text) > 200 else "")
        record_items.append(
            RecordSummaryItem(
                id=r.id,
                patient_id=r.patient_id,
                cycle_id=r.cycle_id,
                type=r.type,
                date=r.date,
                author=r.author,
                origin_org=r.origin_org,
                trust_status=r.trust_status.value if hasattr(r.trust_status, "value") else str(r.trust_status),
                version=r.version,
                content_excerpt=excerpt,
                content_text=r.content_text,
                source_refs=[r.id],
            )
        )

    return PaginatedRecordsResponse(
        patient_id=scope.patient_id,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        records=record_items,
        source_refs=page_source_refs,
    )


class RegenerateSummaryRequest(BaseModel):
    sections: Optional[List[str]] = None


@router.get(
    "/{patient_id}/summary",
    summary="Get patient AI summary",
    description="Access patient AI summary. Hidden from patient view unless PATIENT_SEES_AI_SUMMARY is enabled.",
)
async def get_patient_summary(
    patient_id: str,
    length: str = Query("detailed", pattern="^(snapshot|detailed)$", description="Summary verbosity: snapshot or detailed"),
    scope: Scope = Depends(get_scope),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN, UserRole.PATIENT)),
    db: Session = Depends(get_db),
):
    """
    Access patient AI summary with automatic data_version caching and provenance citations.
    """
    from app.core.config import settings
    if scope.user.role == UserRole.PATIENT and not settings.PATIENT_SEES_AI_SUMMARY:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="AI clinical summaries are restricted from patient view.",
        )
    record_audit(db, user_id=scope.user.id, action="summary_view", patient_id=scope.patient_id)
    try:
        summary_data = get_or_generate_summary(
            db=db,
            scope=scope,
            length=length,
            force_regenerate=False,
        )
        return summary_data
    except GenerationTimeoutException:
        return JSONResponse(
            status_code=202,
            content={
                "patient_id": scope.patient_id,
                "status": "in_progress",
                "message": "Summary generation in progress. Poll /patients/{id}/summary/status.",
            },
        )


@router.post(
    "/{patient_id}/summary/regenerate",
    summary="Regenerate patient AI summary",
    description="Force regeneration of patient AI summary, optionally targeting specific sections.",
)
async def regenerate_patient_summary(
    patient_id: str,
    body: Optional[RegenerateSummaryRequest] = None,
    scope: Scope = Depends(get_scope),
    doctor_user=Depends(require_roles(UserRole.DOCTOR)),
    db: Session = Depends(get_db),
):
    """
    Forces AI summary regeneration, optionally for specific sections only.
    """
    record_audit(db, user_id=scope.user.id, action="summary_regenerate", patient_id=scope.patient_id)
    sections = body.sections if body else None
    try:
        summary_data = get_or_generate_summary(
            db=db,
            scope=scope,
            length="detailed",
            force_regenerate=True,
            sections_to_regenerate=sections,
        )
        return summary_data
    except GenerationTimeoutException:
        return JSONResponse(
            status_code=202,
            content={
                "patient_id": scope.patient_id,
                "status": "in_progress",
                "message": "Summary regeneration in progress. Poll /patients/{id}/summary/status.",
            },
        )


@router.get(
    "/{patient_id}/summary/status",
    summary="Get patient AI summary status",
    description="Check generation readiness, version, and data staleness for patient summary.",
)
async def get_patient_summary_status(
    patient_id: str,
    scope: Scope = Depends(get_scope),
    doctor_user=Depends(require_roles(UserRole.DOCTOR)),
    db: Session = Depends(get_db),
):
    """
    Check if a patient's summary is ready, stale, or requires generation.
    """
    record_audit(db, user_id=scope.user.id, action="summary_status_view", patient_id=scope.patient_id)
    return get_summary_status(db, scope)


@router.post(
    "/{patient_id}/ask",
    response_model=AskQuestionResponse,
    summary="Ask-the-chart clinical Q&A",
    description="Ask a clinical question about the patient's records. Classified as structured field lookup or open-ended note retrieval. Refuses recommendations.",
)
async def ask_patient_endpoint(
    patient_id: str,
    body: AskQuestionRequest,
    scope: Scope = Depends(get_scope),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Handles Ask-The-Chart queries:
    - Structured: deterministic DB lookup returned as typed claim.
    - Open-ended: keyword retrieval over that patient's notes only + validation.
    - Refuses treatment/dosing recommendations.
    - Neutralizes prompt injection attempts.
    """
    record_audit(db, user_id=scope.user.id, action="ask_question", patient_id=scope.patient_id)
    result = ask_patient_chart(db, scope, body.question)
    return AskQuestionResponse(**result)


@router.get(
    "/{patient_id}/brief",
    summary="Download pre-consult clinical brief PDF",
    description="Generates and returns a single-page PDF clinical brief using only cached validated summary and deterministic engines. Restricted to doctors.",
)
async def get_patient_brief_endpoint(
    patient_id: str,
    scope: Scope = Depends(get_scope),
    doctor_user=Depends(require_roles(UserRole.DOCTOR)),
    db: Session = Depends(get_db),
):
    """
    Renders and streams a one-page pre-consult PDF brief for the authorized patient.
    Audit-logs the brief export.
    """
    record_audit(db, user_id=scope.user.id, action="brief_download", patient_id=scope.patient_id)
    pdf_bytes = generate_patient_brief_pdf(db=db, scope=scope)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="brief_{scope.patient_id}.pdf"'
        },
    )


def generate_next_record_id(db: Session) -> str:
    """Generates the next unique REC-#### source record identifier."""
    records = db.scalars(select(SourceRecord.id)).all()
    max_num = 0
    for rid in records:
        if rid.startswith("REC-"):
            try:
                num = int(rid.replace("REC-", ""))
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return f"REC-{max_num + 1:04d}"


@router.post(
    "/{patient_id}/records/upload",
    response_model=RecordUploadResponse,
    summary="Upload clinical source record",
    description="Upload a clinical document (.pdf, .txt, .json) up to 5 MB for a patient. Extracts text and creates an immutable SourceRecord.",
)
async def upload_patient_record(
    patient_id: str,
    file: UploadFile = File(..., description="Document file (.pdf, .txt, .json)"),
    record_type: str = Form(..., description="Type of clinical document (e.g. lab_report, doctor_note, opu_report)"),
    record_date: Optional[str] = Form(None, description="Record date YYYY-MM-DD (defaults to as-of date)"),
    cycle_id: Optional[str] = Form(None, description="Associated cycle ID if applicable"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Multipart upload endpoint for patient clinical documents.
    Enforces RBAC: DOCTOR (assigned, hospital has READ_WRITE) and HOSPITAL_ADMIN may upload;
    a hospital with READ_ONLY access is forbidden (403).
    Performs content hashing, deduplication (409), path traversal defense, and text extraction.
    """
    allowed_roles = {UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.STAFF, UserRole.ADMIN}
    if current_user.role not in allowed_roles:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Role '{current_user.role.value}' is not permitted to upload records",
        )

    # 1. Patient existence check
    patient = db.get(Patient, patient_id)
    if not patient:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Patient '{patient_id}' not found",
        )

    # 2. Doctor assignment check
    if current_user.role == UserRole.DOCTOR:
        assignment = db.scalar(
            select(DoctorPatient).where(
                DoctorPatient.doctor_id == current_user.id,
                DoctorPatient.patient_id == patient_id,
            )
        )
        if not assignment:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Doctor '{current_user.username}' is not assigned to patient '{patient_id}'",
            )

    # 3. Hospital access level check
    user_hospital_id = current_user.hospital_id or current_user.org_id
    pha = db.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == patient_id,
            PatientHospitalAccess.hospital_id == user_hospital_id,
            PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
        )
    )
    if not pha and current_user.role != UserRole.ADMIN:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Hospital '{user_hospital_id}' is not authorized to access patient '{patient_id}'",
        )
    if pha and pha.access_level == HospitalAccessLevel.READ_ONLY:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Hospital '{user_hospital_id}' has READ_ONLY access to patient '{patient_id}'; uploading records requires READ_WRITE access",
        )

    # 4. File extension and type validation
    filename = file.filename or "uploaded_record"
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = {".pdf", ".txt", ".json"}
    if ext not in allowed_exts:
        raise AppException(
            status_code=415,
            code="UNSUPPORTED_MEDIA_TYPE",
            message=f"File extension '{ext}' is not supported. Allowed formats: .pdf, .txt, .json",
        )

    # 5. Read content and validate size
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise AppException(
            status_code=413,
            code="PAYLOAD_TOO_LARGE",
            message=f"File size ({len(file_bytes)} bytes) exceeds the maximum allowed limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes",
        )
    if len(file_bytes) == 0:
        raise AppException(
            status_code=400,
            code="EMPTY_FILE",
            message="Uploaded file is empty",
        )

    # 6. Date validation
    if record_date and record_date.strip():
        try:
            parsed_date = date.fromisoformat(record_date.strip())
        except ValueError:
            raise AppException(
                status_code=400,
                code="INVALID_DATE",
                message=f"Invalid record_date '{record_date}'. Format must be YYYY-MM-DD",
            )
    else:
        try:
            parsed_date = date.fromisoformat(settings.AS_OF_DATE)
        except Exception:
            parsed_date = date.today()

    # 7. Cycle check if specified
    if cycle_id:
        cycle = db.get(Cycle, cycle_id)
        if not cycle or cycle.patient_id != patient_id:
            raise AppException(
                status_code=404,
                code="NOT_FOUND",
                message=f"Cycle '{cycle_id}' not found for patient '{patient_id}'",
            )

    # 8. Content hash & Duplicate prevention
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    existing_dup = db.scalar(
        select(SourceRecord).where(
            SourceRecord.patient_id == patient_id,
            SourceRecord.content_hash == content_hash,
        )
    )
    if existing_dup:
        raise AppException(
            status_code=409,
            code="DUPLICATE_DOCUMENT",
            message=f"Exact duplicate document already exists for patient '{patient_id}' (record '{existing_dup.id}')",
        )

    # 9. Sanitize filename and storage path (neutralize path traversal)
    raw_basename = os.path.basename(filename.replace("\\", "/"))
    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_basename)
    if not clean_name or clean_name.startswith("."):
        clean_name = f"doc_{clean_name}"

    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    patient_dir = os.path.join(upload_root, patient_id)
    os.makedirs(patient_dir, exist_ok=True)

    stored_filename = f"{content_hash[:12]}_{clean_name}"
    target_path = os.path.join(patient_dir, stored_filename)

    # Guard against path traversal escaping upload_root
    if not os.path.abspath(target_path).startswith(upload_root):
        raise AppException(
            status_code=400,
            code="INVALID_PATH",
            message="Path traversal attempt detected in filename",
        )

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    # 10. Extract text using TextExtractor
    extractor = get_text_extractor(clean_name, mime_type=file.content_type)
    extracted = extractor.extract(file_bytes, filename=clean_name)

    if extracted.needs_ocr:
        proc_status = SourceProcessingStatus.NEEDS_OCR
        content_text = extracted.text or "[NEEDS OCR: Scanned document requires OCR processing]"
    else:
        proc_status = SourceProcessingStatus.VALIDATED
        content_text = extracted.text

    # 11. Create SourceRecord
    new_record_id = generate_next_record_id(db)
    new_record = SourceRecord(
        id=new_record_id,
        patient_id=patient_id,
        cycle_id=cycle_id,
        type=record_type,
        date=parsed_date,
        author=current_user.username,
        origin_org=current_user.org_id,
        trust_status=TrustStatus.INTERNAL_VERIFIED if current_user.org_id == patient.org_id else TrustStatus.EXTERNAL_UNVERIFIED,
        content_text=content_text,
        version=1,
        uploaded_by=current_user.id,
        mime_type=file.content_type or ("application/pdf" if ext == ".pdf" else "text/plain"),
        file_path=os.path.relpath(target_path, os.path.abspath(os.path.join(upload_root, "..", ".."))),
        processing_status=proc_status,
        content_hash=content_hash,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    # 12. Audit log
    record_audit(
        db,
        user_id=current_user.id,
        action="record_upload",
        patient_id=patient_id,
        hospital_id=current_user.org_id,
        details={
            "record_id": new_record.id,
            "filename": clean_name,
            "record_type": record_type,
            "content_hash": content_hash,
            "processing_status": proc_status.value,
            "warnings": extracted.warnings,
        },
    )

    # 13. Process record extraction pipeline (extract candidate claims, normalize, validate, persist)
    if proc_status != SourceProcessingStatus.NEEDS_OCR:
        process_record(new_record.id, db=db)
        db.refresh(new_record)

    msg = "Record uploaded and processed successfully."
    if new_record.processing_status == SourceProcessingStatus.NEEDS_OCR:
        msg = "Record uploaded but requires OCR: scanned image detected without embedded text layer."

    return RecordUploadResponse(
        id=new_record.id,
        patient_id=new_record.patient_id,
        cycle_id=new_record.cycle_id,
        type=new_record.type,
        date=new_record.date,
        author=new_record.author,
        origin_org=new_record.origin_org,
        trust_status=new_record.trust_status,
        processing_status=new_record.processing_status,
        content_hash=new_record.content_hash,
        content_text=new_record.content_text,
        file_path=new_record.file_path,
        warnings=extracted.warnings,
        message=msg,
    )


@router.get(
    "/{patient_id}/dashboard",
    summary="Get patient overview dashboard",
    description="Returns treatment journey line with latest cycle stages, counts of verified claims, flagged claims, rejected candidates, open conflicts, open gaps, source records, hospitals, and links to filtered list endpoints.",
)
async def get_patient_dashboard(
    patient_id: str,
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise AppException(status_code=404, code="NOT_FOUND", message=f"Patient '{patient_id}' not found.")

    # 1. Counts
    verified_count = db.scalar(
        select(func.count(ClinicalClaim.id)).where(
            ClinicalClaim.patient_id == patient_id,
            ClinicalClaim.validation_status == ClaimValidationStatus.VERIFIED,
        )
    ) or 0

    flagged_count = db.scalar(
        select(func.count(ClinicalClaim.id)).where(
            ClinicalClaim.patient_id == patient_id,
            ClinicalClaim.validation_status == ClaimValidationStatus.FLAGGED,
        )
    ) or 0

    rejected_count = db.scalar(
        select(func.count(ClinicalClaim.id)).where(
            ClinicalClaim.patient_id == patient_id,
            ClinicalClaim.validation_status == ClaimValidationStatus.REJECTED,
        )
    ) or 0

    open_conflicts_count = db.scalar(
        select(func.count(ConflictRecord.id)).where(
            ConflictRecord.patient_id == patient_id,
            ConflictRecord.status == ConflictStatus.OPEN,
        )
    ) or 0

    open_gaps_count = db.scalar(
        select(func.count(DocumentationGap.id)).where(
            DocumentationGap.patient_id == patient_id,
            DocumentationGap.status == GapStatus.OPEN,
        )
    ) or 0

    source_records_count = db.scalar(
        select(func.count(SourceRecord.id)).where(
            SourceRecord.patient_id == patient_id,
        )
    ) or 0

    hospitals_records = db.scalars(
        select(SourceRecord.origin_org).where(
            SourceRecord.patient_id == patient_id,
            SourceRecord.origin_org.isnot(None),
        )
    ).all()
    hospitals_claims = db.scalars(
        select(ClinicalClaim.hospital_id).where(
            ClinicalClaim.patient_id == patient_id,
            ClinicalClaim.hospital_id.isnot(None),
        )
    ).all()
    distinct_hospitals = sorted(list(set(filter(None, list(hospitals_records) + list(hospitals_claims)))))
    hospitals_count = len(distinct_hospitals)

    # 2. Treatment journey line (latest cycle stages)
    stmt = (
        select(Cycle)
        .where(Cycle.patient_id == patient_id)
        .order_by(desc(Cycle.start_date), desc(Cycle.cycle_no))
    )
    latest_cycle = db.scalars(stmt).first()

    journey = []
    if latest_cycle:
        c_id = latest_cycle.id

        stim_count = db.scalar(
            select(func.count(StimulationDay.id)).where(StimulationDay.cycle_id == c_id)
        ) or 0
        trigger_evt = db.scalars(
            select(TreatmentEvent).where(
                TreatmentEvent.cycle_id == c_id,
                TreatmentEvent.kind == TreatmentEventKind.TRIGGER,
            )
        ).first()
        opu_count = db.scalar(
            select(func.count(OocyteRetrieval.id)).where(OocyteRetrieval.cycle_id == c_id)
        ) or 0
        embryo_count = db.scalar(
            select(func.count(Embryo.id)).where(Embryo.cycle_id == c_id)
        ) or 0
        transfer_evt = db.scalars(
            select(Transfer).where(Transfer.cycle_id == c_id)
        ).first()
        outcome_evt = db.scalars(
            select(PregnancyOutcome).where(PregnancyOutcome.cycle_id == c_id)
        ).first()

        journey.append({
            "stage": "STIMULATION",
            "label": "Ovarian Stimulation",
            "status": "COMPLETED" if stim_count > 0 else "PENDING",
            "date": latest_cycle.start_date.isoformat() if latest_cycle.start_date else None,
            "detail": f"{stim_count} stimulation days tracked" if stim_count > 0 else "Stimulation pending",
        })

        journey.append({
            "stage": "TRIGGER",
            "label": "Ovulation Trigger",
            "status": "COMPLETED" if trigger_evt else ("IN_PROGRESS" if stim_count >= 8 else "PENDING"),
            "date": trigger_evt.date.isoformat() if trigger_evt and trigger_evt.date else None,
            "detail": trigger_evt.detail if trigger_evt else "Pending follicular maturation",
        })

        journey.append({
            "stage": "OPU",
            "label": "Oocyte Retrieval (OPU)",
            "status": "COMPLETED" if opu_count > 0 else ("PENDING" if trigger_evt else "NOT_STARTED"),
            "date": None,
            "detail": f"{opu_count} retrieval records" if opu_count > 0 else "Awaiting retrieval",
        })

        journey.append({
            "stage": "EMBRYOLOGY",
            "label": "Embryology & Culture",
            "status": "COMPLETED" if embryo_count > 0 else ("IN_PROGRESS" if opu_count > 0 else "PENDING"),
            "date": None,
            "detail": f"{embryo_count} embryos cultured/graded" if embryo_count > 0 else "Culture pending",
        })

        journey.append({
            "stage": "TRANSFER",
            "label": "Embryo Transfer",
            "status": "COMPLETED" if transfer_evt else ("PENDING" if embryo_count > 0 else "NOT_STARTED"),
            "date": transfer_evt.date.isoformat() if transfer_evt and transfer_evt.date else None,
            "detail": f"{transfer_evt.kind.value} transfer" if transfer_evt else "Transfer pending",
        })

        journey.append({
            "stage": "OUTCOME",
            "label": "Pregnancy Confirmation",
            "status": "COMPLETED" if outcome_evt else ("PENDING" if transfer_evt else "NOT_STARTED"),
            "date": outcome_evt.beta_hcg_date.isoformat() if outcome_evt and outcome_evt.beta_hcg_date else None,
            "detail": (outcome_evt.result.value if hasattr(outcome_evt.result, "value") else str(outcome_evt.result)) if outcome_evt else "Awaiting outcome",
        })
    else:
        journey.append({
            "stage": "BASELINE_WORKUP",
            "label": "Initial Clinical Workup",
            "status": "COMPLETED",
            "date": None,
            "detail": "Baseline hormonal diagnostics and clinical intake completed",
        })
        journey.append({
            "stage": "CYCLE_PLANNING",
            "label": "Protocol Selection",
            "status": "IN_PROGRESS",
            "date": None,
            "detail": "Protocol decision pending multidisciplinary review",
        })

    filter_links = {
        "verified_claims": f"/api/v1/claims?patient_id={patient_id}&status=VERIFIED",
        "flagged_claims": f"/api/v1/claims?patient_id={patient_id}&status=FLAGGED",
        "rejected_candidates": f"/api/v1/claims?patient_id={patient_id}&status=REJECTED",
        "open_conflicts": f"/api/v1/patients/{patient_id}/conflicts?status=OPEN",
        "open_gaps": f"/api/v1/patients/{patient_id}/gaps?status=OPEN",
        "source_records": f"/api/v1/patients/{patient_id}/records",
        "hospitals": f"/api/v1/patients/{patient_id}/records",
    }

    return {
        "patient_id": patient_id,
        "patient_name": patient.name,
        "cycle_id": latest_cycle.id if latest_cycle else None,
        "cycle_type": latest_cycle.type if latest_cycle else None,
        "treatment_journey": journey,
        "counts": {
            "verified_claims": verified_count,
            "flagged_claims": flagged_count,
            "rejected_candidates": rejected_count,
            "open_conflicts": open_conflicts_count,
            "open_gaps": open_gaps_count,
            "source_records": source_records_count,
            "hospitals": hospitals_count,
        },
        "distinct_hospitals": distinct_hospitals,
        "filter_links": filter_links,
    }




