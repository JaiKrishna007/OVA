import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.source_record import SourceRecord
from app.models.audit_log import AuditLog
from app.models.summary import Summary


def get_token(client: TestClient, username: str, password: str = "password123") -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def test_summary_cache_hit_and_definition_of_done(client: TestClient):
    """
    Definition of Done:
    P-101 summary returns in a single call with the mock provider,
    and a second call is served from cache without re-generation.
    """
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    # Call 1: Initial generation
    resp1 = client.get("/api/v1/patients/P-101/summary", headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()

    assert data1["patient_id"] == "P-101"
    assert data1["metadata"]["version"] == 1
    assert data1["metadata"]["from_cache"] is False
    assert len(data1["snapshot"]) <= 5
    assert len(data1["snapshot"]) > 0
    assert data1["disclaimer"] == "AI-assisted summary. Clinician review required."

    assert len(data1["conflicts"]) == 0
    assert len(data1["not_documented"]) == 0

    # Call 2: Served from cache
    resp2 = client.get("/api/v1/patients/P-101/summary", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data2["patient_id"] == "P-101"
    assert data2["metadata"]["version"] == 1
    assert data2["metadata"]["from_cache"] is True
    assert data2["is_stale"] is False
    assert data2["metadata"]["data_version"] == data1["metadata"]["data_version"]


def test_cache_invalidation_after_record_change(
    client: TestClient,
    seeded_session: Session,
):
    """
    When underlying clinical records for a patient are updated,
    data_version hash changes, invalidating cache and generating version 2.
    """
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Warm cache (version 1)
    resp1 = client.get("/api/v1/patients/P-101/summary", headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["metadata"]["version"] == 1

    # 2. Mutate a source record for P-101 in the database
    rec = seeded_session.get(SourceRecord, "REC-0101")
    assert rec is not None
    rec.version += 1
    seeded_session.commit()

    # 3. Check status shows is_stale = True
    status_resp = client.get("/api/v1/patients/P-101/summary/status", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["is_stale"] is True

    # 4. Request summary again: cache should invalidate and trigger version 2
    resp2 = client.get("/api/v1/patients/P-101/summary", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["metadata"]["version"] == 2
    assert data2["metadata"]["from_cache"] is False


def test_section_only_regenerate(client: TestClient):
    """
    POST /patients/{id}/summary/regenerate with a specific sections list
    triggers regeneration and increments version.
    """
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    # Initial get
    client.get("/api/v1/patients/P-101/summary", headers=headers)

    # Force regenerate only prior_cycles
    resp = client.post(
        "/api/v1/patients/P-101/summary/regenerate",
        headers=headers,
        json={"sections": ["prior_cycles"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["version"] >= 2
    assert "sections" in data
    assert "prior_cycles" in data["sections"]


def test_summary_scope_failures(client: TestClient):
    """
    Verifies RBAC and patient assignment scope rules:
    - Doctor dr.rao gets 403 on unassigned patient P-106.
    - Staff nurse.devi gets 403 on AI summary.
    """
    doctor_token = get_token(client, "dr.rao")
    staff_token = get_token(client, "nurse.devi")

    # Doctor on unassigned patient P-106
    resp_unassigned = client.get(
        "/api/v1/patients/P-106/summary",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp_unassigned.status_code == 403
    assert resp_unassigned.json()["error"]["code"] == "FORBIDDEN"

    # Staff on summary
    resp_staff = client.get(
        "/api/v1/patients/P-101/summary",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp_staff.status_code == 403
    assert resp_staff.json()["error"]["code"] == "FORBIDDEN"


def test_summary_snapshot_length_param(client: TestClient):
    """
    GET /patients/{id}/summary?length=snapshot returns snapshot lines and disclaimer
    without full section objects.
    """
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/patients/P-101/summary?length=snapshot", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "snapshot" in data
    assert len(data["snapshot"]) <= 5
    assert "disclaimer" in data
    assert "sections" not in data


def test_summary_status_endpoint(client: TestClient):
    """
    GET /patients/{id}/summary/status returns readiness, version, and data staleness.
    """
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    # Before generation on P-102
    resp = client.get("/api/v1/patients/P-102/summary/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "P-102"
    assert data["status"] in ("ready", "not_generated")

    # Generate summary on P-102
    client.get("/api/v1/patients/P-102/summary", headers=headers)

    # Check status again
    resp2 = client.get("/api/v1/patients/P-102/summary/status", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "ready"
    assert data2["version"] == 1
    assert data2["is_stale"] is False


def test_summary_audit_logs_written(client: TestClient, seeded_session: Session):
    """
    Summary view and regenerate endpoints write audit rows.
    """
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    # View summary
    client.get("/api/v1/patients/P-101/summary", headers=headers)
    # Regenerate summary
    client.post("/api/v1/patients/P-101/summary/regenerate", headers=headers, json={})

    # Check audit log in database
    audit_rows = seeded_session.scalars(
        select(AuditLog).where(AuditLog.patient_id == "P-101")
    ).all()
    actions = [a.action for a in audit_rows]
    assert "summary_view" in actions
    assert "summary_regenerate" in actions
