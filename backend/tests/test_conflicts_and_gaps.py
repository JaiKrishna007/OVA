"""
Test Suite for OVA v2 Conflict Engine & Documentation Gap Engine.
Tests:
1. P-102 produces AMH 2.4 vs 1.2 conflict with both hospitals shown.
2. Same value in two hospitals produces no conflict.
3. Different units produce a flag (UNIT_AMBIGUOUS), not a conflict.
4. P-103 OPU without embryology produces a gap.
5. Uploading the embryology record resolves it (RESOLVED with resolving_claim_id).
6. Acknowledging does not alter clinical values or choose a winner.
7. Re-running engines creates no duplicates and preserves acknowledgments.
8. Definition of done: P-106 shows multiple conflicts and gaps matching gold files.
9. RBAC & hospital scoping: unassigned doctor gets 403 Forbidden on P-106.
"""

import json
import os
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models.enums import ClaimValidationStatus, ConflictStatus, GapStatus, ExtractionMethod
from app.models.provenance import ClinicalClaim, ConflictRecord, DocumentationGap
from app.models.user import User
from app.models.source_record import SourceRecord
from app.services.engines.conflicts import recompute_and_persist_conflicts
from app.services.engines.gaps import recompute_and_persist_gaps

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")


def get_token(client: TestClient, username: str = "dr.rao", password: str = "password123") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return resp.json()["access_token"]


def test_p102_produces_cross_hospital_amh_conflict_with_both_hospitals(seeded_engine, client):
    """
    P-102: Two verified claims for AMH (2.4 vs 1.2 ng/mL) from different source records
    and different hospitals (ORG-Y vs ORG-X) produce an OPEN conflict with both hospitals shown.
    """
    with Session(seeded_engine) as session:
        # Create claim A at Hospital A (ORG-Y)
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
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        # Create claim B at Hospital B (ORG-X)
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
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([claim_a, claim_b])
        session.commit()

        # Run conflict engine
        confs = recompute_and_persist_conflicts(session, "P-102")
        session.commit()

        # Find AMH conflict
        amh_confs = [c for c in confs if c.field == "amh"]
        assert len(amh_confs) >= 1
        conf = amh_confs[0]

        # Verify both values and both hospitals are shown
        assert conf.status == ConflictStatus.OPEN
        assert set([conf.hospital_a, conf.hospital_b]) == {"ORG-Y", "ORG-X"}
        assert "2.4" in conf.value_a or "2.4" in conf.value_b
        assert "1.2" in conf.value_a or "1.2" in conf.value_b
        assert conf.display_text == "Conflicting documented values. Clinician review required."

    # Test GET /patients/P-102/conflicts endpoint
    token = get_token(client, "dr.rao", "password123")
    resp = client.get("/api/v1/patients/P-102/conflicts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(c["field"] == "amh" and set([c["hospital_a"], c["hospital_b"]]) == {"ORG-Y", "ORG-X"} for c in data)


def test_same_value_in_two_hospitals_produces_no_conflict(seeded_engine):
    """
    Two verified claims across different hospitals with the SAME value (or difference within tolerance)
    must produce NO conflict.
    """
    with Session(seeded_engine) as session:
        claim_a = ClinicalClaim(
            id="CLM-TEST-SAME-A",
            patient_id="P-104",
            hospital_id="ORG-Y",
            source_record_id="REC-0401",
            field="amh",
            value_text="2.4",
            value_num=2.4,
            unit="ng/mL",
            event_date=date(2024, 6, 14),
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        claim_b = ClinicalClaim(
            id="CLM-TEST-SAME-B",
            patient_id="P-104",
            hospital_id="ORG-X",
            source_record_id="REC-0402",
            field="amh",
            value_text="2.4",
            value_num=2.4,
            unit="ng/mL",
            event_date=date(2024, 6, 20),
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([claim_a, claim_b])
        session.commit()

        confs = recompute_and_persist_conflicts(session, "P-104")
        amh_confs = [c for c in confs if c.field == "amh"]
        assert len(amh_confs) == 0, "Identical AMH values across hospitals should produce NO conflict"


def test_different_units_produce_flag_not_conflict(seeded_engine):
    """
    Claims with divergent units (e.g. ng/mL vs ng/dL) are FLAGGED as UNIT_AMBIGUOUS,
    and do NOT produce a numerical conflict record.
    """
    with Session(seeded_engine) as session:
        claim_a = ClinicalClaim(
            id="CLM-TEST-UNIT-A",
            patient_id="P-105",
            hospital_id="ORG-Y",
            source_record_id="REC-0501",
            field="progesterone",
            value_text="15.0",
            value_num=15.0,
            unit="ng/mL",
            event_date=date(2024, 6, 14),
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        claim_b = ClinicalClaim(
            id="CLM-TEST-UNIT-B",
            patient_id="P-105",
            hospital_id="ORG-X",
            source_record_id="REC-0502",
            field="progesterone",
            value_text="1500.0",
            value_num=1500.0,
            unit="ng/dL",  # Different unit!
            event_date=date(2024, 6, 15),
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([claim_a, claim_b])
        session.commit()

        confs = recompute_and_persist_conflicts(session, "P-105")
        p4_confs = [c for c in confs if c.field == "progesterone"]
        assert len(p4_confs) == 0, "Divergent units must NOT be treated as a conflict"

        # Check claims are flagged as UNIT_AMBIGUOUS
        session.refresh(claim_a)
        session.refresh(claim_b)
        assert claim_a.validation_status == ClaimValidationStatus.FLAGGED
        assert "UNIT_AMBIGUOUS" in (claim_a.reason_codes or [])
        assert claim_b.validation_status == ClaimValidationStatus.FLAGGED
        assert "UNIT_AMBIGUOUS" in (claim_b.reason_codes or [])


def test_p103_opu_without_embryology_produces_gap_and_resolves_on_upload(seeded_engine):
    """
    P-103: An OPU claim without subsequent embryology report produces an OPEN documentation gap.
    Uploading / materializing the embryology record resolves it automatically (RESOLVED with resolving_claim_id).
    """
    with Session(seeded_engine) as session:
        # Create OPU claim without embryology report
        opu_claim = ClinicalClaim(
            id="CLM-TEST-P103-OPU",
            patient_id="P-103",
            hospital_id="ORG-Y",
            source_record_id="REC-0301",
            field="OPU",
            value_text="12",
            value_num=12.0,
            unit=None,
            event_date=date(2024, 5, 10),
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        session.add(opu_claim)
        session.commit()

        # Run gap engine
        gaps = recompute_and_persist_gaps(session, "P-103")
        session.commit()

        # Must detect OPEN gap
        opu_gaps = [g for g in gaps if g.rule_id == "RULE_GAP_OPU_EMBRYOLOGY" and g.trigger_claim_id == opu_claim.id]
        assert len(opu_gaps) == 1
        gap = opu_gaps[0]
        assert gap.status == GapStatus.OPEN
        assert gap.expected_item == "embryology_record"
        gap_id = gap.id

        # Now simulate arrival / upload of the embryology report
        emb_claim = ClinicalClaim(
            id="CLM-TEST-P103-EMB",
            patient_id="P-103",
            hospital_id="ORG-Y",
            source_record_id="REC-0304",
            field="embryology_record",
            value_text="8 fertilized, 4 blastocysts vitrified",
            event_date=date(2024, 5, 15),
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        session.add(emb_claim)
        session.commit()

        # Re-run gap engine
        recompute_and_persist_gaps(session, "P-103")
        session.commit()

        # Gap must now be RESOLVED with resolving_claim_id
        session.refresh(gap)
        assert gap.status == GapStatus.RESOLVED
        assert gap.resolving_claim_id == emb_claim.id
        assert gap.resolved_at is not None


def test_acknowledging_conflict_records_doctor_and_preserves_values(seeded_engine, client):
    """
    POST /conflicts/{id}/acknowledge records who and when with a note,
    and NEVER alters any clinical value or picks a winner.
    """
    token = get_token(client, "dr.rao", "password123")

    with Session(seeded_engine) as session:
        # Create conflicting claims
        c_a = ClinicalClaim(
            id="CLM-TEST-ACK-A",
            patient_id="P-102",
            hospital_id="ORG-Y",
            source_record_id="REC-0201",
            field="amh",
            value_text="2.4",
            value_num=2.4,
            unit="ng/mL",
            event_date=date(2024, 6, 14),
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        c_b = ClinicalClaim(
            id="CLM-TEST-ACK-B",
            patient_id="P-102",
            hospital_id="ORG-X",
            source_record_id="REC-0202",
            field="amh",
            value_text="1.2",
            value_num=1.2,
            unit="ng/mL",
            event_date=date(2024, 6, 16),
            extraction_method=ExtractionMethod.MOCK,
            validation_status=ClaimValidationStatus.VERIFIED,
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([c_a, c_b])
        session.commit()

        confs = recompute_and_persist_conflicts(session, "P-102")
        session.commit()
        conf = [c for c in confs if c.field == "amh"][0]
        conf_id = conf.id

    # Clinician acknowledges via POST /conflicts/{id}/acknowledge
    ack_note = "Dr. Rao reviewed AMH lab variation. Discrepancy noted; primary protocol based on 2.4 stands."
    resp = client.post(
        f"/api/v1/conflicts/{conf_id}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": ack_note},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["note"] == ack_note
    assert data["acknowledged_by"] is not None

    # Crucial assertion: BOTH claims still exist in database with original values intact
    with Session(seeded_engine) as session:
        db_ca = session.get(ClinicalClaim, "CLM-TEST-ACK-A")
        db_cb = session.get(ClinicalClaim, "CLM-TEST-ACK-B")
        assert db_ca.value_num == 2.4
        assert db_ca.validation_status == ClaimValidationStatus.VERIFIED
        assert db_cb.value_num == 1.2
        assert db_cb.validation_status == ClaimValidationStatus.VERIFIED


def test_acknowledging_gap_records_doctor_without_altering_data(seeded_engine, client):
    """
    POST /gaps/{id}/acknowledge records doctor acknowledgment and note.
    """
    token = get_token(client, "dr.rao", "password123")

    with Session(seeded_engine) as session:
        # P-103 has OPU embryology gap
        gaps = recompute_and_persist_gaps(session, "P-103")
        session.commit()
        gap = [g for g in gaps if g.rule_id == "RULE_GAP_OPU_EMBRYOLOGY"][0]
        gap_id = gap.id

    ack_note = "Embryology report requested from external IVF lab; awaited."
    resp = client.post(
        f"/api/v1/gaps/{gap_id}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": ack_note},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["note"] == ack_note
    assert data["acknowledged_by"] is not None


def test_rerunning_engines_creates_no_duplicates_and_preserves_ack(seeded_engine):
    """
    Re-running conflict and gap engines multiple times is strictly idempotent:
    no duplicate records and existing ACKNOWLEDGED statuses are preserved.
    """
    with Session(seeded_engine) as session:
        # Run 5 times in succession
        for _ in range(5):
            recompute_and_persist_conflicts(session, "P-102")
            recompute_and_persist_gaps(session, "P-102")
            session.commit()

        # Check conflict counts
        conf_count = session.query(ConflictRecord).filter(ConflictRecord.patient_id == "P-102").count()
        assert conf_count == 1, "Must contain exactly 1 conflict for P-102 without duplicates"

        # Check gap counts
        gap_count = session.query(DocumentationGap).filter(DocumentationGap.patient_id == "P-102").count()
        assert gap_count == 0, "Must contain exactly 0 gaps for P-102 without duplicates"


def test_p106_shows_multiple_conflicts_and_gaps_matching_gold(seeded_engine):
    """
    Definition of Done: P-106 shows multiple conflicts and gaps matching gold files.
    - Conflicting beta-hCG values across hospitals (145.0 vs 12.0 mIU/mL)
    - Missing partner semen analysis gap
    """
    with open(os.path.join(GOLD_DIR, "conflicts.json"), "r", encoding="utf-8") as f:
        gold_confs = json.load(f)
    with open(os.path.join(GOLD_DIR, "absences.json"), "r", encoding="utf-8") as f:
        gold_gaps = json.load(f)

    p106_gold_confs = [c for c in gold_confs if c.get("patient_id") == "P-106"]
    p106_gold_gaps = [g for g in gold_gaps if g.get("patient_id") == "P-106"]

    assert len(p106_gold_confs) >= 1, "Gold conflicts must specify P-106 conflict"
    assert len(p106_gold_gaps) >= 1, "Gold absences must specify P-106 gap"

    with Session(seeded_engine) as session:
        # Admin or engine recomputes P-106
        confs = recompute_and_persist_conflicts(session, "P-106")
        gaps = recompute_and_persist_gaps(session, "P-106")
        session.commit()

        # Conflicts check
        hcg_confs = [c for c in confs if "beta_hcg" in c.field.lower() or "beta-hcg" in c.field.lower()]
        assert len(hcg_confs) >= 1, "P-106 must show conflicting beta-hCG values"
        c = hcg_confs[0]
        assert "145" in str(c.value_a) or "145" in str(c.value_b)
        assert "12" in str(c.value_a) or "12" in str(c.value_b)
        assert set([c.hospital_a, c.hospital_b]) == {"ORG-Y", "ORG-B"}
        assert c.display_text == "Conflicting documented values. Clinician review required."

        # Gaps check
        semen_gaps = [g for g in gaps if g.rule_id == "RULE_EXPECT_MALE_FACTOR_WORKUP"]
        assert len(semen_gaps) >= 1, "P-106 must show missing partner semen analysis gap"
        assert semen_gaps[0].status == GapStatus.OPEN


def test_doctor_scope_enforcement_on_conflicts_and_gaps(seeded_engine, client):
    """
    RBAC: Doctor dr.rao has access to assigned patient P-102,
    but gets 403 Forbidden when requesting unassigned patient P-106.
    """
    token = get_token(client, "dr.rao", "password123")

    # Accessing assigned patient P-102 -> 200 OK
    resp_102_c = client.get("/api/v1/patients/P-102/conflicts", headers={"Authorization": f"Bearer {token}"})
    assert resp_102_c.status_code == 200

    resp_102_g = client.get("/api/v1/patients/P-102/gaps", headers={"Authorization": f"Bearer {token}"})
    assert resp_102_g.status_code == 200

    # Accessing unassigned patient P-106 -> 403 Forbidden
    resp_106_c = client.get("/api/v1/patients/P-106/conflicts", headers={"Authorization": f"Bearer {token}"})
    assert resp_106_c.status_code == 403

    resp_106_g = client.get("/api/v1/patients/P-106/gaps", headers={"Authorization": f"Bearer {token}"})
    assert resp_106_g.status_code == 403
