import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError

from app.core.scope import Scope
from app.models.summary import Summary
from app.models.patient import Patient
from app.models.cycle import Cycle
from app.models.source_record import SourceRecord
from app.models.clinical import (
    Investigation,
    Medication,
    StimulationDay,
    OocyteRetrieval,
    Embryo,
    Transfer,
    PregnancyOutcome,
    AdverseEvent,
    Followup,
)
from app.services.ai.composer import compose_summary
from app.services.ai.degraded import execute_section_pipeline, DegradedSectionResult
from app.services.ai.context_pack import SECTIONS
from app.services.ai.llm.base import LLMClient
from app.services.ai.llm import get_llm_client
from app.services.engines.conflicts import detect_conflicts
from app.services.engines.missing import detect_missing_data

logger = logging.getLogger(__name__)


class GenerationTimeoutException(Exception):
    """Raised when parallel section generation exceeds request timeout."""
    pass


def compute_patient_data_version(db: Session, patient_id: str) -> str:
    """
    Computes a deterministic cryptographic hash of all relevant patient records
    and clinical rows to guarantee reliable cache validation and invalidation.
    """
    tokens: List[str] = []

    # 1. Patient baseline
    patient = db.get(Patient, patient_id)
    if patient:
        diag_str = json.dumps(patient.diagnosis, sort_keys=True) if patient.diagnosis else ""
        tokens.append(f"pat:{patient.id}:{patient.bmi}:{patient.blood_group}:{diag_str}")

    # 2. Source records
    records = db.scalars(
        select(SourceRecord).where(SourceRecord.patient_id == patient_id).order_by(SourceRecord.id)
    ).all()
    for r in records:
        tokens.append(f"rec:{r.id}:{r.version}:{r.date}")

    # 3. Cycles
    cycles = db.scalars(
        select(Cycle).where(Cycle.patient_id == patient_id).order_by(Cycle.id)
    ).all()
    for c in cycles:
        tokens.append(f"cy:{c.id}:{c.outcome}:{c.start_date}:{c.end_date}")

    # 4. Investigations
    invs = db.scalars(
        select(Investigation).where(Investigation.patient_id == patient_id).order_by(Investigation.id)
    ).all()
    for i in invs:
        tokens.append(f"inv:{i.id}:{i.value}:{i.status}:{i.date}")

    # 5. Medications
    meds = db.scalars(
        select(Medication).join(Cycle, Medication.cycle_id == Cycle.id)
        .where(Cycle.patient_id == patient_id).order_by(Medication.id)
    ).all()
    for m in meds:
        tokens.append(f"med:{m.id}:{m.dose}:{m.name}:{m.start_date}")

    # 6. Stimulation days
    stims = db.scalars(
        select(StimulationDay).join(Cycle, StimulationDay.cycle_id == Cycle.id)
        .where(Cycle.patient_id == patient_id).order_by(StimulationDay.id)
    ).all()
    for s in stims:
        tokens.append(f"stim:{s.id}:{s.day_no}:{s.e2}:{s.endometrium_mm}")

    # 7. Oocyte retrievals
    opus = db.scalars(
        select(OocyteRetrieval).join(Cycle, OocyteRetrieval.cycle_id == Cycle.id)
        .where(Cycle.patient_id == patient_id).order_by(OocyteRetrieval.id)
    ).all()
    for o in opus:
        tokens.append(f"opu:{o.id}:{o.oocytes_retrieved}:{o.mii}")

    # 8. Embryos
    embryos = db.scalars(
        select(Embryo).join(Cycle, Embryo.cycle_id == Cycle.id)
        .where(Cycle.patient_id == patient_id).order_by(Embryo.id)
    ).all()
    for e in embryos:
        tokens.append(f"emb:{e.id}:{e.grade}:{e.fate}")

    # 9. Transfers
    transfers = db.scalars(
        select(Transfer).join(Cycle, Transfer.cycle_id == Cycle.id)
        .where(Cycle.patient_id == patient_id).order_by(Transfer.id)
    ).all()
    for t in transfers:
        tokens.append(f"tr:{t.id}:{t.kind}:{t.date}")

    # 10. Pregnancy outcomes
    outcomes = db.scalars(
        select(PregnancyOutcome).join(Cycle, PregnancyOutcome.cycle_id == Cycle.id)
        .where(Cycle.patient_id == patient_id).order_by(PregnancyOutcome.id)
    ).all()
    for p in outcomes:
        tokens.append(f"po:{p.id}:{p.result}:{p.beta_hcg_value}:{p.beta_hcg_date}")

    # 11. Adverse events
    adverse = db.scalars(
        select(AdverseEvent).join(Cycle, AdverseEvent.cycle_id == Cycle.id)
        .where(Cycle.patient_id == patient_id).order_by(AdverseEvent.id)
    ).all()
    for a in adverse:
        tokens.append(f"adv:{a.id}:{a.kind}:{a.severity}")

    # 12. Followups
    followups = db.scalars(
        select(Followup).where(Followup.patient_id == patient_id).order_by(Followup.id)
    ).all()
    for f in followups:
        tokens.append(f"fol:{f.id}:{f.status}:{f.due_date}")

    digest = hashlib.sha256("|".join(tokens).encode("utf-8")).hexdigest()
    return digest


def generate_sections_in_parallel(
    db: Session,
    scope: Scope,
    sections_to_run: List[str],
    llm_client: Optional[LLMClient] = None,
    timeout: float = 30.0,
) -> Dict[str, DegradedSectionResult]:
    """
    Generates summary sections concurrently using a worker pool, respecting timeout.
    """
    bind = db.get_bind()
    WorkerSession = sessionmaker(bind=bind, autocommit=False, autoflush=False)
    all_conflicts = detect_conflicts(db, scope)
    all_missing = detect_missing_data(db, scope)

    results: Dict[str, DegradedSectionResult] = {}

    def _worker(sec_name: str):
        with WorkerSession() as thread_db:
            res = execute_section_pipeline(
                db=thread_db,
                scope=scope,
                section=sec_name,
                llm_client=llm_client,
                all_conflicts=all_conflicts,
                all_missing=all_missing,
            )
            return sec_name, res

    try:
        bind = db.get_bind()
        is_sqlite = bind.dialect.name == "sqlite"
    except Exception:
        is_sqlite = False

    if is_sqlite:
        for sec in sections_to_run:
            res = execute_section_pipeline(
                db=db,
                scope=scope,
                section=sec,
                llm_client=llm_client,
                all_conflicts=all_conflicts,
                all_missing=all_missing,
            )
            results[sec] = res
        return results

    max_workers = min(len(sections_to_run), 4) if sections_to_run else 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_worker, sec): sec for sec in sections_to_run}
        try:
            for fut in as_completed(future_map, timeout=timeout):
                sec, res = fut.result()
                results[sec] = res
        except TimeoutError:
            logger.error(f"Section generation timed out after {timeout} seconds.")
            raise GenerationTimeoutException(f"Generation exceeded {timeout}s timeout limit")

    return results


_LOCKS_MUTEX = threading.Lock()
_PATIENT_LOCKS: Dict[str, threading.Lock] = {}


def _get_patient_lock(patient_id: str) -> threading.Lock:
    with _LOCKS_MUTEX:
        if patient_id not in _PATIENT_LOCKS:
            _PATIENT_LOCKS[patient_id] = threading.Lock()
        return _PATIENT_LOCKS[patient_id]


def get_or_generate_summary(
    db: Session,
    scope: Scope,
    force_regenerate: bool = False,
    sections_to_regenerate: Optional[List[str]] = None,
    length: str = "detailed",
    llm_client: Optional[LLMClient] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Retrieves cached summary or executes full/partial parallel generation with versioning.
    Guarded with per-patient concurrency locks and IntegrityError rollback recovery (SEC-08).
    """
    patient_id = scope.patient_id
    if not patient_id:
        raise ValueError("Scope missing patient_id")

    lock = _get_patient_lock(patient_id)
    with lock:
        current_data_version = compute_patient_data_version(db, patient_id)

        # 1. Check latest summary in database
        latest_summary = db.scalars(
            select(Summary)
            .where(Summary.patient_id == patient_id)
            .order_by(desc(Summary.version))
        ).first()

        # 2. Serve from cache if data_version matches and no regenerate requested
        if (
            latest_summary is not None
            and not force_regenerate
            and not sections_to_regenerate
            and latest_summary.data_version == current_data_version
        ):
            cached_content = dict(latest_summary.content_json)
            cached_content["id"] = latest_summary.id
            cached_content["summary_id"] = latest_summary.id
            cached_content["version"] = latest_summary.version
            cached_content["data_version"] = latest_summary.data_version
            cached_content["cache_hit"] = True
            cached_content["generated_at"] = (
                latest_summary.generated_at.isoformat()
                if latest_summary.generated_at
                else None
            )
            cached_content["is_stale"] = False
            cached_content["metadata"]["from_cache"] = True
            cached_content["metadata"]["version"] = latest_summary.version
            cached_content["metadata"]["data_version"] = current_data_version

            if length == "snapshot":
                return {
                    "id": latest_summary.id,
                    "summary_id": latest_summary.id,
                    "patient_id": patient_id,
                    "snapshot": cached_content.get("snapshot", []),
                    "disclaimer": cached_content.get("disclaimer"),
                    "is_stale": False,
                    "metadata": cached_content.get("metadata", {}),
                }
            return cached_content

        # 3. Parallel section generation
        target_sections = sections_to_regenerate if sections_to_regenerate else SECTIONS

        # Parallel run with timeout
        generate_sections_in_parallel(
            db=db,
            scope=scope,
            sections_to_run=target_sections,
            llm_client=llm_client,
            timeout=timeout,
        )

        # 4. Compose full summary
        composed = compose_summary(
            db=db,
            scope=scope,
            llm_client=llm_client,
        )

        # Re-check latest version under lock in case another transaction committed
        latest_after_gen = db.scalars(
            select(Summary)
            .where(Summary.patient_id == patient_id)
            .order_by(desc(Summary.version))
        ).first()
        next_version = (latest_after_gen.version + 1) if latest_after_gen else 1
        composed["metadata"]["version"] = next_version
        composed["metadata"]["data_version"] = current_data_version
        composed["metadata"]["from_cache"] = False
        composed["is_stale"] = False

        # 5. Persist to database with IntegrityError protection
        summary_record = Summary(
            id=f"SUM-{patient_id}-{next_version}",
            patient_id=patient_id,
            version=next_version,
            data_version=current_data_version,
            generated_at=datetime.now(timezone.utc),
            content_json=composed,
            validator_report_json=composed.get("validator_report", {}),
        )
        try:
            db.add(summary_record)
            db.commit()
            db.refresh(summary_record)
        except IntegrityError:
            db.rollback()
            # Concurrently inserted summary exists: reload latest committed version
            latest_existing = db.scalars(
                select(Summary)
                .where(Summary.patient_id == patient_id)
                .order_by(desc(Summary.version))
            ).first()
            if latest_existing:
                res = dict(latest_existing.content_json)
                res["cache_hit"] = True
                return res

        composed["id"] = summary_record.id
        composed["summary_id"] = summary_record.id
        composed["version"] = summary_record.version
        composed["data_version"] = summary_record.data_version
        composed["cache_hit"] = False
        composed["generated_at"] = summary_record.generated_at.isoformat()

        if length == "snapshot":
            return {
                "id": summary_record.id,
                "summary_id": summary_record.id,
                "patient_id": patient_id,
                "snapshot": composed.get("snapshot", []),
                "disclaimer": composed.get("disclaimer"),
                "is_stale": False,
                "metadata": composed.get("metadata", {}),
            }

        return composed


def get_summary_status(db: Session, scope: Scope) -> Dict[str, Any]:
    """
    Returns current summary generation status, staleness, and metadata.
    """
    patient_id = scope.patient_id
    if not patient_id:
        raise ValueError("Scope missing patient_id")

    current_data_version = compute_patient_data_version(db, patient_id)

    latest_summary = db.scalars(
        select(Summary)
        .where(Summary.patient_id == patient_id)
        .order_by(desc(Summary.version))
    ).first()

    if not latest_summary:
        return {
            "patient_id": patient_id,
            "status": "not_generated",
            "is_stale": False,
            "data_version": current_data_version,
            "version": None,
            "last_generated_at": None,
        }

    is_stale = latest_summary.data_version != current_data_version
    return {
        "patient_id": patient_id,
        "status": "ready",
        "is_stale": is_stale,
        "data_version": current_data_version,
        "version": latest_summary.version,
        "last_generated_at": latest_summary.generated_at.isoformat() if latest_summary.generated_at else None,
    }
