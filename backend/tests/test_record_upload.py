"""
Tests for document upload endpoint POST /patients/{id}/records/upload and GET /records/{id}/status:
1. Upload each allowed file type (.txt, .json, .pdf).
2. Oversized file rejected with 413.
3. Unsupported file type rejected with 415.
4. Duplicate upload rejected with 409.
5. Path traversal filename neutralized and safely saved.
6. Hospital with READ_ONLY access forbidden (403).
7. Unassigned doctor forbidden (403).
8. Scanned / image-only PDF triggers NEEDS_OCR status.
9. GET /records/{id}/status returns valid processing metadata.
10. Audit log entries are recorded for uploads.
"""

import io
import json
import os
import pytest
from datetime import date
from starlette.testclient import TestClient

from app.main import create_app
from app.db.session import SessionLocal
from app.models import (
    User,
    Patient,
    SourceRecord,
    PatientHospitalAccess,
    HospitalAccessLevel,
    HospitalAccessStatus,
    SourceProcessingStatus,
    AuditLog,
)
from app.core.security import create_access_token


@pytest.fixture
def dr_rao_token():
    return create_access_token(data={"sub": "dr.rao", "role": "doctor", "org_id": "ORG-Y"})


@pytest.fixture
def admin_token():
    return create_access_token(data={"sub": "admin.prime", "role": "admin", "org_id": "ORG-Y"})


def _create_simple_pdf_bytes(text: str) -> bytes:
    """Helper creating a minimal valid PDF with an embedded text stream."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 700, text)
    c.save()
    return buf.getvalue()


def _create_blank_pdf_bytes() -> bytes:
    """Helper creating a valid PDF page with no text (simulating scanned/image-only PDF)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # No text drawn
    c.showPage()
    c.save()
    return buf.getvalue()


def test_upload_txt_record_success(client, dr_rao_token, seeded_session):
    """Uploading a TXT lab report for assigned patient P-102 succeeds and persists content."""
    txt_content = f"CLINICAL LAB REPORT\nPatient: Anitha R.\nSerum AMH: 4.2 ng/mL\nDate: 2024-05-15\nMethod: ECLIA\nNonce: {os.urandom(6).hex()}"
    response = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers={"Authorization": f"Bearer {dr_rao_token}"},
        data={"record_type": "lab_report", "record_date": "2024-05-15"},
        files={"file": ("amh_lab_report.txt", txt_content.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["patient_id"] == "P-102"
    assert data["type"] == "lab_report"
    assert data["processing_status"] == "VALIDATED"
    assert "Serum AMH: 4.2 ng/mL" in data["content_text"]
    assert data["id"].startswith("REC-")

    # Verify audit log recorded
    audit = seeded_session.query(AuditLog).filter(
        AuditLog.patient_id == "P-102",
        AuditLog.action == "record_upload",
    ).order_by(AuditLog.at.desc()).first()
    assert audit is not None
    assert audit.user_id == "USR-RAO"


def test_upload_json_record_success(client, dr_rao_token):
    """Uploading a JSON clinical document flattens into structured text."""
    payload = {
        "report_type": "ultrasound",
        "endometrium_thickness_mm": 9.5,
        "right_ovary_follicles": [18, 16, 14],
        "left_ovary_follicles": [17, 15],
        "nonce": os.urandom(6).hex(),
    }
    json_bytes = json.dumps(payload).encode("utf-8")

    response = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers={"Authorization": f"Bearer {dr_rao_token}"},
        data={"record_type": "imaging_report", "record_date": "2024-05-16"},
        files={"file": ("scan_data.json", json_bytes, "application/json")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["processing_status"] == "VALIDATED"
    assert "endometrium_thickness_mm: 9.5" in data["content_text"]


def test_upload_pdf_record_success(client, dr_rao_token):
    """Uploading a text PDF extracts embedded text properly."""
    pdf_bytes = _create_simple_pdf_bytes("Hormone Profile: Estradiol E2 2450 pg/mL on Day 10.")

    response = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers={"Authorization": f"Bearer {dr_rao_token}"},
        data={"record_type": "lab_report", "record_date": "2024-05-17"},
        files={"file": ("e2_hormone.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["processing_status"] == "VALIDATED"
    assert "Estradiol E2 2450 pg/mL" in data["content_text"]


def test_upload_scanned_pdf_triggers_needs_ocr(client, dr_rao_token):
    """Uploading an empty/scanned PDF without text triggers NEEDS_OCR status."""
    blank_pdf = _create_blank_pdf_bytes()

    response = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers={"Authorization": f"Bearer {dr_rao_token}"},
        data={"record_type": "scan_copy", "record_date": "2024-05-18"},
        files={"file": ("scanned_blank.pdf", blank_pdf, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["processing_status"] == "NEEDS_OCR"
    assert any("OCR" in w for w in data["warnings"])


def test_upload_duplicate_rejected_with_409(client, dr_rao_token):
    """Uploading the exact same file content for the same patient returns 409 Conflict."""
    unique_content = f"Unique note {os.urandom(8).hex()}"
    file_bytes = unique_content.encode("utf-8")

    # 1. First upload succeeds
    res1 = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers={"Authorization": f"Bearer {dr_rao_token}"},
        data={"record_type": "clinical_note"},
        files={"file": ("note.txt", file_bytes, "text/plain")},
    )
    assert res1.status_code == 200

    # 2. Duplicate upload fails with 409
    res2 = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers={"Authorization": f"Bearer {dr_rao_token}"},
        data={"record_type": "clinical_note"},
        files={"file": ("note_copy.txt", file_bytes, "text/plain")},
    )
    assert res2.status_code == 409
    msg2 = res2.json().get("error", {}).get("message", res2.text)
    assert "duplicate" in msg2.lower()


def test_upload_unsupported_file_type_rejected_with_415(client, dr_rao_token):
    """Uploading a disallowed file format (.docx, .png, etc.) returns 415."""
    response = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers={"Authorization": f"Bearer {dr_rao_token}"},
        data={"record_type": "scan"},
        files={"file": ("image.png", b"\x89PNG\r\n\x1a\nfakeimage", "image/png")},
    )
    assert response.status_code == 415
    msg = response.json().get("error", {}).get("message", response.text)
    assert "not supported" in msg.lower()


def test_upload_oversized_file_rejected_with_413(client, dr_rao_token, monkeypatch):
    """Uploading a file exceeding configured max size returns 413."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 100)

    large_bytes = b"X" * 150
    response = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers={"Authorization": f"Bearer {dr_rao_token}"},
        data={"record_type": "lab_report"},
        files={"file": ("large.txt", large_bytes, "text/plain")},
    )
    assert response.status_code == 413
    msg = response.json().get("error", {}).get("message", response.text)
    assert "exceeds" in msg.lower()


def test_path_traversal_filename_neutralized(client, dr_rao_token, seeded_session):
    """Filename containing directory traversal sequences is sanitized."""
    txt_content = f"Path traversal test {os.urandom(8).hex()}"
    response = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers={"Authorization": f"Bearer {dr_rao_token}"},
        data={"record_type": "clinical_note"},
        files={"file": ("../../../../etc/passwd.txt", txt_content.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200
    rec_id = response.json()["id"]

    rec = seeded_session.get(SourceRecord, rec_id)
    assert rec is not None
    # Verify file path is within uploads directory and has no ..
    assert ".." not in rec.file_path
    assert "passwd" in rec.file_path


def test_read_only_hospital_forbidden_with_403(client, seeded_session):
    """A hospital with READ_ONLY access delegation is forbidden from uploading records."""
    from app.models.enums import UserRole
    # Create doctor in external hospital ORG-X if not existing
    ext_user = seeded_session.query(User).filter_by(username="dr.external").first()
    if not ext_user:
        ext_user = User(
            id="USR-DR-EXT",
            username="dr.external",
            password_hash="mockhash",
            role=UserRole.DOCTOR,
            org_id="ORG-X",
        )
        seeded_session.add(ext_user)
        seeded_session.commit()

    dr_x_token = create_access_token(data={"sub": "dr.external", "role": "doctor", "org_id": "ORG-X"})

    # Grant READ_ONLY access to ORG-X for P-102
    existing_pha = seeded_session.query(PatientHospitalAccess).filter_by(
        patient_id="P-102",
        hospital_id="ORG-X",
    ).first()
    if not existing_pha:
        pha = PatientHospitalAccess(
            id="PHA-TEST-RO",
            patient_id="P-102",
            hospital_id="ORG-X",
            access_level=HospitalAccessLevel.READ_ONLY,
            status=HospitalAccessStatus.ACTIVE,
        )
        seeded_session.add(pha)
        seeded_session.commit()
    else:
        existing_pha.access_level = HospitalAccessLevel.READ_ONLY
        existing_pha.status = HospitalAccessStatus.ACTIVE
        seeded_session.commit()

    response = client.post(
        "/api/v1/patients/P-102/records/upload",
        headers={"Authorization": f"Bearer {dr_x_token}"},
        data={"record_type": "external_note"},
        files={"file": ("ext_report.txt", b"External lab note", "text/plain")},
    )
    assert response.status_code == 403
    msg = response.json().get("error", {}).get("message", response.text)
    assert "read_only" in msg.lower() or "not assigned" in msg.lower()


def test_unassigned_doctor_forbidden_with_403(client):
    """A doctor not assigned to the patient cannot upload records."""
    token = create_access_token(data={"sub": "dr.rao", "role": "doctor", "org_id": "ORG-Y"})
    response = client.post(
        "/api/v1/patients/P-106/records/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"record_type": "clinical_note"},
        files={"file": ("note.txt", b"Doctor note for unassigned patient", "text/plain")},
    )
    assert response.status_code == 403
    msg = response.json().get("error", {}).get("message", response.text)
    assert "not assigned" in msg.lower()


def test_get_record_status_endpoint(client, dr_rao_token):
    """GET /records/{id}/status returns document status and metadata."""
    # Use existing seed record
    response = client.get(
        "/api/v1/records/REC-0101/status",
        headers={"Authorization": f"Bearer {dr_rao_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == "REC-0101"
    assert data["patient_id"] == "P-101"
    assert data["processing_status"] in ["VALIDATED", "UPLOADED"]
