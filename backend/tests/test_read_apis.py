import pytest
from fastapi.testclient import TestClient


def get_token(client: TestClient, username: str, password: str = "password123") -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, f"Login failed for {username}: {response.text}"
    return response.json()["access_token"]


def test_get_patients_search_and_phone_masked(client: TestClient):
    """GET /patients?q= fuzzy search on name, id, phone masked, verifying doctor scope."""
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Search by name
    res = client.get("/api/v1/patients?q=Priya", headers=headers)
    assert res.status_code == 200
    patients = res.json()
    assert len(patients) == 1
    p = patients[0]
    assert p["id"] == "P-101"
    assert p["name"] == "Priya S."
    assert p["phone_masked"] is not None
    assert p["phone_masked"].endswith("*****")
    assert "9845012341" not in p["phone_masked"]
    assert "Cycle 1 completed" in p["current_stage"]
    assert len(p["source_refs"]) > 0

    # 2. Search by ID
    res_id = client.get("/api/v1/patients?q=101", headers=headers)
    assert res_id.status_code == 200
    assert any(pt["id"] == "P-101" for pt in res_id.json())

    # 3. Search by partial phone number
    res_phone = client.get("/api/v1/patients?q=98450", headers=headers)
    assert res_phone.status_code == 200
    assert len(res_phone.json()) > 0

    # 4. Unassigned patient P-106 is NOT in dr.rao's search results
    all_res = client.get("/api/v1/patients", headers=headers)
    assert all_res.status_code == 200
    all_ids = [pt["id"] for pt in all_res.json()]
    assert "P-106" not in all_ids
    assert "P-101" in all_ids


def test_get_patient_detail(client: TestClient):
    """GET /patients/{id} returns patient profile with stage and source_refs."""
    token = get_token(client, "dr.rao")
    res = client.get("/api/v1/patients/P-101", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "P-101"
    assert data["name"] == "Priya S."
    assert data["phone_masked"].endswith("*****")
    assert "Cycle 1 completed" in data["current_stage"]
    assert len(data["source_refs"]) > 0


def test_get_patient_timeline(client: TestClient):
    """GET /patients/{id}/timeline returns ordered cycles, badges, trust tags, and source_refs."""
    token = get_token(client, "dr.rao")
    res = client.get("/api/v1/patients/P-101/timeline", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["patient_id"] == "P-101"
    assert data["total_cycles"] == 1
    assert len(data["cycles"]) == 1
    assert len(data["source_refs"]) > 0

    # Verify cycle properties
    c = data["cycles"][0]
    assert c["cycle_id"] == "CY-P101-1"
    assert "Ongoing" in c["outcome_badge"] or "Pregnancy" in c["outcome_badge"]
    assert c["trust_status"] == "internal_verified"
    assert len(c["source_refs"]) > 0


def test_get_patient_cycle_detail(client: TestClient):
    """GET /patients/{id}/cycles/{cycle_id} returns detailed cycle breakdown with source_refs."""
    token = get_token(client, "dr.rao")
    res = client.get("/api/v1/patients/P-101/cycles/CY-P101-1", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "CY-P101-1"
    assert data["cycle_no"] == 1
    assert data["type"] == "IVF"
    assert "Ongoing" in data["outcome_badge"] or "Pregnancy" in data["outcome_badge"]
    assert data["opu"]["oocytes_retrieved"] > 0
    assert len(data["embryos"]) > 0
    assert len(data["transfers"]) > 0
    assert data["pregnancy_outcome"]["result"] in ("ongoing", "clinical", "positive")
    assert len(data["source_refs"]) > 0


def test_get_patient_cycle_comparison(client: TestClient):
    """GET /patients/{id}/cycle-comparison returns multi-cycle comparison matrix."""
    token = get_token(client, "dr.rao")
    res = client.get("/api/v1/patients/P-101/cycle-comparison", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["patient_id"] == "P-101"
    assert len(data["comparison_matrix"]) == 1
    assert len(data["source_refs"]) > 0

    row_c1 = next(r for r in data["comparison_matrix"] if r["cycle_id"] == "CY-P101-1")
    assert row_c1["oocytes"] > 0
    assert row_c1["mii"] > 0


def test_get_patient_embryos(client: TestClient):
    """GET /patients/{id}/embryos returns embryos inventory with remaining_frozen count."""
    token = get_token(client, "dr.rao")
    res = client.get("/api/v1/patients/P-101/embryos", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["patient_id"] == "P-101"
    assert data["remaining_frozen"] == 2
    assert data["total_count"] >= 1
    assert len(data["source_refs"]) > 0
    for emb in data["embryos"]:
        assert "source_refs" in emb
        assert len(emb["source_refs"]) > 0


def test_get_patient_stimulation(client: TestClient):
    """GET /patients/{id}/stimulation/{cycle_id} returns flow sheet, hormones, follicles, medications."""
    token = get_token(client, "dr.rao")
    res = client.get("/api/v1/patients/P-101/stimulation/CY-P101-1", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["patient_id"] == "P-101"
    assert data["cycle_id"] == "CY-P101-1"
    assert data["summary"]["total_days"] >= 0
    assert len(data["days"]) >= 0
    assert len(data["source_refs"]) > 0


def test_get_patient_followups(client: TestClient):
    """GET /patients/{id}/followups returns categorized followups with overdue TSH."""
    token = get_token(client, "dr.rao")
    res = client.get("/api/v1/patients/P-101/followups", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["patient_id"] == "P-101"
    assert data["as_of_date"] == "2026-06-25"
    assert data["counts"]["overdue"] >= 1
    assert any("Early Viability Ultrasound Scan" in item["name"] for item in data["overdue"])
    assert len(data["source_refs"]) > 0


def test_patch_followup_and_audit(client: TestClient):
    """PATCH /followups/{id} updates followup status and logs audit entry."""
    # Find a followup ID for P-101
    doctor_token = get_token(client, "dr.rao")
    doctor_headers = {"Authorization": f"Bearer {doctor_token}"}
    fol_res = client.get("/api/v1/patients/P-101/followups", headers=doctor_headers)
    assert fol_res.status_code == 200
    overdue_item = fol_res.json()["overdue"][0]
    followup_id = overdue_item["id"]

    # Doctor patches status to 'done'
    patch_res = client.patch(
        f"/api/v1/followups/{followup_id}",
        json={"status": "done"},
        headers=doctor_headers,
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["id"] == followup_id
    assert updated["status"] == "done"
    assert len(updated["source_refs"]) > 0

    # Staff can also update followups
    staff_token = get_token(client, "nurse.devi")
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    patch_res2 = client.patch(
        f"/api/v1/followups/{followup_id}",
        json={"name": "Repeat TSH Completed"},
        headers=staff_headers,
    )
    assert patch_res2.status_code == 200
    assert patch_res2.json()["name"] == "Repeat TSH Completed"

    # Check audit log as admin
    admin_token = get_token(client, "admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    audit_res = client.get("/api/v1/audit", headers=admin_headers)
    assert audit_res.status_code == 200
    actions = [row["action"] for row in audit_res.json()]
    assert "followup_update" in actions


def test_get_source_record(client: TestClient):
    """GET /records/{source_id} returns content_text, origin, trust with authorized access."""
    token = get_token(client, "dr.rao")
    res = client.get("/api/v1/records/REC-0103", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "REC-0103"
    assert data["patient_id"] == "P-101"
    assert data["origin_org"] == "ORG-Y"
    assert data["trust_status"] == "internal_verified"
    assert "OVUM PICKUP (OPU)" in data["content_text"]
    assert "EMBRYOLOGY" in data["content_text"]
    assert data["source_refs"] == ["REC-0103"]


def test_get_patient_records_paginated_and_filtered(client: TestClient):
    """GET /patients/{id}/records with pagination and type filtering."""
    token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Paginated records
    res = client.get("/api/v1/patients/P-101/records?page=1&page_size=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["patient_id"] == "P-101"
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["records"]) <= 2
    assert data["total"] >= 2
    assert data["total_pages"] >= 1
    for r in data["records"]:
        assert "content_excerpt" in r
        assert len(r["source_refs"]) > 0

    # 2. Filtered by type
    filter_res = client.get("/api/v1/patients/P-101/records?type=lab_report", headers=headers)
    assert filter_res.status_code == 200
    f_data = filter_res.json()
    assert "records" in f_data


def test_scope_and_permission_failures(client: TestClient):
    """Verify security boundaries and standard error responses."""
    doctor_token = get_token(client, "dr.rao")
    headers = {"Authorization": f"Bearer {doctor_token}"}

    # 1. Accessing unassigned patient P-106 -> 403
    p106_res = client.get("/api/v1/patients/P-106", headers=headers)
    assert p106_res.status_code == 403
    err106 = p106_res.json()
    assert err106["error"]["code"] == "FORBIDDEN"
    assert err106["error"]["request_id"].startswith("r-")

    # 2. Accessing source record of unassigned patient P-106 (REC-0601) -> 403
    rec_res = client.get("/api/v1/records/REC-0601", headers=headers)
    assert rec_res.status_code == 403
    err_rec = rec_res.json()
    assert err_rec["error"]["code"] == "FORBIDDEN"

    # 3. Accessing wrong cycle for patient -> 404
    wrong_cy_res = client.get("/api/v1/patients/P-101/cycles/CY-P102-1", headers=headers)
    assert wrong_cy_res.status_code == 404
    err_cy = wrong_cy_res.json()
    assert err_cy["error"]["code"] == "NOT_FOUND"

    # 4. Accessing non-existent record -> 404
    non_rec_res = client.get("/api/v1/records/REC-9999", headers=headers)
    assert non_rec_res.status_code == 404
    assert non_rec_res.json()["error"]["code"] == "NOT_FOUND"

    # 5. Non-existent followup -> 404
    non_fol_res = client.patch("/api/v1/followups/FOL-9999", json={"status": "done"}, headers=headers)
    assert non_fol_res.status_code == 404
    assert non_fol_res.json()["error"]["code"] == "NOT_FOUND"


def test_openapi_schema_contains_all_routes(client: TestClient):
    """Verify OpenAPI specification exposes all required routes."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    paths = schema.get("paths", {})

    required_endpoints = [
        "/api/v1/patients",
        "/api/v1/patients/{patient_id}",
        "/api/v1/patients/{patient_id}/timeline",
        "/api/v1/patients/{patient_id}/cycles/{cycle_id}",
        "/api/v1/patients/{patient_id}/cycle-comparison",
        "/api/v1/patients/{patient_id}/embryos",
        "/api/v1/patients/{patient_id}/stimulation/{cycle_id}",
        "/api/v1/patients/{patient_id}/followups",
        "/api/v1/followups/{followup_id}",
        "/api/v1/records/{source_id}",
        "/api/v1/patients/{patient_id}/records",
    ]

    for endpoint in required_endpoints:
        assert endpoint in paths, f"OpenAPI missing path: {endpoint}"
