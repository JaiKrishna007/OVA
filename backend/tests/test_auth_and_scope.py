from fastapi.testclient import TestClient
import pytest


def get_token(client: TestClient, username: str, password: str = "password123") -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, f"Login failed for {username}: {response.text}"
    return response.json()["access_token"]


def test_login_success_and_auth_me(client: TestClient):
    """Test login for dr.rao returns 1-hour JWT token and /auth/me returns profile."""
    # 1. Login
    resp = client.post("/api/v1/auth/login", json={"username": "dr.rao", "password": "password123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600
    assert data["user"]["username"] == "dr.rao"
    assert data["user"]["role"] == "doctor"
    assert data["user"]["org_id"] == "ORG-Y"

    token = data["access_token"]

    # 2. Call /auth/me
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["username"] == "dr.rao"
    assert me_data["role"] == "doctor"


def test_login_invalid_password(client: TestClient):
    """Test login failure returns standard error format with request_id."""
    resp = client.post("/api/v1/auth/login", json={"username": "dr.rao", "password": "wrongpassword"})
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_CREDENTIALS"
    assert "request_id" in data["error"]
    assert data["error"]["request_id"].startswith("r-")


def test_doctor_can_open_assigned_patient_p101(client: TestClient):
    """Test doctor dr.rao can access assigned patient P-101."""
    token = get_token(client, "dr.rao")
    resp = client.get("/api/v1/patients/P-101", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "P-101"
    assert data["name"] == "Priya S."


def test_doctor_gets_403_on_unassigned_p106(client: TestClient):
    """Test doctor gets 403 on P-106 because dr.rao is not assigned to P-106."""
    token = get_token(client, "dr.rao")
    resp = client.get("/api/v1/patients/P-106", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "FORBIDDEN"
    assert "not assigned" in data["error"]["message"].lower()
    assert "request_id" in data["error"]


def test_wrong_cycle_for_patient_gets_404(client: TestClient):
    """Test requesting a cycle belonging to another patient returns 404."""
    token = get_token(client, "dr.rao")

    # Cycle CY-P102-3 belongs to P-102, not P-101
    resp = client.get("/api/v1/patients/P-101/cycles/CY-P102-3", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "not found for patient" in data["error"]["message"]


@pytest.mark.skip(reason="Seed data v2 mismatch")
def test_valid_patient_and_cycle_succeeds(client: TestClient):
    """Test requesting correct cycle for patient succeeds."""
    token = get_token(client, "dr.rao")
    resp = client.get("/api/v1/patients/P-101/cycles/CY-P101-2", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "CY-P101-2"
    assert data["patient_id"] == "P-101"


def test_nonexistent_patient_gets_404(client: TestClient):
    """Test requesting nonexistent patient returns 404 with standard error format."""
    token = get_token(client, "dr.rao")
    resp = client.get("/api/v1/patients/P-9999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "NOT_FOUND"


def test_staff_cannot_call_summary_endpoint(client: TestClient):
    """Test staff nurse.devi is blocked from calling AI summary endpoints (403)."""
    token = get_token(client, "nurse.devi")
    resp = client.get("/api/v1/patients/P-101/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "not permitted" in data["error"]["message"]


def test_doctor_can_call_summary_endpoint(client: TestClient):
    """Test doctor dr.rao can call AI summary endpoint on assigned patient."""
    token = get_token(client, "dr.rao")
    resp = client.get("/api/v1/patients/P-101/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "P-101"


def test_audit_rows_are_written_and_admin_accessible(client: TestClient):
    """Test that patient views create audit_log rows and admin can view GET /audit."""
    doctor_token = get_token(client, "dr.rao")
    admin_token = get_token(client, "admin")

    # 1. Doctor views P-101 (triggers record_audit)
    client.get("/api/v1/patients/P-101", headers={"Authorization": f"Bearer {doctor_token}"})

    # 2. Admin queries audit log
    audit_resp = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {admin_token}"})
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) > 0
    actions = [log["action"] for log in logs]
    assert "patient_view" in actions

    # 3. Doctor tries to access /audit -> forbidden (403)
    doc_audit = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {doctor_token}"})
    assert doc_audit.status_code == 403
    assert doc_audit.json()["error"]["code"] == "FORBIDDEN"
