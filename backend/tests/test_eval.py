"""
Tests for Evaluation Benchmark Endpoints: GET /eval/latest and POST /eval/run.
Verifies metrics computation, role RBAC (doctor/admin allowed, staff forbidden),
audit logging, and adversarial mode execution.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.audit_log import AuditLog


def get_token(client: TestClient, username: str, password: str = "password123") -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, f"Login failed for {username}: {response.text}"
    return response.json()["access_token"]


def test_get_eval_latest_doctor_access(client: TestClient):
    """Doctor can access latest evaluation benchmark results."""
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/eval/latest", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert "run_id" in data
    assert "summary_metrics" in data
    m = data["summary_metrics"]
    assert "fact_recall" in m
    assert "citation_accuracy" in m
    assert "unsupported_claim_rate" in m
    assert "conflict_recall" in m
    assert "absence_recall" in m
    assert "injection_pass_rate" in m

    assert m["fact_recall"] >= 0.8
    assert m["citation_accuracy"] >= 0.95
    assert m["unsupported_claim_rate"] == 0.0
    assert m["conflict_recall"] == 1.0
    assert m["absence_recall"] == 1.0
    assert m["injection_pass_rate"] == 1.0

    assert len(data.get("per_patient", [])) == 6


def test_get_eval_latest_admin_access(client: TestClient):
    """Admin can access latest evaluation benchmark results."""
    token = get_token(client, "admin")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/eval/latest", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "summary_metrics" in data


def test_get_eval_latest_staff_forbidden(client: TestClient):
    """Staff user is forbidden from accessing eval benchmark."""
    token = get_token(client, "nurse.devi")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/eval/latest", headers=headers)
    assert response.status_code == 403
    err = response.json()
    assert err["error"]["code"] == "FORBIDDEN"


def test_post_eval_run_adversarial_mode(client: TestClient, seeded_session: Session):
    """POST /eval/run?adversarial=true executes adversarial corruption benchmark and writes audit log."""
    token = get_token(client, "admin")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/api/v1/eval/run?adversarial=true", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["is_adversarial"] is True
    assert "summary_metrics" in data
    m = data["summary_metrics"]
    assert m["blocked_claim_rate"] > 0.15  # Adversarial claims actively blocked

    # Verify audit log
    audit_rows = seeded_session.scalars(
        select(AuditLog).where(AuditLog.action == "eval_run")
    ).all()
    assert len(audit_rows) > 0
