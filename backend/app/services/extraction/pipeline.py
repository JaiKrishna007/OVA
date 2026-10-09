import uuid
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.source_record import SourceRecord
from app.models.provenance import ClinicalClaim
from app.models.summary import Summary
from app.models.enums import SourceProcessingStatus, ClaimValidationStatus, ExtractionMethod
from app.core.audit import record_audit
from app.services.extraction.schemas import CandidateClaim, ExtractionResult
from app.services.extraction.extractors import get_extractor, BaseExtractor
from app.services.extraction.normalizer import get_normalizer, Normalizer, NormalizedClaimResult
from app.services.validator.extraction.validator import ExtractionValidator
from app.services.validator.extraction.models import ValidationResult

logger = logging.getLogger(__name__)


def validate_candidate_claim(
    claim: CandidateClaim,
    document_text: str,
    normalized: NormalizedClaimResult,
    existing_claims: Optional[List[CandidateClaim]] = None,
) -> Tuple[ClaimValidationStatus, List[str]]:
    """
    Delegates to ExtractionValidator executing 7 deterministic checks.
    """
    res: ValidationResult = ExtractionValidator.validate(
        candidate=claim,
        source_text=document_text,
        existing_claims=existing_claims,
    )
    combined = list(set(res.reason_codes + normalized.reason_codes))
    status = res.status
    if "UNIT_AMBIGUOUS" in combined and status == ClaimValidationStatus.VERIFIED:
        status = ClaimValidationStatus.FLAGGED
    return status, combined


def process_record(
    record_id: str,
    db: Optional[Session] = None,
    extractor: Optional[BaseExtractor] = None,
    normalizer: Optional[Normalizer] = None,
) -> SourceProcessingStatus:
    """
    Orchestrates end-to-end extraction pipeline for a source record:
    1. Sets status to EXTRACTING.
    2. Runs extractor (Mock or Gemini) behind LLMClient with prompt injection guard.
    3. Normalizes candidate claims (synonyms, canonical units, dates).
    4. Validates claims against raw text.
    5. Writes ClinicalClaim rows for all candidates (including REJECTED/FLAGGED for transparency).
    6. Transitions status to VALIDATED (or FAILED on error).
    7. Marks patient summary stale.
    """
    owns_session = db is None
    session: Session = db if db is not None else SessionLocal()

    try:
        record = session.get(SourceRecord, record_id)
        if not record:
            logger.error(f"process_record: SourceRecord '{record_id}' not found.")
            return SourceProcessingStatus.FAILED

        # Do not process scanned image PDFs that require OCR
        if record.processing_status == SourceProcessingStatus.NEEDS_OCR:
            logger.info(f"process_record: SourceRecord '{record_id}' is marked NEEDS_OCR. Skipping extraction.")
            return SourceProcessingStatus.NEEDS_OCR

        # Transition to EXTRACTING
        record.processing_status = SourceProcessingStatus.EXTRACTING
        session.commit()

        content_text = record.content_text or ""
        if not content_text.strip():
            logger.info(f"process_record: SourceRecord '{record_id}' has no text content.")
            record.processing_status = SourceProcessingStatus.VALIDATED
            session.commit()
            return SourceProcessingStatus.VALIDATED

        # Instantiate extractor and normalizer
        active_extractor = extractor or get_extractor()
        active_normalizer = normalizer or get_normalizer()

        # Execute extraction with prompt injection defense
        extraction_result: ExtractionResult = active_extractor.extract(record_id, content_text)

        # Handle detected prompt injection
        if extraction_result.has_injection:
            logger.warning(f"process_record: Prompt injection detected in record '{record_id}'. Neutralized.")
            record_audit(
                db=session,
                user_id=record.uploaded_by or "system",
                action="prompt_injection_blocked",
                patient_id=record.patient_id,
                hospital_id=record.origin_org,
                event_type="security_alert",
                details={"record_id": record_id, "guard_events": extraction_result.guard_events},
            )
            record.processing_status = SourceProcessingStatus.VALIDATED
            session.commit()
            return SourceProcessingStatus.VALIDATED

        # Extract, normalize, validate, and persist claims
        persisted_claims: List[ClinicalClaim] = []
        method_enum = (
            ExtractionMethod.GEMINI
            if active_extractor.name.lower() == "gemini"
            else ExtractionMethod.MOCK
        )

        existing_candidates: List[CandidateClaim] = []

        for candidate in extraction_result.claims:
            # 1. Normalize
            norm_result = active_normalizer.normalize_claim(candidate)

            # 2. Comprehensive deterministic validation across 7 checks
            val_res = ExtractionValidator.validate(
                candidate=candidate,
                source_text=content_text,
                existing_claims=existing_candidates,
            )
            val_status = val_res.status
            combined_reasons = list(set(val_res.reason_codes + norm_result.reason_codes))
            if "UNIT_AMBIGUOUS" in combined_reasons and val_status == ClaimValidationStatus.VERIFIED:
                val_status = ClaimValidationStatus.FLAGGED

            checks_payload = [c.model_dump() for c in val_res.checks]

            # 3. Create immutable ClinicalClaim
            claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
            clm = ClinicalClaim(
                id=claim_id,
                patient_id=record.patient_id,
                hospital_id=record.origin_org or "ORG-Y",
                source_record_id=record.id,
                cycle_id=record.cycle_id,
                field=norm_result.canonical_field,
                value_text=str(norm_result.canonical_value),
                value_num=norm_result.numeric_value,
                unit=norm_result.canonical_unit,
                event_date=norm_result.canonical_date,
                span_start=candidate.span.start,
                span_end=candidate.span.end,
                evidence_text=candidate.evidence_text,
                extraction_method=method_enum,
                validation_status=val_status,
                validation_checks=checks_payload,
                reason_codes=combined_reasons if combined_reasons else None,
                uploaded_by=record.uploaded_by,
            )
            session.add(clm)
            persisted_claims.append(clm)
            existing_candidates.append(candidate)

        # Materialize verified claims into typed tables & invalidate summary
        from app.services.materializer.service import materialize_claims
        materialize_claims(session, patient_id=record.patient_id, record_id=record.id)

        record.processing_status = SourceProcessingStatus.VALIDATED
        session.commit()
        logger.info(
            f"process_record: Successfully processed record '{record_id}' ({len(persisted_claims)} claims persisted)."
        )
        return SourceProcessingStatus.VALIDATED

    except Exception as exc:
        logger.error(f"process_record failed for record '{record_id}': {exc}", exc_info=True)
        session.rollback()
        try:
            record = session.get(SourceRecord, record_id)
            if record:
                record.processing_status = SourceProcessingStatus.FAILED
                record.error_message = str(exc)
                session.commit()
        except Exception:
            pass
        return SourceProcessingStatus.FAILED

    finally:
        if owns_session:
            session.close()
