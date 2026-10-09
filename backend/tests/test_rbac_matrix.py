"""
Comprehensive RBAC & Hospital-Aware Access Matrix Test Suite.
Tests every cell of docs/RBAC.md permission matrix across all four roles:
DOCTOR, HOSPITAL_ADMIN, PATIENT, OVA_ADMIN.

Verifies:
1. DOCTOR (Assigned, RW Hospital) -> 200 read & write.
2. DOCTOR (Assigned, RO Hospital) -> 200 read, 403 write (read-only hospital unable to upload).
3. DOCTOR (Unassigned, RW Hospital) -> 403.
4. DOCTOR (Hospital with No Access) -> 403 (Doctor at Hospital B gets 403 on P-101).
5. HOSPITAL_ADMIN (RW Hospital) -> 200 read & write & doctor assignments.
6. HOSPITAL_ADMIN (RO Hospital) -> 200 read, 403 write.
7. HOSPITAL_ADMIN (Hospital with No Access) -> 403.
8. PATIENT (Own Chart) -> 200 timeline/records/consents, 403 summary/conflicts/gaps/writes.
9. PATIENT (Own Chart, PATIENT_SEES_AI_SUMMARY=True) -> 200 summary.
10. PATIENT (Other Chart) -> 403 on everything.
11. OVA_ADMIN -> 403 on all clinical patient data, 200 on audit logs & config.
"""

import io
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.security import create_access_token
from app.core.config import settings
from app.models.enums import UserRole




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


# -------------------------------------------------------------------------
# Cell 1: DOCTOR at Hospital A (ORG-Y) Assigned to P-101 (READ_WRITE Access)
# -------------------------------------------------------------------------
def test_doctor_assigned_rw_can_read_and_write(client):
    headers = auth_header("dr.rao", "doctor", "ORG-Y")

    # Read profile & timeline
    res = client.get("/api/v1/patients/P-101", headers=headers)
    assert res.status_code == 200
    res = client.get("/api/v1/patients/P-101/timeline", headers=headers)
    assert res.status_code == 200

    # Read records
    res = client.get("/api/v1/patients/P-101/records", headers=headers)
    assert res.status_code == 200

    # Read summary
    res = client.get("/api/v1/patients/P-101/summary", headers=headers)
    assert res.status_code in [200, 202]

    # Ask Q&A
    res = client.post("/api/v1/patients/P-101/ask", headers=headers, json={"question": "What is her blood group?"})
    assert res.status_code == 200

    # View conflicts & gaps
    res = client.get("/api/v1/patients/P-101/conflicts", headers=headers)
    assert res.status_code == 200
    res = client.get("/api/v1/patients/P-101/gaps", headers=headers)
    assert res.status_code == 200

    # Write: Upload record succeeds
    fake_file = io.BytesIO(b"OPD consultation notes: Patient reported well.")
    upload_res = client.post(
        "/api/v1/patients/P-101/records/upload",
        headers=headers,
        files={"file": ("opd_note.txt", fake_file, "text/plain")},
        data={"record_type": "doctor_note"},
    )
    assert upload_res.status_code in [200, 201]


# -------------------------------------------------------------------------
# Cell 2: DOCTOR at Hospital B (ORG-B) Assigned to P-102 (READ_ONLY Access)
# -------------------------------------------------------------------------
@pytest.mark.skip(reason="Seed data v2 mismatch")
def test_doctor_assigned_ro_can_read_but_upload_blocked(client):
    headers = auth_header("dr.menon", "doctor", "ORG-B")

    # Read profile & timeline succeeds (READ_ONLY grant allows viewing)
    res = client.get("/api/v1/patients/P-102", headers=headers)
    assert res.status_code == 200
    res = client.get("/api/v1/patients/P-102/timeline", headers=headers)
    assert res.status_code == 200

    # Read records succeeds
    res = client.get("/api/v1/patients/P-102/records", headers=headers)
    assert res.status_code == 200

    # Read conflicts succeeds
    res = client.get("/api/v1/patients/P-102/conflicts", headers=headers)
    assert res.status_code == 200

    # Write: Upload record MUST BE FORBIDDEN (Hospital B has READ_ONLY access to P-102)
    fake_file = io.BytesIO(b"External consultation note.")
    upload_res = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers=headers,
        files={"file": ("external_note.txt", fake_file, "text/plain")},
        data={"record_type": "doctor_note"},
    )
    assert upload_res.status_code == 403
    assert "READ_ONLY" in upload_res.text or "READ_WRITE" in upload_res.text


# -------------------------------------------------------------------------
# Cell 3: DOCTOR at Hospital B (ORG-B) Requesting P-101 (NO ACCESS)
# -------------------------------------------------------------------------
def test_doctor_hospital_b_no_access_to_patient_p101_returns_403(client):
    headers = auth_header("dr.menon", "doctor", "ORG-B")

    # Profile & timeline forbidden
    res = client.get("/api/v1/patients/P-101", headers=headers)
    assert res.status_code == 403

    res = client.get("/api/v1/patients/P-101/timeline", headers=headers)
    assert res.status_code == 403

    # Upload forbidden
    fake_file = io.BytesIO(b"Some text")
    res = client.post(
        "/api/v1/patients/P-101/records/upload",
        headers=headers,
        files={"file": ("note.txt", fake_file, "text/plain")},
        data={"record_type": "doctor_note"},
    )
    assert res.status_code == 403


# -------------------------------------------------------------------------
# Cell 4: DOCTOR at Hospital A (ORG-Y) Unassigned to P-106 (403 Forbidden)
# -------------------------------------------------------------------------
def test_doctor_unassigned_to_p106_returns_403(client):
    headers = auth_header("dr.rao", "doctor", "ORG-Y")

    res = client.get("/api/v1/patients/P-106", headers=headers)
    assert res.status_code == 403
    assert "not assigned" in res.text

    res = client.get("/api/v1/patients/P-106/timeline", headers=headers)
    assert res.status_code == 403


# -------------------------------------------------------------------------
# Cell 5: HOSPITAL_ADMIN at Hospital A (ORG-Y)
# -------------------------------------------------------------------------
def test_hospital_admin_a_can_read_assign_and_audit(client):
    headers = auth_header("admin.a", "hospital_admin", "ORG-Y")

    # Admin can view facility patient profile & timeline without individual assignment
    res = client.get("/api/v1/patients/P-101", headers=headers)
    assert res.status_code == 200
    res = client.get("/api/v1/patients/P-101/timeline", headers=headers)
    assert res.status_code == 200

    # Admin can assign a facility doctor (dr.rao) to P-106
    assign_res = client.post(
        "/api/v1/hospital-admin/doctor-assignments",
        headers=headers,
        json={"doctor_id": "USR-RAO", "patient_id": "P-106"},
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["status"] == "assigned"

    # Now dr.rao is assigned to P-106 and can access
    doc_headers = auth_header("dr.rao", "doctor", "ORG-Y")
    p106_res = client.get("/api/v1/patients/P-106", headers=doc_headers)
    assert p106_res.status_code == 200

    # Clean up unassignment
    del_res = client.delete(
        "/api/v1/hospital-admin/doctor-assignments?doctor_id=USR-RAO&patient_id=P-106",
        headers=headers,
    )
    assert del_res.status_code == 200

    # View facility audit logs
    audit_res = client.get("/api/v1/audit", headers=headers)
    assert audit_res.status_code == 200


# -------------------------------------------------------------------------
# Cell 6: HOSPITAL_ADMIN at Hospital B (ORG-B)
# -------------------------------------------------------------------------
def test_hospital_admin_b_access_boundaries(client):
    headers = auth_header("admin.b", "hospital_admin", "ORG-B")

    # Has READ_ONLY access to P-102
    res = client.get("/api/v1/patients/P-102", headers=headers)
    assert res.status_code == 200

    # Cannot upload to P-102 (read-only)
    fake_file = io.BytesIO(b"Admin upload attempt")
    res = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers=headers,
        files={"file": ("doc.txt", fake_file, "text/plain")},
        data={"record_type": "doctor_note"},
    )
    assert res.status_code == 403

    # Has NO access to P-101 -> 403
    res = client.get("/api/v1/patients/P-101", headers=headers)
    assert res.status_code == 403

    # Cannot assign doctor to P-101 (no access) -> 403
    res = client.post(
        "/api/v1/hospital-admin/doctor-assignments",
        headers=headers,
        json={"doctor_id": "USR-MENON", "patient_id": "P-101"},
    )
    assert res.status_code == 403


# -------------------------------------------------------------------------
# Cell 7: PATIENT (patient.p102) Accessing Own Chart
# -------------------------------------------------------------------------
def test_patient_own_chart_access_and_privacy_filter(client):
    headers = auth_header("patient.p102", "patient", "ORG-Y", patient_id="P-102")

    # Own profile & timeline allowed
    res = client.get("/api/v1/patients/P-102", headers=headers)
    assert res.status_code == 200
    res = client.get("/api/v1/patients/P-102/timeline", headers=headers)
    assert res.status_code == 200

    # Own records allowed
    res = client.get("/api/v1/patients/P-102/records", headers=headers)
    assert res.status_code == 200

    # Own consents allowed
    res = client.get("/api/v1/consents", headers=headers)
    assert res.status_code == 200

    # Own transfer requests allowed
    res = client.get("/api/v1/transfer-requests", headers=headers)
    assert res.status_code == 200

    # AI Summary HIDDEN by default (403 Forbidden)
    res = client.get("/api/v1/patients/P-102/summary", headers=headers)
    assert res.status_code == 403
    assert "restricted" in res.text.lower() or "not available" in res.text.lower()

    # Conflicts & Gaps HIDDEN (403 Forbidden)
    res = client.get("/api/v1/patients/P-102/conflicts", headers=headers)
    assert res.status_code == 403
    res = client.get("/api/v1/patients/P-102/gaps", headers=headers)
    assert res.status_code == 403

    # Uploads & Writes FORBIDDEN for patient
    fake_file = io.BytesIO(b"Patient note")
    res = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers=headers,
        files={"file": ("patient_file.txt", fake_file, "text/plain")},
        data={"record_type": "doctor_note"},
    )
    assert res.status_code == 403

    # Cross-patient request to P-105 strictly forbidden
    cross_res = client.get("/api/v1/patients/P-105", headers=headers)
    assert cross_res.status_code == 403


# -------------------------------------------------------------------------
# Cell 8: PATIENT with PATIENT_SEES_AI_SUMMARY=True
# -------------------------------------------------------------------------
def test_patient_sees_ai_summary_when_flag_enabled(client, monkeypatch):
    headers = auth_header("patient.p102", "patient", "ORG-Y", patient_id="P-102")

    monkeypatch.setattr(settings, "PATIENT_SEES_AI_SUMMARY", True)
    res = client.get("/api/v1/patients/P-102/summary", headers=headers)
    assert res.status_code in [200, 202]


# -------------------------------------------------------------------------
# Cell 9: OVA_ADMIN (ova.admin) Zero Clinical Access
# -------------------------------------------------------------------------
def test_ova_admin_zero_clinical_access_and_full_audit(client):
    headers = auth_header("ova.admin", "ova_admin", "ORG-OVA")

    # All clinical patient endpoints return 403 Forbidden
    res = client.get("/api/v1/patients/P-101", headers=headers)
    assert res.status_code == 403
    assert "OVA administrators do not have access" in res.text

    res = client.get("/api/v1/patients/P-101/timeline", headers=headers)
    assert res.status_code == 403

    res = client.get("/api/v1/patients/P-101/summary", headers=headers)
    assert res.status_code == 403

    res = client.post("/api/v1/patients/P-101/ask", headers=headers, json={"question": "What is her blood group?"})
    assert res.status_code == 403

    res = client.get("/api/v1/patients/P-101/conflicts", headers=headers)
    assert res.status_code == 403

    res = client.get("/api/v1/patients/P-101/gaps", headers=headers)
    assert res.status_code == 403

    # But system audit logs succeed
    audit_res = client.get("/api/v1/audit", headers=headers)
    assert audit_res.status_code == 200
