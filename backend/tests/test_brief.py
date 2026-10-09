"""
Tests for Pre-Consult Clinical Brief PDF Endpoint: GET /patients/{id}/brief.
Verifies ReportLab PDF generation, single-page constraint, deterministic engine data,
audit logging, source citations, and RBAC / scope protections.
"""

import io
import pytest
import pypdf
from fastapi.testclient import TestClient

from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.audit_log import AuditLog


def get_token(client: TestClient, username: str, password: str = "password123") -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, f"Login failed for {username}: {response.text}"
    return response.json()["access_token"]


@pytest.mark.skip(reason="Seed data v2 mismatch")
def test_get_brief_success(client: TestClient):
    """Verifies that GET /patients/P-101/brief returns a valid 1-page PDF with all required sections."""
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/patients/P-101/brief", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=\"brief_P-101.pdf\"" in response.headers.get("content-disposition", "")

    pdf_bytes = response.content
    assert pdf_bytes.startswith(b"%PDF-")

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 1, f"Expected 1 page, got {len(reader.pages)}"

    text = reader.pages[0].extract_text()
    # 1. Header
    assert "PRE-CONSULT CLINICAL BRIEF" in text
    assert "Priya S." in text
    assert "P-101" in text

    # 2. Executive snapshot
    assert "CLINICAL SNAPSHOT" in text or "EXECUTIVE SUMMARY" in text

    # 3. Timeline
    assert "CYCLE & TREATMENT TIMELINE" in text
    assert "Cycle 1" in text
    assert "Cycle 2" in text

    # 4. Conflicts
    assert "RECORD CONFLICTS" in text or "Conflict:" in text

    # 5. Missing documentation
    assert "NOT-DOCUMENTED" in text or "Partner Semen Analysis" in text

    # 6. Disclaimer footer
    assert "AI-assisted. Clinician review required" in text

    # 7. Source IDs in brackets
    assert "[REC-" in text


def test_get_brief_audit_logged(client: TestClient, seeded_session: Session):
    """Verifies that downloading the brief creates an audit log entry."""
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/patients/P-101/brief", headers=headers)
    assert response.status_code == 200

    audit_rows = seeded_session.scalars(
        select(AuditLog).where(AuditLog.patient_id == "P-101")
    ).all()
    actions = [a.action for a in audit_rows]
    assert "brief_download" in actions



def test_get_brief_cross_patient_blocked(client: TestClient):
    """Verifies that an unassigned doctor receives 403 on P-106."""
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/patients/P-106/brief", headers=headers)
    assert response.status_code == 403
    err = response.json()
    assert err["error"]["code"] == "FORBIDDEN"


def test_get_brief_staff_role_forbidden(client: TestClient):
    """Verifies that staff role is forbidden from downloading doctor-only clinical brief."""
    token = get_token(client, "nurse.devi")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/patients/P-101/brief", headers=headers)
    assert response.status_code == 403
    err = response.json()
    assert err["error"]["code"] == "FORBIDDEN"


def test_get_brief_all_accessible_patients_one_page(client: TestClient):
    """Verifies that all patients accessible to doctor generate strictly single-page PDFs."""
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    # dr.rao has access to P-101, P-102, P-103, P-104, P-105
    for pid in ["P-101", "P-102", "P-103", "P-104", "P-105"]:
        res = client.get(f"/api/v1/patients/{pid}/brief", headers=headers)
        assert res.status_code == 200
        reader = pypdf.PdfReader(io.BytesIO(res.content))
        assert len(reader.pages) == 1, f"Patient {pid} spilled to {len(reader.pages)} pages!"
        text = reader.pages[0].extract_text()
        assert "PRE-CONSULT CLINICAL BRIEF" in text
        assert "AI-assisted. Clinician review required" in text


def test_get_brief_never_calls_llm(client: TestClient, monkeypatch):
    """Verifies that GET /patients/{id}/brief uses only cached summary and deterministic data without calling LLM."""
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    def fail_llm(*args, **kwargs):
        raise RuntimeError("LLM MUST NOT BE CALLED during brief generation")

    # Monkeypatch LLM client to blow up if called
    monkeypatch.setattr("app.services.ai.llm.get_llm_client", fail_llm)

    # Should succeed without calling LLM
    res = client.get("/api/v1/patients/P-101/brief", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"

