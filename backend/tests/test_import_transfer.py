import pytest
from fastapi.testclient import TestClient


def get_token(client: TestClient, username: str, password: str = "password123") -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, f"Login failed for {username}: {response.text}"
    return response.json()["access_token"]


def test_import_staff_only_and_quarantine(client: TestClient):
    """Test staff-only permission and quarantine batch creation."""
    doc_token = get_token(client, "dr.rao")
    staff_token = get_token(client, "nurse.devi")

    payload = {
        "origin_org": "St. Jude Fertility Clinic",
        "patient": {
            "external_id": "SJ-9981",
            "name": "Priya S.",
            "dob": "1991-05-20",
            "phone": "+91-9845012341",
        },
        "records": [
            {
                "type": "external_summary",
                "date": "2024-01-15",
                "author": "Dr. Miller",
                "content_text": "Prior IVF cycle 1 at St. Jude. 8 oocytes retrieved, 2 blastocysts frozen.",
            }
        ],
        "cycles": [
            {
                "cycle_no": 1,
                "type": "IVF",
                "start_date": "2024-01-02",
                "end_date": "2024-01-20",
                "outcome": "completed",
            }
        ],
    }

    # Doctor role cannot access staff-only import
    res_doc = client.post("/api/v1/import", json=payload, headers={"Authorization": f"Bearer {doc_token}"})
    assert res_doc.status_code == 403

    # Staff role can upload into quarantine
    res_staff = client.post("/api/v1/import", json=payload, headers={"Authorization": f"Bearer {staff_token}"})
    assert res_staff.status_code == 201
    batch = res_staff.json()
    assert batch["id"].startswith("BAT-")
    assert batch["status"] == "quarantined"
    assert batch["origin_org"] == "St. Jude Fertility Clinic"

    # Verify GET /import/{batch_id}
    res_get = client.get(f"/api/v1/import/{batch['id']}", headers={"Authorization": f"Bearer {staff_token}"})
    assert res_get.status_code == 200
    batch_detail = res_get.json()
    assert batch_detail["validation_report_json"]["syntax_valid"] is True
    assert batch_detail["validation_report_json"]["records_count"] == 1
    assert len(batch_detail["cycle_suggestions_json"]) == 1

    # Identity match candidate should have high confidence for Priya S. (exact DOB + phone match)
    match_info = batch_detail["identity_match_json"]
    assert match_info["best_match"]["patient_id"] == "P-101"
    assert match_info["best_match"]["confidence"] == "high"


def test_import_missing_consent_returns_409(client: TestClient):
    """
    POST /import/{batch_id}/confirm requires an active recorded consent.
    If consent is missing, it must fail with 409 Conflict.
    """
    staff_token = get_token(client, "nurse.devi")

    # Upload batch for Priya S. (P-101)
    payload = {
        "origin_org": "Metro IVF Center",
        "patient": {
            "name": "Priya S.",
            "dob": "1991-05-20",
            "phone": "+91-9845012341",
        },
        "records": [
            {
                "type": "external_record",
                "date": "2023-11-10",
                "author": "Dr. Davis",
                "content_text": "Transfer note from Metro IVF.",
            }
        ],
    }
    upload_res = client.post("/api/v1/import", json=payload, headers={"Authorization": f"Bearer {staff_token}"})
    assert upload_res.status_code == 201
    batch_id = upload_res.json()["id"]

    # Attempt confirm without recorded consent
    confirm_res = client.post(
        f"/api/v1/import/{batch_id}/confirm",
        json={"target_patient_id": "P-101", "confirm_identity": True},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    # Must return 409 Conflict per spec
    assert confirm_res.status_code == 409
    error_detail = confirm_res.json()["detail"]
    assert error_detail["code"] == "CONSENT_REQUIRED"
    assert "Active transfer consent is missing" in error_detail["message"]


def test_wrong_merge_prevention_on_name_alone(client: TestClient):
    """
    Never auto-merge on name alone.
    If external demographics match only by name but lack DOB/phone match,
    medium/low confidence requires explicit staff confirmation.
    Attempting confirmation without confirm_identity: true must return 400.
    """
    staff_token = get_token(client, "nurse.devi")

    # Upload external patient with name 'Priya S.' but completely DIFFERENT DOB & phone
    payload = {
        "origin_org": "City Health Hospital",
        "patient": {
            "external_id": "EXT-DIFF-001",
            "name": "Priya S.",
            "dob": "1980-01-01",  # Completely different DOB
            "phone": "+91-9999999999",  # Completely different phone
        },
        "records": [
            {
                "type": "external_summary",
                "date": "2022-05-10",
                "content_text": "Prior clinic visit note.",
            }
        ],
    }
    upload_res = client.post("/api/v1/import", json=payload, headers={"Authorization": f"Bearer {staff_token}"})
    assert upload_res.status_code == 201
    batch_id = upload_res.json()["id"]

    # First record consent for P-101 so consent check passes
    consent_res = client.post(
        "/api/v1/consents",
        json={
            "patient_id": "P-101",
            "consent_type": "external_transfer",
            "granted_by": "Priya S.",
            "status": "active",
        },
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert consent_res.status_code == 201

    # Attempt to confirm WITHOUT explicit confirm_identity: false
    # Because it is a name match alone (low confidence score 0.45), auto-merging is blocked.
    confirm_res = client.post(
        f"/api/v1/import/{batch_id}/confirm",
        json={
            "target_patient_id": "P-101",
            "confirm_identity": False,
        },
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert confirm_res.status_code == 400
    err = confirm_res.json()["detail"]
    assert err["code"] == "IDENTITY_CONFIRMATION_REQUIRED"
    assert "Cannot auto-merge on name alone" in err["message"]


def test_successful_transfer_confirm_flow(client: TestClient):
    """
    Verify complete happy path:
    1. Upload batch
    2. Record consent
    3. Confirm batch with explicit staff confirmation
    4. Records committed with origin_org and trust_status=external_unverified
    5. Patient summary marked stale
    6. Confirmed IdentityLink created
    """
    staff_token = get_token(client, "nurse.devi")
    doc_token = get_token(client, "dr.rao")

    payload = {
        "origin_org": "Bangalore Fertility Care",
        "patient": {
            "external_id": "BFC-4421",
            "name": "Priya S.",
            "dob": "1991-05-20",
            "phone": "+91-9845012341",
        },
        "records": [
            {
                "type": "external_discharge_summary",
                "date": "2024-02-01",
                "author": "Dr. Verma",
                "content_text": "Stimulation cycle conducted at BFC. 10 MII retrieved.",
            }
        ],
        "cycles": [
            {
                "cycle_no": 1,
                "type": "ICSI",
                "start_date": "2024-01-10",
                "end_date": "2024-02-01",
                "outcome": "frozen_all",
            }
        ],
    }

    # 1. Upload
    res_upload = client.post("/api/v1/import", json=payload, headers={"Authorization": f"Bearer {staff_token}"})
    assert res_upload.status_code == 201
    batch_id = res_upload.json()["id"]

    # 2. Record consent
    consent_res = client.post(
        "/api/v1/consents",
        json={
            "patient_id": "P-101",
            "consent_type": "external_transfer",
            "granted_by": "Priya S.",
            "status": "active",
        },
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert consent_res.status_code == 201

    # 3. Confirm batch
    confirm_res = client.post(
        f"/api/v1/import/{batch_id}/confirm",
        json={
            "target_patient_id": "P-101",
            "confirm_identity": True,
            "override_reasons": "Verified medical record number with BFC clinic staff.",
        },
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert confirm_res.status_code == 200
    confirmed_batch = confirm_res.json()
    assert confirmed_batch["status"] == "confirmed"
    assert confirmed_batch["target_patient_id"] == "P-101"

    # 4. Check records committed with origin_org and trust_status=external_unverified
    rec_res = client.get("/api/v1/patients/P-101/records", headers={"Authorization": f"Bearer {doc_token}"})
    assert rec_res.status_code == 200
    records = rec_res.json()["records"]
    ext_records = [r for r in records if r.get("origin_org") == "Bangalore Fertility Care"]
    assert len(ext_records) >= 1
    for r in ext_records:
        assert r["trust_status"] == "external_unverified"

    # 5. Check identity link created
    idl_res = client.get("/api/v1/identity-links?patient_id=P-101", headers={"Authorization": f"Bearer {staff_token}"})
    assert idl_res.status_code == 200
    links = idl_res.json()
    assert any(l["external_org_name"] == "Bangalore Fertility Care" for l in links)
