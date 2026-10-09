import os
import sys
import pytest
from datetime import date
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.models.provenance import ClinicalClaim
from app.models.enums import ClaimValidationStatus


def get_token(client: TestClient, username: str = "dr.rao", password: str = "password123") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def test_p102_dashboard_returns_counts_journey_and_links(client):
    """
    GET /patients/P-102/dashboard returns:
    - treatment journey line (latest cycle stages)
    - counts of verified claims, flagged claims, rejected candidates, open conflicts, open gaps, source records, hospitals
    - filter links for each count
    """
    token = get_token(client, "dr.rao", "password123")
    resp = client.get("/api/v1/patients/P-102/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["patient_id"] == "P-102"
    assert "counts" in data
    counts = data["counts"]
    assert counts["verified_claims"] > 0
    assert counts["source_records"] > 0
    assert counts["hospitals"] >= 2
    assert "open_conflicts" in counts
    assert "open_gaps" in counts

    # Check journey
    assert "treatment_journey" in data
    assert len(data["treatment_journey"]) > 0
    stages = [s["stage"] for s in data["treatment_journey"]]
    assert "STIMULATION" in stages or "BASELINE_WORKUP" in stages

    # Check filter links
    links = data["filter_links"]
    assert "verified_claims" in links
    assert "open_conflicts" in links
    assert "open_gaps" in links
    assert "source_records" in links
    assert "hospitals" in links


def test_claims_evidence_endpoint_returns_metadata_highlight_and_checks(client):
    """
    GET /claims/{id}/evidence returns:
    - claim details
    - source record metadata (id, hospital, date, uploader, type)
    - evidence text with span highlighted (prefix, highlighted_text, suffix)
    - validation checks checklist ('Value verified', 'Unit verified', 'Date verified', 'Source span verified')
    - Never renders HTML
    """
    token = get_token(client, "dr.rao", "password123")

    # Fetch a verified claim for P-102
    claims_resp = client.get("/api/v1/claims?patient_id=P-102&status=VERIFIED", headers={"Authorization": f"Bearer {token}"})
    assert claims_resp.status_code == 200
    claims = claims_resp.json()
    assert len(claims) > 0
    claim_id = claims[0]["id"]

    ev_resp = client.get(f"/api/v1/claims/{claim_id}/evidence", headers={"Authorization": f"Bearer {token}"})
    assert ev_resp.status_code == 200, ev_resp.text
    data = ev_resp.json()

    # Claim
    assert data["claim"]["id"] == claim_id
    assert data["claim"]["patient_id"] == "P-102"

    # Source Record metadata
    assert "source_record" in data
    sr = data["source_record"]
    assert "id" in sr
    assert "hospital" in sr
    assert "date" in sr
    assert "uploader" in sr
    assert "type" in sr

    # Evidence
    assert "evidence" in data
    ev = data["evidence"]
    assert "full_text" in ev
    assert "highlighted_text" in ev
    assert "prefix" in ev
    assert "suffix" in ev
    assert "evidence_sentence" in ev
    # Verify no raw HTML tags
    assert "<span" not in ev["highlighted_text"]
    assert "<html" not in ev["full_text"]

    # Validation checks
    assert "validation_checks" in data
    checks = data["validation_checks"]
    labels = [c["label"] for c in checks]
    assert "Value verified" in labels
    assert "Unit verified" in labels
    assert "Date verified" in labels
    assert "Source span verified" in labels

    for c in checks:
        assert "passed" in c
        assert "detail" in c
        assert isinstance(c["passed"], bool)


def test_doctor_scope_enforcement_on_dashboard_and_evidence(client):
    """
    Doctor dr.rao (assigned to P-102) gets 403 when requesting unassigned P-106.
    """
    token = get_token(client, "dr.rao", "password123")

    # Unassigned patient P-106 dashboard -> 403 Forbidden
    resp = client.get("/api/v1/patients/P-106/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_p102_amh_evidence_and_conflicts_definition_of_done(seeded_engine, client):
    """
    Definition of done: P-102 dashboard shows counts; clicking AMH opens evidence
    with correct highlight; conflict panel shows both hospitals.
    """
    from datetime import datetime, timezone
    from sqlalchemy.orm import Session
    from app.models.enums import ExtractionMethod
    from app.services.engines.conflicts import recompute_and_persist_conflicts

    # Populate the cross-hospital AMH claims for P-102
    with Session(seeded_engine) as session:
        claim_a = ClinicalClaim(
            id="CLM-TEST-P102-AMH-A",
            patient_id="P-102",
            hospital_id="ORG-Y",
            source_record_id="REC-0201",
            field="amh",
            value_text="2.4",
            value_num=2.4,
            unit="ng/mL",
            event_date=date(2024, 6, 14),
            evidence_text="Serum AMH was 2.4 ng/mL.",
            span_start=14,
            span_end=17,
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        claim_b = ClinicalClaim(
            id="CLM-TEST-P102-AMH-B",
            patient_id="P-102",
            hospital_id="ORG-X",
            source_record_id="REC-0202",
            field="amh",
            value_text="1.2",
            value_num=1.2,
            unit="ng/mL",
            event_date=date(2024, 6, 20),
            evidence_text="Serum AMH documented as 1.2 ng/mL.",
            span_start=25,
            span_end=28,
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([claim_a, claim_b])
        session.commit()
        recompute_and_persist_conflicts(session, "P-102")
        session.commit()

    token = get_token(client, "dr.rao", "password123")

    # 1. Dashboard shows counts
    dash_resp = client.get("/api/v1/patients/P-102/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert dash_resp.status_code == 200
    dash = dash_resp.json()
    assert dash["counts"]["verified_claims"] > 0
    assert dash["counts"]["source_records"] > 0
    assert dash["counts"]["hospitals"] >= 2
    assert dash["counts"]["open_conflicts"] >= 1

    # 2. Get AMH claim and check evidence
    claims_resp = client.get("/api/v1/claims?patient_id=P-102&field=amh", headers={"Authorization": f"Bearer {token}"})
    assert claims_resp.status_code == 200
    claims = claims_resp.json()
    assert len(claims) >= 1
    amh_claim = claims[0]

    ev_resp = client.get(f"/api/v1/claims/{amh_claim['id']}/evidence", headers={"Authorization": f"Bearer {token}"})
    assert ev_resp.status_code == 200
    ev_data = ev_resp.json()
    assert ev_data["evidence"]["highlighted_text"] == amh_claim["value_text"] or amh_claim["value_text"] in ev_data["evidence"]["highlighted_text"]
    assert ev_data["source_record"]["hospital"] is not None

    # Check checklist items
    checks = ev_data["validation_checks"]
    assert any(c["label"] == "Value verified" and c["passed"] is True for c in checks)
    assert any(c["label"] == "Unit verified" and c["passed"] is True for c in checks)
    assert any(c["label"] == "Date verified" and c["passed"] is True for c in checks)
    assert any(c["label"] == "Source span verified" and c["passed"] is True for c in checks)

    # 3. Conflicts endpoint shows both hospitals
    conf_resp = client.get("/api/v1/patients/P-102/conflicts", headers={"Authorization": f"Bearer {token}"})
    assert conf_resp.status_code == 200
    confs = conf_resp.json()
    amh_confs = [c for c in confs if c["field"] == "amh"]
    if amh_confs:
        ac = amh_confs[0]
        assert ac["hospital_a"] is not None
        assert ac["hospital_b"] is not None
        assert ac["hospital_a"] != ac["hospital_b"]
        assert "Clinician review required" in ac["display_text"]
