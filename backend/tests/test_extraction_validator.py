import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.enums import ClaimValidationStatus, UserRole, ExtractionMethod
from app.models.provenance import ClinicalClaim
from app.models.source_record import SourceRecord
from app.models.audit_log import AuditLog
from app.services.extraction.schemas import CandidateClaim, Span
from app.services.validator.extraction.models import CheckDetail, ValidationResult
from app.services.validator.extraction.validator import ExtractionValidator
from app.services.validator.extraction.check_known_field import check_known_field
from app.services.validator.extraction.check_value_in_source import check_value_in_source
from app.services.validator.extraction.check_unit_in_source import check_unit_in_source
from app.services.validator.extraction.check_date_in_source import check_date_in_source
from app.services.validator.extraction.check_span_grounding import check_span_grounding
from app.services.validator.extraction.check_context_attachment import check_context_attachment
from app.services.validator.extraction.check_duplicate import check_duplicate_claim


# ---------------------------------------------------------------------------
# Test Suite 1: Full ExtractionValidator Pipeline (Spec Exact & Adversarial)
# ---------------------------------------------------------------------------

def test_exact_verified_claim():
    """
    Source: "AMH was 2.4 ng/mL on 14/06/2026"
    AI AMH=2.4 ng/mL -> VERIFIED
    """
    source_text = "AMH was 2.4 ng/mL on 14/06/2026"
    candidate = CandidateClaim(
        field="amh",
        value=2.4,
        unit="ng/mL",
        date="2026-06-14",
        evidence_text="2.4",
        span=Span(start=8, end=11),
        confidence=0.95,
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.VERIFIED
    assert len(result.reason_codes) == 0
    assert all(c.passed for c in result.checks)


def test_adversarial_value_not_in_source():
    """
    Source: "AMH was 2.4 ng/mL on 14/06/2026"
    AI AMH=3.8 -> REJECTED VALUE_NOT_IN_SOURCE
    """
    source_text = "AMH was 2.4 ng/mL on 14/06/2026"
    candidate = CandidateClaim(
        field="amh",
        value=3.8,
        unit="ng/mL",
        date="2026-06-14",
        evidence_text="2.4",
        span=Span(start=8, end=11),
        confidence=0.95,
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.REJECTED
    assert "VALUE_NOT_IN_SOURCE" in result.reason_codes
    assert "VALUE_NOT_IN_SPAN" in result.reason_codes


def test_adversarial_wrong_unit():
    """
    Source: "AMH was 2.4 ng/mL on 14/06/2026"
    AI unit="pmol/L" (not in source) -> REJECTED UNIT_NOT_IN_SOURCE
    """
    source_text = "AMH was 2.4 ng/mL on 14/06/2026"
    candidate = CandidateClaim(
        field="amh",
        value=2.4,
        unit="pmol/L",
        date="2026-06-14",
        evidence_text="2.4",
        span=Span(start=8, end=11),
        confidence=0.95,
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.REJECTED
    assert "UNIT_NOT_IN_SOURCE" in result.reason_codes


def test_adversarial_wrong_date():
    """
    Source: "AMH was 2.4 ng/mL on 14/06/2026"
    AI date="2026-07-20" -> REJECTED DATE_NOT_IN_SOURCE
    """
    source_text = "AMH was 2.4 ng/mL on 14/06/2026"
    candidate = CandidateClaim(
        field="amh",
        value=2.4,
        unit="ng/mL",
        date="2026-07-20",
        evidence_text="2.4",
        span=Span(start=8, end=11),
        confidence=0.95,
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.REJECTED
    assert "DATE_NOT_IN_SOURCE" in result.reason_codes


def test_adversarial_span_mismatch():
    """
    Span points to different text in source (e.g. slice gives 'AMH' instead of evidence_text '2.4')
    -> REJECTED SPAN_MISMATCH
    """
    source_text = "AMH was 2.4 ng/mL on 14/06/2026"
    candidate = CandidateClaim(
        field="amh",
        value=2.4,
        unit="ng/mL",
        date="2026-06-14",
        evidence_text="2.4",
        span=Span(start=0, end=3),  # "AMH" != "2.4"
        confidence=0.95,
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.REJECTED
    assert "SPAN_MISMATCH" in result.reason_codes


def test_adversarial_span_out_of_range():
    """
    Span out of range -> REJECTED SPAN_OUT_OF_RANGE
    """
    source_text = "AMH was 2.4 ng/mL on 14/06/2026"
    candidate = CandidateClaim(
        field="amh",
        value=2.4,
        unit="ng/mL",
        date="2026-06-14",
        evidence_text="2.4",
        span=Span(start=100, end=110),
        confidence=0.95,
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.REJECTED
    assert "SPAN_OUT_OF_RANGE" in result.reason_codes


def test_adversarial_empty_evidence():
    """
    Empty evidence -> REJECTED EMPTY_EVIDENCE
    """
    source_text = "AMH was 2.4 ng/mL on 14/06/2026"
    candidate = CandidateClaim(
        field="amh",
        value=2.4,
        unit="ng/mL",
        date="2026-06-14",
        evidence_text="",
        span=Span(start=8, end=11),
        confidence=0.95,
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.REJECTED
    assert "EMPTY_EVIDENCE" in result.reason_codes


def test_adversarial_context_mismatch_value_belongs_to_competitor():
    """
    Value 2.4 belongs to FSH in context: "FSH was 2.4 mIU/mL while AMH was 5.1 ng/mL"
    Candidate claims field="amh" for value 2.4 -> REJECTED CONTEXT_MISMATCH
    """
    source_text = "FSH was 2.4 mIU/mL while AMH was 5.1 ng/mL on 14/06/2026"
    # FSH starts at 0, 2.4 is at 8:11
    candidate = CandidateClaim(
        field="amh",
        value=2.4,
        unit="mIU/mL",
        date="2026-06-14",
        evidence_text="2.4",
        span=Span(start=8, end=11),
        confidence=0.95,
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.REJECTED
    assert "CONTEXT_MISMATCH" in result.reason_codes


def test_adversarial_duplicate_claim():
    """
    Duplicate claim within the record -> REJECTED DUPLICATE_CLAIM
    """
    source_text = "AMH was 2.4 ng/mL on 14/06/2026"
    existing = CandidateClaim(
        field="amh",
        value=2.4,
        unit="ng/mL",
        date="2026-06-14",
        evidence_text="2.4",
        span=Span(start=8, end=11),
        confidence=0.95,
    )
    duplicate_candidate = CandidateClaim(
        field="amh",
        value=2.4,
        unit="ng/mL",
        date="2026-06-14",
        evidence_text="2.4",
        span=Span(start=8, end=11),
        confidence=0.95,
    )

    result = ExtractionValidator.validate(
        candidate=duplicate_candidate,
        source_text=source_text,
        existing_claims=[existing],
    )
    assert result.status == ClaimValidationStatus.REJECTED
    assert "DUPLICATE_CLAIM" in result.reason_codes


def test_adversarial_unknown_field():
    """
    Unknown canonical field -> REJECTED FIELD_UNKNOWN
    """
    source_text = "SpecialBiomarker was 2.4 on 14/06/2026"
    candidate = CandidateClaim(
        field="unknown_biomarker_xyz",
        value=2.4,
        date="2026-06-14",
        evidence_text="2.4",
        span=Span(start=20, end=23),
        confidence=0.95,
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.REJECTED
    assert "FIELD_UNKNOWN" in result.reason_codes


def test_soft_check_unit_ambiguous_yields_flagged():
    """
    Unit present in source text, but non-canonical / ambiguous in normalizer -> FLAGGED
    """
    # Suppose source has pmol/L, which occurs in source, but for AMH canonical is ng/mL
    # The normalizer returns ("pmol/L", ["UNIT_AMBIGUOUS"])
    source_text = "AMH was 17.1 pmol/L on 14/06/2026"
    candidate = CandidateClaim(
        field="amh",
        value=17.1,
        unit="pmol/L",
        date="2026-06-14",
        evidence_text="17.1",
        span=Span(start=8, end=12),
        confidence=0.95,
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.FLAGGED
    assert "UNIT_AMBIGUOUS" in result.reason_codes


def test_soft_check_low_confidence_date_yields_flagged():
    """
    Date in source, but AI confidence is low (< 0.6) -> FLAGGED
    """
    source_text = "AMH was 2.4 ng/mL on 14/06/2026"
    candidate = CandidateClaim(
        field="amh",
        value=2.4,
        unit="ng/mL",
        date="2026-06-14",
        evidence_text="2.4",
        span=Span(start=8, end=11),
        confidence=0.45,  # low confidence
    )

    result = ExtractionValidator.validate(candidate, source_text)
    assert result.status == ClaimValidationStatus.FLAGGED
    assert "DATE_LOW_CONFIDENCE" in result.reason_codes


# ---------------------------------------------------------------------------
# Test Suite 2: Individual Module Edge Cases & Branch Coverage
# ---------------------------------------------------------------------------

def test_check_known_field_branches():
    # 1. Direct canonical field
    assert check_known_field(CandidateClaim(field="amh", value=1, evidence_text="1", span=Span(start=0, end=1))).passed
    # 2. Case insensitive
    assert check_known_field(CandidateClaim(field="AMH", value=1, evidence_text="1", span=Span(start=0, end=1))).passed
    # 3. Synonym from terminology.yaml (e.g. 'anti-mullerian hormone')
    assert check_known_field(CandidateClaim(field="anti-mullerian hormone", value=1, evidence_text="1", span=Span(start=0, end=1))).passed
    # 4. Completely invalid
    res = check_known_field(CandidateClaim(field="fake_lab_123", value=1, evidence_text="1", span=Span(start=0, end=1)))
    assert not res.passed
    assert res.reason_code == "FIELD_UNKNOWN"


def test_check_value_in_source_branches():
    # Null value
    c_null = CandidateClaim.model_construct(field="amh", value=None, evidence_text="none", span=Span(start=0, end=4))
    res = check_value_in_source(c_null, "AMH was normal")
    assert not res.passed
    assert res.reason_code == "VALUE_NOT_IN_SOURCE"

    # Numeric integer / float matching
    c_int = CandidateClaim(field="oocytes_retrieved", value=8, evidence_text="8", span=Span(start=0, end=1))
    assert check_value_in_source(c_int, "Retrieved 8 oocytes").passed

    c_float_as_int = CandidateClaim(field="oocytes_retrieved", value=8.0, evidence_text="8", span=Span(start=0, end=1))
    assert check_value_in_source(c_float_as_int, "Retrieved 8 oocytes").passed

    # Value formatted with decimals
    c_float = CandidateClaim(field="amh", value=2.40, evidence_text="2.4", span=Span(start=0, end=3))
    assert check_value_in_source(c_float, "AMH 2.4 ng/mL").passed


def test_check_unit_in_source_branches():
    # Missing unit for field that does not require one (e.g., oocytes_retrieved)
    c_no_unit = CandidateClaim(field="oocytes_retrieved", value=10, unit=None, evidence_text="10", span=Span(start=0, end=2))
    assert check_unit_in_source(c_no_unit, "Retrieved 10 oocytes").passed

    # Missing unit for quantitative lab that requires one (soft failure UNIT_MISSING)
    c_missing_unit = CandidateClaim(field="amh", value=2.4, unit=None, evidence_text="2.4", span=Span(start=0, end=3))
    res = check_unit_in_source(c_missing_unit, "AMH 2.4")
    assert not res.passed
    assert res.reason_code == "UNIT_MISSING"
    assert res.is_hard_check is False

    # Standard matching unit
    c_valid = CandidateClaim(field="amh", value=2.4, unit="ng/mL", evidence_text="2.4", span=Span(start=0, end=3))
    assert check_unit_in_source(c_valid, "AMH 2.4 ng/mL").passed


def test_check_date_in_source_branches():
    # No date in claim
    c_no_date = CandidateClaim(field="amh", value=2.4, date=None, evidence_text="2.4", span=Span(start=0, end=3))
    assert check_date_in_source(c_no_date, "AMH 2.4").passed

    # Invalid date format in claim
    c_bad_date = CandidateClaim(field="amh", value=2.4, date="invalid-date", evidence_text="2.4", span=Span(start=0, end=3))
    res = check_date_in_source(c_bad_date, "AMH 2.4 on 2026-06-14")
    assert not res.passed
    assert res.reason_code == "DATE_INVALID_FORMAT"

    # Text contains no dates
    c_valid_date = CandidateClaim(field="amh", value=2.4, date="2026-06-14", evidence_text="2.4", span=Span(start=0, end=3))
    res = check_date_in_source(c_valid_date, "AMH 2.4 without any timestamp")
    assert not res.passed
    assert res.reason_code == "DATE_NOT_IN_SOURCE"

    # Various source date formats matching candidate date
    assert check_date_in_source(c_valid_date, "AMH 2.4 on 14 June 2026").passed
    assert check_date_in_source(c_valid_date, "AMH 2.4 on June 14, 2026").passed
    assert check_date_in_source(c_valid_date, "AMH 2.4 on 14.06.2026").passed
    assert check_date_in_source(c_valid_date, "AMH 2.4 on 14-06-2026").passed


def test_check_span_grounding_branches():
    # Negative start
    c_neg = CandidateClaim(field="amh", value=2.4, evidence_text="2.4", span=Span(start=-1, end=5))
    assert not check_span_grounding(c_neg, "AMH 2.4").passed

    # Start >= end
    c_inv = CandidateClaim(field="amh", value=2.4, evidence_text="2.4", span=Span(start=5, end=2))
    assert not check_span_grounding(c_inv, "AMH 2.4").passed

    # Value not contained in evidence text
    c_val_mismatch = CandidateClaim(field="amh", value=9.9, evidence_text="2.4 ng/mL", span=Span(start=4, end=13))
    res = check_span_grounding(c_val_mismatch, "AMH 2.4 ng/mL")
    assert not res.passed
    assert res.reason_code == "VALUE_NOT_IN_SPAN"

    # Float represented as integer in evidence
    c_float_int = CandidateClaim.model_construct(field="oocytes_retrieved", value=8.0, evidence_text="8 oocytes", span=Span(start=0, end=9))
    assert check_span_grounding(c_float_int, "8 oocytes").passed

    # Case-insensitive string in evidence
    c_str_case = CandidateClaim(field="procedure", value="OPU", evidence_text="opu", span=Span(start=0, end=3))
    assert check_span_grounding(c_str_case, "opu").passed


def test_check_context_attachment_branches():
    # Context window where field appears
    source = "Patient report: AMH serum test was 2.4 ng/mL"
    candidate = CandidateClaim(
        field="amh",
        value=2.4,
        evidence_text="2.4",
        span=Span(start=35, end=38),
    )
    assert check_context_attachment(candidate, source).passed

    # Context window with term_cfg from terminology.yaml (e.g. OPU)
    source_opu = "Patient underwent Ovum Pickup on 14/06/2026"
    candidate_opu = CandidateClaim(
        field="opu",
        value="OPU",
        evidence_text="Ovum Pickup",
        span=Span(start=18, end=29),
    )
    assert check_context_attachment(candidate_opu, source_opu).passed

    # Context window where field does not appear before value
    source_no_field = "Blood chemistry panel: value was 2.4 ng/mL"
    candidate_no_field = CandidateClaim(
        field="amh",
        value=2.4,
        evidence_text="2.4",
        span=Span(start=33, end=36),
    )
    res = check_context_attachment(candidate_no_field, source_no_field)
    assert not res.passed
    assert res.reason_code == "CONTEXT_MISMATCH"


def test_check_duplicate_branches():
    existing = [
        CandidateClaim(field="amh", value=2.4, date="2026-06-14", evidence_text="2.4", span=Span(start=8, end=11)),
    ]
    # No existing
    cand = CandidateClaim(field="amh", value=2.4, date="2026-06-14", evidence_text="2.4", span=Span(start=8, end=11))
    assert check_duplicate_claim(cand, None).passed

    # Different field at different span -> passes
    cand_diff = CandidateClaim(field="fsh", value=5.2, date="2026-06-14", evidence_text="5.2", span=Span(start=20, end=23))
    assert check_duplicate_claim(cand_diff, existing).passed

    # Duplicate by span
    cand_same_span = CandidateClaim(field="amh", value=9.9, evidence_text="9.9", span=Span(start=8, end=11))
    assert not check_duplicate_claim(cand_same_span, existing).passed

    # Duplicate by field, value, date (different span)
    cand_same_vals = CandidateClaim(field="amh", value=2.4, date="2026-06-14", evidence_text="2.4", span=Span(start=40, end=43))
    assert not check_duplicate_claim(cand_same_vals, existing).passed


# ---------------------------------------------------------------------------
# Test Suite 3: Claims Review Endpoints (POST /accept, POST /reject, GET)
# ---------------------------------------------------------------------------

def _get_auth_header(client: TestClient, username: str, password: str = "password123") -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_claims_accept_and_reject_flow(client: TestClient, seeded_session):
    sr = seeded_session.scalar(select(SourceRecord).where(SourceRecord.patient_id == "P-101"))
    assert sr is not None

    # 1. Create a FLAGGED claim in the seeded database
    flagged_claim = ClinicalClaim(
        id="CLM-TEST-FLAGGED-01",
        patient_id="P-101",
        hospital_id="ORG-Y",
        source_record_id=sr.id,
        field="amh",
        value_text="17.1",
        value_num=17.1,
        unit="pmol/L",
        event_date=date(2026, 6, 14),
        span_start=8,
        span_end=12,
        evidence_text="17.1",
        extraction_method=ExtractionMethod.GEMINI,
        validation_status=ClaimValidationStatus.FLAGGED,
        reason_codes=["UNIT_AMBIGUOUS"],
        validation_checks=[{"name": "check_unit_in_source", "passed": False, "reason_code": "UNIT_AMBIGUOUS"}],
    )
    seeded_session.add(flagged_claim)
    seeded_session.commit()

    # Log in as dr.rao (assigned to P-101 in ORG-Y)
    headers = _get_auth_header(client, "dr.rao")

    # 2. List claims filtering by status=FLAGGED
    list_resp = client.get("/api/v1/claims?status=FLAGGED&patient_id=P-101", headers=headers)
    assert list_resp.status_code == 200
    flagged_claims = list_resp.json()
    assert any(c["id"] == "CLM-TEST-FLAGGED-01" for c in flagged_claims)

    # 3. Doctor accepts the claim -> POST /claims/{id}/accept
    accept_resp = client.post(f"/api/v1/claims/{flagged_claim.id}/accept", headers=headers)
    assert accept_resp.status_code == 200
    acc_data = accept_resp.json()
    assert acc_data["status"] == "ok"
    assert acc_data["validation_status"] == "VERIFIED"

    # Verify audit log recorded
    audit = seeded_session.scalar(
        select(AuditLog).where(AuditLog.action == "claim_accept", AuditLog.patient_id == "P-101")
    )
    assert audit is not None
    assert audit.user_id == "USR-RAO"

    # 4. Create another FLAGGED claim to test reject
    bad_claim = ClinicalClaim(
        id="CLM-TEST-REJECT-02",
        patient_id="P-101",
        hospital_id="ORG-Y",
        source_record_id=sr.id,
        field="fsh",
        value_text="99.9",
        value_num=99.9,
        unit="mIU/mL",
        extraction_method=ExtractionMethod.GEMINI,
        validation_status=ClaimValidationStatus.FLAGGED,
        reason_codes=["CONTEXT_MISMATCH"],
    )
    seeded_session.add(bad_claim)
    seeded_session.commit()

    reject_resp = client.post(f"/api/v1/claims/{bad_claim.id}/reject", headers=headers)
    assert reject_resp.status_code == 200
    rej_data = reject_resp.json()
    assert rej_data["status"] == "ok"
    assert rej_data["validation_status"] == "REJECTED"

    # 5. Non-existent claim -> 404
    nf_resp = client.post("/api/v1/claims/CLM-NONEXISTENT/accept", headers=headers)
    assert nf_resp.status_code == 404


def test_claims_unauthorized_access(client: TestClient, seeded_session):
    sr = seeded_session.scalar(select(SourceRecord).where(SourceRecord.patient_id == "P-106"))
    assert sr is not None

    claim = ClinicalClaim(
        id="CLM-TEST-SEC-03",
        patient_id="P-106",  # P-106 is in ORG-Z, dr.rao is in ORG-Y
        hospital_id="ORG-Z",
        source_record_id=sr.id,
        field="amh",
        value_text="2.4",
        validation_status=ClaimValidationStatus.FLAGGED,
    )
    seeded_session.add(claim)
    seeded_session.commit()

    # dr.rao is NOT assigned to P-106 -> 403 FORBIDDEN
    headers = _get_auth_header(client, "dr.rao")
    resp = client.post(f"/api/v1/claims/{claim.id}/accept", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
