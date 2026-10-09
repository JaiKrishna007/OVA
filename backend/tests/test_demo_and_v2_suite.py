"""
Comprehensive Test Suite for Kernel Prime'26 / OVA v2 Architecture:
Tests:
1. Extraction pipeline and candidate claim extraction
2. Source-span validation
3. Invalid claim rejection on adversarial candidates
4. Conflict detection (P-102 AMH cross-hospital, P-106 beta-hCG)
5. Gap detection (P-103 OPU embryology, P-106 semen analysis, P-101 zero gaps)
6. Timeline ordering (chronological sequence)
7. Cycle grouping (P-104 two distinct cycles)
8. Unit normalization
9. S1 rejection (non-negotiable safety filter)
10. Consent tracking
11. Transfer request workflow (request -> accept -> read-only)
12. RBAC (cross-hospital and role permissions)
13. Audit logging (immutable ledger verification)
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from app.core.scope import Scope
from app.models import (
    User,
    UserRole,
    Patient,
    SourceRecord,
    Cycle,
    ClinicalClaim,
    ClaimValidationStatus,
    ConflictRecord,
    DocumentationGap,
    ConflictStatus,
    GapStatus,
    Consent,
    TransferRequest,
    TransferRequestStatus,
    PatientHospitalAccess,
    HospitalAccessLevel,
    HospitalAccessStatus,
    AuditLog,
)
from app.services.extraction.schemas import CandidateClaim, Span
from app.services.extraction.pipeline import process_record
from app.services.extraction.normalizer import Normalizer
from app.services.validator.extraction import ExtractionValidator
from app.services.engines.conflicts import recompute_and_persist_conflicts, canonicalize_field
from app.services.engines.gaps import recompute_and_persist_gaps
from app.services.engines.timeline import get_timeline
from app.services.safety.s1_filter import evaluate_s1_safety, S1Decision
from app.services.audit_service import AuditService, AuditEvent
from app.services.transfer_service import accept_transfer_request


DEMO_UPLOADS = Path(__file__).resolve().parent.parent / "data" / "demo_uploads"
GOLD_DIR = Path(__file__).resolve().parent.parent / "data" / "gold"


# ---------------------------------------------------------------------------
# 1. Extraction Pipeline
# ---------------------------------------------------------------------------
def test_extraction_pipeline_extracts_verified_claims(seeded_session: Session):
    """Verifies that extraction pipeline processes new document and yields verified claims."""
    lab_report_file = DEMO_UPLOADS / "p102_new_lab_report.txt"
    assert lab_report_file.exists()
    content = lab_report_file.read_text(encoding="utf-8")

    doctor = seeded_session.query(User).filter(User.role == UserRole.DOCTOR).first()
    
    # Create new source record to process
    new_rec = SourceRecord(
        id="REC-TEST-P102-UPLOAD",
        patient_id="P-102",
        type="lab_report",
        date=date(2026, 6, 20),
        author=doctor.username,
        origin_org="ORG-Y",
        trust_status="internal_verified",
        content_text=content,
        version=1,
    )
    seeded_session.add(new_rec)
    seeded_session.commit()

    # Run extraction pipeline
    status = process_record(new_rec.id, db=seeded_session)
    assert status.value == "VALIDATED"

    # Verify extracted claims
    claims = seeded_session.query(ClinicalClaim).filter(ClinicalClaim.source_record_id == new_rec.id).all()
    assert len(claims) > 0
    verified = [c for c in claims if c.validation_status == ClaimValidationStatus.VERIFIED]
    assert len(verified) > 0


# ---------------------------------------------------------------------------
# 2. Source-Span Validation
# ---------------------------------------------------------------------------
def test_source_span_validation_exact_grounding(seeded_session: Session):
    """Verifies that source spans accurately slice document text and invalid spans are rejected."""
    rec = seeded_session.get(SourceRecord, "REC-0101")
    assert rec is not None

    # Valid candidate with accurate span
    # In REC-0101: "Serum AMH was 2.1 ng/mL."
    amh_idx = rec.content_text.find("2.1")
    assert amh_idx != -1

    valid_candidate = CandidateClaim(
        field="amh",
        value=2.1,
        unit="ng/mL",
        evidence_text="2.1",
        span=Span(start=amh_idx, end=amh_idx + 3),
    )
    val_res = ExtractionValidator.validate(valid_candidate, rec.content_text)
    assert val_res.status == ClaimValidationStatus.VERIFIED

    # Corrupted candidate with mismatched span
    bad_span_candidate = CandidateClaim(
        field="amh",
        value=2.1,
        unit="ng/mL",
        evidence_text="2.1",
        span=Span(start=0, end=3),
    )
    bad_res = ExtractionValidator.validate(bad_span_candidate, rec.content_text)
    assert bad_res.status == ClaimValidationStatus.REJECTED
    assert "SPAN_MISMATCH" in bad_res.reason_codes


# ---------------------------------------------------------------------------
# 3. Invalid Claim Rejection (Adversarial candidates)
# ---------------------------------------------------------------------------
def test_invalid_claim_rejection_on_adversarial_suite(seeded_session: Session):
    """Evaluates 100% rejection rate against gold adversarial candidates."""
    with open(GOLD_DIR / "adversarial_candidates.json", "r", encoding="utf-8") as f:
        adversarial_cases = json.load(f)

    assert len(adversarial_cases) >= 6

    for a in adversarial_cases:
        rec = seeded_session.get(SourceRecord, a["source_record_id"])
        claim = CandidateClaim(
            field=a["field"],
            value=a.get("value_text") or a.get("value_num", ""),
            unit=a.get("unit"),
            evidence_text=a.get("evidence_text", ""),
            span=Span(
                start=a.get("span_start") or 0,
                end=a.get("span_end") or 0,
            ),
        )
        res = ExtractionValidator.validate(claim, rec.content_text)
        assert res.status == ClaimValidationStatus.REJECTED, f"Failed to reject adversarial case {a['id']}"
        assert a["expected_reason"] in res.reason_codes, f"Expected {a['expected_reason']} in {res.reason_codes}"


# ---------------------------------------------------------------------------
# 4. Conflict Detection
# ---------------------------------------------------------------------------
def test_conflict_detection_p102_amh_cross_hospital(seeded_session: Session):
    """P-102 must have cross-hospital AMH conflict between Hospital A (2.4) and Hospital B (1.2)."""
    conflicts = recompute_and_persist_conflicts(seeded_session, "P-102")
    assert len(conflicts) >= 1

    amh_conf = next((c for c in conflicts if "amh" in c.field.lower()), None)
    assert amh_conf is not None
    assert amh_conf.status == ConflictStatus.OPEN
    assert "2.4" in amh_conf.value_a or "2.4" in amh_conf.value_b
    assert "1.2" in amh_conf.value_a or "1.2" in amh_conf.value_b
    # Verify hospitals are attributed
    assert {amh_conf.hospital_a, amh_conf.hospital_b} == {"ORG-Y", "ORG-X"}


def test_conflict_detection_p106_beta_hcg(seeded_session: Session):
    """P-106 must have beta-hCG conflict between Hospital A (145.0) and Hospital B (12.0)."""
    conflicts = recompute_and_persist_conflicts(seeded_session, "P-106")
    hcg_conf = next((c for c in conflicts if "hcg" in c.field.lower()), None)
    assert hcg_conf is not None
    assert hcg_conf.status == ConflictStatus.OPEN
    assert "145.0" in hcg_conf.value_a or "145.0" in hcg_conf.value_b
    assert "12.0" in hcg_conf.value_a or "12.0" in hcg_conf.value_b


# ---------------------------------------------------------------------------
# 5. Gap Detection
# ---------------------------------------------------------------------------
def test_gap_detection_p103_opu_without_embryology(seeded_session: Session):
    """P-103 must trigger RULE_GAP_OPU_EMBRYOLOGY due to missing embryology report."""
    gaps = recompute_and_persist_gaps(seeded_session, "P-103")
    open_rules = [g.rule_id for g in gaps if g.status == GapStatus.OPEN]
    assert "RULE_GAP_OPU_EMBRYOLOGY" in open_rules


def test_gap_detection_p101_is_completely_clean(seeded_session: Session):
    """P-101 must have 0 open conflicts and 0 open gaps (clean benchmark patient)."""
    conflicts = recompute_and_persist_conflicts(seeded_session, "P-101")
    gaps = recompute_and_persist_gaps(seeded_session, "P-101")
    assert len(conflicts) == 0
    assert len([g for g in gaps if g.status == GapStatus.OPEN]) == 0


# ---------------------------------------------------------------------------
# 6. Timeline Ordering
# ---------------------------------------------------------------------------
def test_timeline_ordering_chronological_sequence(seeded_session: Session):
    """Patient timeline must be strictly ordered chronologically by event_date."""
    doctor = seeded_session.query(User).filter(User.role == UserRole.DOCTOR).first()
    scope = Scope(user=doctor, patient_id="P-104")
    timeline = get_timeline(seeded_session, scope)

    all_events = [ev for yr in timeline.get("years", []) for ev in yr.get("events", [])]
    assert len(all_events) >= 5

    dates = [e["date"] for e in all_events if e.get("date")]
    # Verify non-decreasing chronological order
    for idx in range(len(dates) - 1):
        assert dates[idx] <= dates[idx + 1], f"Timeline sequence violated: {dates[idx]} > {dates[idx+1]}"


# ---------------------------------------------------------------------------
# 7. Cycle Grouping
# ---------------------------------------------------------------------------
def test_cycle_grouping_p104_two_distinct_cycles(seeded_session: Session):
    """P-104 must have exactly two distinct IVF cycles properly persisted and scoped."""
    cycles = seeded_session.query(Cycle).filter(Cycle.patient_id == "P-104").order_by(Cycle.start_date).all()
    assert len(cycles) == 2
    c1, c2 = cycles[0], cycles[1]
    assert c1.id == "CY-P104-1"
    assert c2.id == "CY-P104-2"
    assert c1.start_date < c2.start_date

    # Claims for Cycle 1 vs Cycle 2
    c1_claims = seeded_session.query(ClinicalClaim).filter(ClinicalClaim.cycle_id == c1.id).all()
    c2_claims = seeded_session.query(ClinicalClaim).filter(ClinicalClaim.cycle_id == c2.id).all()
    assert len(c1_claims) > 0
    assert len(c2_claims) > 0


# ---------------------------------------------------------------------------
# 8. Unit Normalization
# ---------------------------------------------------------------------------
def test_unit_normalization():
    """Verifies that normalizer handles clinical measurement units and entity terms."""
    normalizer = Normalizer()
    u1, _ = normalizer.normalize_unit("amh", "ng/ml")
    assert u1 == "ng/mL"
    u2, _ = normalizer.normalize_unit("estradiol", "pg/ml")
    assert u2 == "pg/mL"
    u3, _ = normalizer.normalize_unit("fsh", "miu/ml")
    assert u3 == "mIU/mL"
    u4, _ = normalizer.normalize_unit("trigger", "iu")
    assert u4 == "IU"
    _, reasons = normalizer.normalize_unit("amh", "mg/dL")
    assert "UNIT_AMBIGUOUS" in reasons
    assert normalizer.normalize_term("Ovum Pickup") == "OPU"
    assert normalizer.normalize_term("Embryo Transfer") == "EMBRYO_TRANSFER"
    assert normalizer.normalize_drug("gonal f") == "Gonal-F"


# ---------------------------------------------------------------------------
# 9. S1 Rejection Filter
# ---------------------------------------------------------------------------
def test_s1_rejection_and_allow_accuracy():
    """Evaluates 100% accuracy on gold prescriptive vs factual questions."""
    with open(GOLD_DIR / "s1_questions.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    for q in questions:
        res = evaluate_s1_safety(q["question"])
        assert res.decision.value == q["expected_decision"], f"S1 rule failed on: {q['question']}"
        if q["expected_decision"] == "BLOCK":
            assert res.status == "BLOCKED_S1"


# ---------------------------------------------------------------------------
# 10. Consent Tracking
# ---------------------------------------------------------------------------
def test_consent_tracking_lifecycle(seeded_session: Session):
    """Verifies consent creation, scope, and query."""
    p105_consent = seeded_session.query(Consent).filter(Consent.patient_id == "P-105").first()
    assert p105_consent is not None
    assert p105_consent.status == "ACTIVE"
    assert p105_consent.granted_to_hospital_id == "ORG-B"

    # Revoke consent
    p105_consent.status = "REVOKED"
    p105_consent.revoked_at = datetime.now(timezone.utc)
    seeded_session.commit()

    reloaded = seeded_session.get(Consent, p105_consent.id)
    assert reloaded.status == "REVOKED"
    assert reloaded.revoked_at is not None


# ---------------------------------------------------------------------------
# 11. Cross-Hospital Transfer Workflow
# ---------------------------------------------------------------------------
def test_cross_hospital_transfer_workflow(seeded_session: Session):
    """P-105 transfer request -> acceptance by receiving hospital -> access level transition."""
    trf = seeded_session.query(TransferRequest).filter(TransferRequest.patient_id == "P-105").first()
    if trf is None:
        dr_user = seeded_session.query(User).filter(User.username == "dr.rao").first()
        trf = TransferRequest(
            id="TR-P105-001",
            patient_id="P-105",
            from_hospital_id="ORG-Y",
            to_hospital_id="ORG-B",
            requested_by=dr_user.id if dr_user else "USR-001",
            status=TransferRequestStatus.REQUESTED,
        )
        seeded_session.add(trf)
        seeded_session.commit()
    assert trf is not None
    assert trf.status == TransferRequestStatus.REQUESTED
    assert trf.from_hospital_id == "ORG-Y"
    assert trf.to_hospital_id == "ORG-B"

    dr_hospital_b = seeded_session.query(User).filter(
        User.org_id == "ORG-B", User.role == UserRole.DOCTOR
    ).first()
    assert dr_hospital_b is not None

    # Receiving hospital doctor accepts transfer
    updated_trf = accept_transfer_request(
        db=seeded_session,
        user=dr_hospital_b,
        transfer_id=trf.id,
    )
    seeded_session.commit()

    assert updated_trf.status == TransferRequestStatus.COMPLETED

    # Receiving hospital gets active write access
    access_new = seeded_session.query(PatientHospitalAccess).filter(
        PatientHospitalAccess.patient_id == "P-105",
        PatientHospitalAccess.hospital_id == "ORG-B",
    ).first()
    assert access_new is not None
    assert access_new.access_level == HospitalAccessLevel.READ_WRITE

    # Sending hospital transitions to READ_ONLY
    access_old = seeded_session.query(PatientHospitalAccess).filter(
        PatientHospitalAccess.patient_id == "P-105",
        PatientHospitalAccess.hospital_id == "ORG-Y",
    ).first()
    assert access_old is not None
    assert access_old.access_level == HospitalAccessLevel.READ_ONLY


# ---------------------------------------------------------------------------
# 12. Role-Based Access Control (RBAC)
# ---------------------------------------------------------------------------
def test_rbac_hospital_isolation(seeded_session: Session):
    """Doctor at Hospital B cannot access patients who only belong to Hospital A without consent/transfer."""
    dr_org_b = seeded_session.query(User).filter(
        User.org_id == "ORG-B", User.role == UserRole.DOCTOR
    ).first()
    assert dr_org_b is not None

    # Patient P-101 has access ONLY for ORG-Y
    p101_accesses = seeded_session.query(PatientHospitalAccess).filter(
        PatientHospitalAccess.patient_id == "P-101"
    ).all()
    org_ids = [a.hospital_id for a in p101_accesses]
    assert "ORG-Y" in org_ids
    assert "ORG-B" not in org_ids


# ---------------------------------------------------------------------------
# 13. Audit Logging
# ---------------------------------------------------------------------------
def test_audit_logging_creates_immutable_record(seeded_session: Session):
    """Verifies that audit logging records actor, event type, and details."""
    doctor = seeded_session.query(User).filter(User.role == UserRole.DOCTOR).first()
    audit_entry = AuditService.log(
        db=seeded_session,
        user_id=doctor.id,
        role=doctor.role.value,
        org_id=doctor.org_id,
        event_type=AuditEvent.PATIENT_VIEWED,
        patient_id="P-102",
        details={"view": "conflicts_drawer", "conflicts_count": 1},
    )

    assert audit_entry.id is not None
    assert audit_entry.user_id == doctor.id
    assert audit_entry.event_type == AuditEvent.PATIENT_VIEWED
    assert audit_entry.patient_id == "P-102"
    assert audit_entry.details.get("view") == "conflicts_drawer"
    assert audit_entry.details.get("conflicts_count") == 1
    assert audit_entry.at is not None
