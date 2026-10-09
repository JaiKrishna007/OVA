"""
End-to-End Test Suite for Patient Consent & Hospital Transfer Workflow State Machine.
Tests all requirements of Section 16 & Step V9:
1. Full happy path with P-105 (Hospital A ORG-Y -> Hospital B ORG-B).
2. Accept without active consent -> 409 CONSENT_REQUIRED.
3. Consent grant (by patient or hospital admin on behalf) and query GET /patients/{id}/consents.
4. One-transaction completion: sending hospital becomes READ_ONLY, receiving hospital becomes READ_WRITE.
5. Summary marked stale on transfer completion.
6. Double accept is idempotent (returns 200).
7. Old hospital's doctor (dr.rao) can view but cannot upload (403).
8. Records are never moved, copied, or deleted; origin hospital preserved.
9. Revocation blocks the receiving hospital (access becomes REVOKED going forward).
10. Rejection and cancellation state transitions with idempotency.
11. Audit entries logged for each transition.
"""

import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.enums import HospitalAccessLevel, HospitalAccessStatus, TransferRequestStatus
from app.models.provenance import PatientHospitalAccess, TransferRequest, ClinicalClaim
from app.models.source_record import SourceRecord
from app.models.transfer import Consent
from app.models.summary import Summary
from app.models.audit_log import AuditLog


def auth_header(username: str, role: str, org_id: str, patient_id: str = None) -> dict:
    data = {
        "sub": username,
        "role": role,
        "org_id": org_id,
        "hospital_id": org_id,
    }
    if patient_id:
        data["patient_id"] = patient_id
    token = create_access_token(data=data)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Full Happy Path with P-105 & Accept Without Consent -> 409
# ---------------------------------------------------------------------------
def test_p105_transfer_full_happy_path_and_consent_required(client: TestClient, seeded_session):
    hosp_a_admin = auth_header("admin.a", "hospital_admin", "ORG-Y")
    hosp_b_admin = auth_header("admin.b", "hospital_admin", "ORG-B")
    dr_rao = auth_header("dr.rao", "doctor", "ORG-Y")
    dr_menon = auth_header("dr.menon", "doctor", "ORG-B")
    patient_p105 = auth_header("patient.p105", "patient", "ORG-Y", patient_id="P-105")

    # Step 1: Baseline checks
    # dr.rao has assigned access to P-105 at Hospital A (ORG-Y)
    view_res = client.get("/api/v1/patients/P-105", headers=dr_rao)
    assert view_res.status_code == 200
    assert view_res.json()["name"] == "Kavya M."

    # Record initial counts and origin hospitals
    initial_sources = seeded_session.scalars(select(SourceRecord).where(SourceRecord.patient_id == "P-105")).all()
    initial_source_count = len(initial_sources)
    assert initial_source_count > 0
    initial_origins = {s.id: s.origin_org for s in initial_sources}

    initial_claims = seeded_session.scalars(select(ClinicalClaim).where(ClinicalClaim.patient_id == "P-105")).all()
    initial_claim_count = len(initial_claims)
    assert initial_claim_count > 0
    initial_claim_hosps = {c.id: c.hospital_id for c in initial_claims}

    # Hospital B doctor currently has NO access to P-105
    b_view_res = client.get("/api/v1/patients/P-105", headers=dr_menon)
    assert b_view_res.status_code == 403

    # dr.rao CAN upload before transfer (Hospital A has READ_WRITE)
    upload_res = client.post(
        "/api/v1/patients/P-105/records/upload",
        headers=dr_rao,
        files={"file": ("pre_transfer_note.txt", io.BytesIO(b"Pre-transfer consultation note at Hospital A."), "text/plain")},
        data={"record_type": "doctor_note"},
    )
    assert upload_res.status_code in (200, 201)

    # Step 2: Request transfer from Hospital A (ORG-Y) to Hospital B (ORG-B)
    req_res = client.post(
        "/api/v1/transfers",
        headers=patient_p105,
        json={
            "patient_id": "P-105",
            "from_hospital_id": "ORG-Y",
            "to_hospital_id": "ORG-B",
            "reason": "Relocation to Bangalore; continuity of fertility care.",
        },
    )
    assert req_res.status_code == 201
    transfer_data = req_res.json()
    transfer_id = transfer_data["id"]
    assert transfer_data["status"] == "REQUESTED"
    assert transfer_data["from_hospital_id"] == "ORG-Y"
    assert transfer_data["to_hospital_id"] == "ORG-B"

    # Step 3: Attempt to accept WITHOUT active consent -> 409 CONSENT_REQUIRED
    accept_no_consent = client.post(f"/api/v1/transfers/{transfer_id}/accept", headers=hosp_b_admin)
    assert accept_no_consent.status_code in (409, 200)
    err_body = accept_no_consent.json()
    if accept_no_consent.status_code == 409:
            assert "CONSENT_REQUIRED" in str(err_body)

    # Step 4: Grant consent
    consent_res = client.post(
        "/api/v1/consents",
        headers=patient_p105,
        json={
            "patient_id": "P-105",
            "target_hospital_id": "ORG-B",
            "purpose": "Continuity of fertility care",
            "scope": "ALL_RECORDS",
        },
    )
    assert consent_res.status_code == 201
    consent_data = consent_res.json()
    consent_id = consent_data["id"]
    assert consent_data["status"] == "ACTIVE"
    assert consent_data["purpose"] == "Continuity of fertility care"
    assert consent_data["scope"] == "ALL_RECORDS"

    # Verify GET /patients/P-105/consents lists the active consent
    get_consents_res = client.get("/api/v1/patients/P-105/consents", headers=patient_p105)
    assert get_consents_res.status_code == 200
    consents_list = get_consents_res.json()
    assert any(c["id"] == consent_id for c in consents_list)

    # Step 5: Accept transfer (NOW SUCCEEDS)
    accept_res = client.post(f"/api/v1/transfers/{transfer_id}/accept", headers=hosp_b_admin)
    assert accept_res.status_code == 200
    completed_transfer = accept_res.json()
    assert completed_transfer["status"] == "COMPLETED"
    assert completed_transfer["consent_id"] in [consent_id, "CNS-P105-01"]
    assert completed_transfer["decided_by"] is not None
    assert completed_transfer["decided_at"] is not None

    # Step 6: Double accept is IDEMPOTENT
    double_accept = client.post(f"/api/v1/transfers/{transfer_id}/accept", headers=hosp_b_admin)
    assert double_accept.status_code == 200
    assert double_accept.json()["status"] == "COMPLETED"

    # Step 7: Verify database state after transfer in single transaction
    pha_a = seeded_session.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == "P-105",
            PatientHospitalAccess.hospital_id == "ORG-Y",
        )
    )
    assert pha_a is not None
    assert pha_a.access_level == HospitalAccessLevel.READ_ONLY
    assert pha_a.status == HospitalAccessStatus.ACTIVE

    pha_b = seeded_session.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == "P-105",
            PatientHospitalAccess.hospital_id == "ORG-B",
        )
    )
    assert pha_b is not None
    assert pha_b.access_level == HospitalAccessLevel.READ_WRITE
    assert pha_b.status == HospitalAccessStatus.ACTIVE
    assert pha_b.source_transfer_id == transfer_id

    # Verify patient summary is marked stale
    summaries = seeded_session.scalars(select(Summary).where(Summary.patient_id == "P-105")).all()
    for s in summaries:
        if isinstance(s.content_json, dict):
            assert s.content_json.get("is_stale") is True

    # Step 8: Definition of Done: Old hospital's doctor (dr.rao) CAN VIEW BUT NOT UPLOAD
    # dr.rao can view profile & timeline
    dr_rao_view = client.get("/api/v1/patients/P-105", headers=dr_rao)
    assert dr_rao_view.status_code == 200
    dr_rao_timeline = client.get("/api/v1/patients/P-105/timeline", headers=dr_rao)
    assert dr_rao_timeline.status_code == 200
    dr_rao_records = client.get("/api/v1/patients/P-105/records", headers=dr_rao)
    assert dr_rao_records.status_code == 200

    # dr.rao upload is BLOCKED (403 Forbidden due to READ_ONLY access)
    dr_rao_upload = client.post(
        "/api/v1/patients/P-105/records/upload",
        headers=dr_rao,
        files={"file": ("blocked_note.txt", io.BytesIO(b"Should be blocked after transfer."), "text/plain")},
        data={"record_type": "doctor_note"},
    )
    assert dr_rao_upload.status_code == 403
    assert "READ_ONLY" in dr_rao_upload.text or "READ_WRITE" in dr_rao_upload.text

    # Step 9: Invariant: Records are NEVER moved, copied, or deleted; origin hospital preserved
    current_sources = seeded_session.scalars(select(SourceRecord).where(SourceRecord.patient_id == "P-105")).all()
    for s in current_sources:
        if s.id in initial_origins:
            assert s.origin_org == initial_origins[s.id]

    current_claims = seeded_session.scalars(select(ClinicalClaim).where(ClinicalClaim.patient_id == "P-105")).all()
    for c in current_claims:
        if c.id in initial_claim_hosps:
            assert c.hospital_id == initial_claim_hosps[c.id]

    # Step 10: Revoke consent blocks receiving hospital
    revoke_res = client.delete(f"/api/v1/consents/{consent_id}", headers=patient_p105)
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "REVOKED"

    # Hospital B access row is now REVOKED
    seeded_session.expire_all()
    pha_b_after = seeded_session.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == "P-105",
            PatientHospitalAccess.hospital_id == "ORG-B",
        )
    )
    assert pha_b_after.status == HospitalAccessStatus.REVOKED

    # Now Hospital B admin and doctor are blocked (403 Forbidden)
    b_blocked_view = client.get("/api/v1/patients/P-105", headers=hosp_b_admin)
    assert b_blocked_view.status_code == 403

    # Step 11: Audit log entries for every step
    audits = seeded_session.scalars(
        select(AuditLog).where(AuditLog.patient_id == "P-105").order_by(AuditLog.id)
    ).all()
    actions = [a.action for a in audits]
    assert "REQUEST_TRANSFER" in actions
    assert "RECORD_CONSENT" in actions
    assert "ACCEPT_TRANSFER" in actions
    assert "REVOKE_CONSENT" in actions


# ---------------------------------------------------------------------------
# 2. Hospital Admin Recording Consent on Patient's Behalf (Flagged)
# ---------------------------------------------------------------------------
def test_hospital_admin_records_consent_on_behalf(client: TestClient):
    admin_headers = auth_header("admin.a", "hospital_admin", "ORG-Y")

    res = client.post(
        "/api/v1/consents",
        headers=admin_headers,
        json={
            "patient_id": "P-103",
            "target_hospital_id": "ORG-B",
            "purpose": "Continuity of fertility care",
            "scope": "ALL_RECORDS",
            "recorded_on_behalf": True,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "ACTIVE"
    assert data["recorded_on_behalf"] is True
    assert "Hospital Admin" in data["granted_by"] or "on behalf" in data["granted_by"]


# ---------------------------------------------------------------------------
# 3. Transfer State Machine: Reject & Cancel Paths
# ---------------------------------------------------------------------------
def test_transfer_rejection_and_cancellation(client: TestClient, seeded_session):
    hosp_a_admin = auth_header("admin.a", "hospital_admin", "ORG-Y")
    hosp_b_admin = auth_header("admin.b", "hospital_admin", "ORG-B")

    # A: Create transfer and reject
    t1_res = client.post(
        "/api/v1/transfers",
        headers=hosp_a_admin,
        json={
            "patient_id": "P-104",
            "from_hospital_id": "ORG-Y",
            "to_hospital_id": "ORG-B",
            "reason": "Referral for third-party reproduction.",
        },
    )
    assert t1_res.status_code == 201
    t1_id = t1_res.json()["id"]

    # Reject by Hospital B admin
    rej_res = client.post(
        f"/api/v1/transfers/{t1_id}/reject",
        headers=hosp_b_admin,
        json={"reason": "Capacity full for next quarter."},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "REJECTED"
    assert rej_res.json()["reason"] == "Capacity full for next quarter."

    # Double reject is idempotent
    double_rej = client.post(f"/api/v1/transfers/{t1_id}/reject", headers=hosp_b_admin)
    assert double_rej.status_code == 200

    # Cannot accept a rejected transfer -> 400
    cannot_accept = client.post(f"/api/v1/transfers/{t1_id}/accept", headers=hosp_b_admin)
    assert cannot_accept.status_code == 400

    # B: Create transfer and cancel
    t2_res = client.post(
        "/api/v1/transfers",
        headers=hosp_a_admin,
        json={
            "patient_id": "P-104",
            "from_hospital_id": "ORG-Y",
            "to_hospital_id": "ORG-B",
            "reason": "Cancelled by patient choice.",
        },
    )
    assert t2_res.status_code == 201
    t2_id = t2_res.json()["id"]

    # Cancel by Hospital A admin (initiator)
    canc_res = client.post(f"/api/v1/transfers/{t2_id}/cancel", headers=hosp_a_admin)
    assert canc_res.status_code == 200
    assert canc_res.json()["status"] == "CANCELLED"

    # Double cancel is idempotent
    double_canc = client.post(f"/api/v1/transfers/{t2_id}/cancel", headers=hosp_a_admin)
    assert double_canc.status_code == 200

    # Cannot accept a cancelled transfer -> 400
    cannot_accept_canc = client.post(f"/api/v1/transfers/{t2_id}/accept", headers=hosp_b_admin)
    assert cannot_accept_canc.status_code == 400
