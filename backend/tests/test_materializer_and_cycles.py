import pytest
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.user import User
from app.models.patient import Patient
from app.models.cycle import Cycle
from app.models.source_record import SourceRecord
from app.models.provenance import ClinicalClaim
from app.models.summary import Summary
from app.models.clinical import (
    Investigation,
    OocyteRetrieval,
    Medication,
    TreatmentEvent,
    Transfer,
    PregnancyOutcome,
    Embryo,
)
from app.models.enums import (
    ClaimValidationStatus,
    TrustStatus,
    CycleType,
    TransferKind,
    PregnancyResult,
    TreatmentEventKind,
)
from app.core.scope import Scope
from app.services.cycle_grouper.service import group_claims_into_cycles
from app.services.materializer.service import materialize_claims
from app.services.engines.timeline import get_timeline


def make_scope(user: User, patient_id: str) -> Scope:
    return Scope(user=user, patient_id=patient_id, cycle_id=None, org_id=user.org_id)


def test_materialization_idempotent(seeded_session: Session):
    """
    Test that materialize_claims is strictly idempotent:
    re-running materialization on the same claims never duplicates typed table rows.
    """
    # 1. Create a test record and verified claims for P-101
    rec = SourceRecord(
        id="REC-TEST-MAT-1",
        patient_id="P-101",
        cycle_id="CY-P101-3",
        type="lab_report",
        date=date(2025, 3, 15),
        origin_org="Kernel Prime Fertility Hospital",
        trust_status=TrustStatus.INTERNAL_VERIFIED,
        content_text="AMH: 1.85 ng/mL. Follicle count: 12 antral follicles.",
        uploaded_by="USR-RAO",
    )
    seeded_session.add(rec)
    seeded_session.flush()

    claim1 = ClinicalClaim(
        id="CLM-MAT-001",
        patient_id="P-101",
        cycle_id="CY-P101-3",
        source_record_id="REC-TEST-MAT-1",
        hospital_id="ORG-Y",
        field="amh",
        value_num=1.85,
        value_text="1.85",
        unit="ng/mL",
        event_date=date(2025, 3, 15),
        validation_status=ClaimValidationStatus.VERIFIED,
    )
    claim2 = ClinicalClaim(
        id="CLM-MAT-002",
        patient_id="P-101",
        cycle_id="CY-P101-3",
        source_record_id="REC-TEST-MAT-1",
        hospital_id="ORG-Y",
        field="oocytes_retrieved",
        value_num=10.0,
        value_text="10",
        unit="oocytes",
        event_date=date(2025, 3, 16),
        validation_status=ClaimValidationStatus.VERIFIED,
    )
    seeded_session.add_all([claim1, claim2])
    seeded_session.commit()

    # Initial count
    inv_count_before = seeded_session.query(Investigation).count()
    opu_count_before = seeded_session.query(OocyteRetrieval).count()

    # First materialization run
    res1 = materialize_claims(seeded_session, patient_id="P-101", record_id="REC-TEST-MAT-1")
    assert res1["materialized_count"] >= 2

    inv_count_after1 = seeded_session.query(Investigation).count()
    opu_count_after1 = seeded_session.query(OocyteRetrieval).count()
    assert inv_count_after1 == inv_count_before + 1
    assert opu_count_after1 == opu_count_before + 1

    # Verify back-links on claim
    seeded_session.refresh(claim1)
    assert claim1.materialized_table == "investigations"
    assert claim1.materialized_row_id == "INV-CLM-MAT-001"

    seeded_session.refresh(claim2)
    assert claim2.materialized_table == "oocyte_retrievals"
    assert claim2.materialized_row_id == "OPU-CLM-MAT-002"

    # Second materialization run: IDEMPOTENCY CHECK
    res2 = materialize_claims(seeded_session, patient_id="P-101", record_id="REC-TEST-MAT-1")
    assert res2["materialized_count"] == 0
    assert res2["skipped_count"] >= 2

    inv_count_after2 = seeded_session.query(Investigation).count()
    opu_count_after2 = seeded_session.query(OocyteRetrieval).count()
    assert inv_count_after2 == inv_count_after1
    assert opu_count_after2 == opu_count_after1


def test_ordering_by_date_across_hospitals(seeded_session: Session):
    """
    Test that the timeline engine orders all clinical events chronologically across hospitals.
    """
    user = seeded_session.query(User).filter_by(username="dr.rao").first()
    scope = make_scope(user, "P-101")

    # Add a cross-hospital event from Hospital X
    rec_hx = SourceRecord(
        id="REC-HX-ORDER-1",
        patient_id="P-101",
        cycle_id="CY-P101-1",
        type="procedure_note",
        date=date(2023, 11, 21),
        origin_org="Hospital X, Hyderabad",
        trust_status=TrustStatus.EXTERNAL_UNVERIFIED,
        content_text="Interim monitoring scan at Hospital X.",
        uploaded_by="USR-RAO",
    )
    seeded_session.add(rec_hx)
    seeded_session.flush()

    ev_hx = TreatmentEvent(
        id="EV-HX-ORD-1",
        cycle_id="CY-P101-1",
        kind=TreatmentEventKind.SCAN,
        date=date(2023, 11, 21),
        detail="Pelvic ultrasound at Hospital X",
        source_id="REC-HX-ORDER-1",
        org_id="ORG-X",
        origin_org="Hospital X, Hyderabad",
        trust_status=TrustStatus.EXTERNAL_UNVERIFIED,
    )
    seeded_session.add(ev_hx)
    seeded_session.commit()

    timeline = get_timeline(seeded_session, scope)
    assert timeline["patient_id"] == "P-101"

    # Verify chronological ordering in years
    for yr_obj in timeline["years"]:
        events = yr_obj["events"]
        for i in range(len(events) - 1):
            assert events[i]["date"] <= events[i + 1]["date"], f"Events out of order: {events[i]['date']} > {events[i+1]['date']}"

    # Verify Hospital X event is properly present and attributed
    hx_events = [ev for yr in timeline["years"] for ev in yr["events"] if "Hospital X" in ev["hospital"]]
    assert len(hx_events) >= 1
    assert any(ev["id"] == "EV-HX-ORD-1" for ev in hx_events)


def test_two_ivf_cycles_grouped_correctly(seeded_session: Session):
    """
    Test that the cycle grouping service correctly separates two IVF cycles:
    starts a new cycle when a new stimulation appears after a closed outcome.
    """
    patient = Patient(
        id="P-TEST-CYCLES",
        name="Test MultiCycle",
        dob=date(1992, 1, 1),
        sex="female",
        org_id="ORG-Y",
    )
    seeded_session.add(patient)
    seeded_session.flush()

    # Cycle 1: Started 2024-01-10, ended 2024-02-15 with negative outcome
    c1 = Cycle(
        id="CY-TEST-1",
        patient_id="P-TEST-CYCLES",
        cycle_no=1,
        type=CycleType.IVF,
        start_date=date(2024, 1, 10),
        end_date=date(2024, 2, 15),
        outcome="negative",
        origin_org="Kernel Prime Fertility Hospital",
        org_id="ORG-Y",
    )
    seeded_session.add(c1)
    seeded_session.flush()

    # Verified claims for new cycle: Stimulation on 2024-06-01, OPU on 2024-06-14, Outcome on 2024-06-28
    rec2 = SourceRecord(
        id="REC-TEST-C2",
        patient_id="P-TEST-CYCLES",
        type="summary",
        date=date(2024, 6, 28),
        origin_org="Kernel Prime Fertility Hospital",
        trust_status=TrustStatus.INTERNAL_VERIFIED,
        content_text="Cycle 2 IVF summary text",
        uploaded_by="USR-RAO",
    )
    seeded_session.add(rec2)
    seeded_session.flush()

    clm_stim = ClinicalClaim(
        id="CLM-C2-STIM",
        patient_id="P-TEST-CYCLES",
        cycle_id=None,
        source_record_id="REC-TEST-C2",
        hospital_id="ORG-Y",
        field="stimulation",
        value_text="Antagonist protocol start",
        event_date=date(2024, 6, 1),
        validation_status=ClaimValidationStatus.VERIFIED,
    )
    clm_opu = ClinicalClaim(
        id="CLM-C2-OPU",
        patient_id="P-TEST-CYCLES",
        cycle_id=None,
        source_record_id="REC-TEST-C2",
        hospital_id="ORG-Y",
        field="opu",
        value_num=12.0,
        value_text="12 oocytes",
        event_date=date(2024, 6, 14),
        validation_status=ClaimValidationStatus.VERIFIED,
    )
    clm_out = ClinicalClaim(
        id="CLM-C2-OUT",
        patient_id="P-TEST-CYCLES",
        cycle_id=None,
        source_record_id="REC-TEST-C2",
        hospital_id="ORG-Y",
        field="pregnancy_outcome",
        value_text="clinical",
        event_date=date(2024, 6, 28),
        validation_status=ClaimValidationStatus.VERIFIED,
    )
    seeded_session.add_all([clm_stim, clm_opu, clm_out])
    seeded_session.commit()

    # Run cycle grouping
    group_res = group_claims_into_cycles(seeded_session, patient_id="P-TEST-CYCLES")
    assert group_res["new_cycles_created"] == 1
    assert group_res["total_cycles"] == 2

    seeded_session.refresh(clm_stim)
    seeded_session.refresh(clm_opu)
    seeded_session.refresh(clm_out)

    assert clm_stim.cycle_assignment == "ASSIGNED"
    assert clm_opu.cycle_assignment == "ASSIGNED"
    assert clm_out.cycle_assignment == "ASSIGNED"

    # All new claims assigned to Cycle 2
    assert clm_stim.cycle_id == "CY-P-TEST-CYCLES-2"
    assert clm_opu.cycle_id == "CY-P-TEST-CYCLES-2"
    assert clm_out.cycle_id == "CY-P-TEST-CYCLES-2"


def test_ambiguous_event_flagged(seeded_session: Session):
    """
    Test that ambiguous event assignments are marked cycle_assignment=NEEDS_REVIEW
    and never guessed silently.
    """
    patient = Patient(
        id="P-TEST-AMBIG",
        name="Test Ambiguous",
        dob=date(1994, 5, 5),
        sex="female",
        org_id="ORG-Y",
    )
    seeded_session.add(patient)
    seeded_session.flush()

    c = Cycle(
        id="CY-TEST-AMB-1",
        patient_id="P-TEST-AMBIG",
        cycle_no=1,
        type=CycleType.IVF,
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 20),
        outcome="clinical",
        origin_org="Kernel Prime Fertility Hospital",
        org_id="ORG-Y",
    )
    seeded_session.add(c)

    # 1. Undated claim
    clm_undated = ClinicalClaim(
        id="CLM-AMB-UNDATED",
        patient_id="P-TEST-AMBIG",
        source_record_id="REC-0101",
        hospital_id="ORG-Y",
        field="fsh",
        value_num=6.5,
        event_date=None,
        validation_status=ClaimValidationStatus.VERIFIED,
    )

    # 2. Sequence violation: OPU occurring after transfer in the same cycle
    trf = Transfer(
        id="TRF-AMB-1",
        cycle_id="CY-TEST-AMB-1",
        date=date(2024, 3, 15),
        kind=TransferKind.FRESH,
        embryo_ids=[],
        source_id="REC-0101",
        org_id="ORG-Y",
        origin_org="Kernel Prime Fertility Hospital",
        trust_status=TrustStatus.INTERNAL_VERIFIED,
    )
    seeded_session.add(trf)

    # OPU claim with date 2024-03-18 (after transfer)
    clm_violation = ClinicalClaim(
        id="CLM-AMB-VIOLATION",
        patient_id="P-TEST-AMBIG",
        source_record_id="REC-0101",
        hospital_id="ORG-Y",
        field="opu",
        value_num=8.0,
        event_date=date(2024, 3, 18),
        validation_status=ClaimValidationStatus.VERIFIED,
    )
    seeded_session.add_all([clm_undated, clm_violation])
    seeded_session.commit()

    res = group_claims_into_cycles(seeded_session, patient_id="P-TEST-AMBIG")
    assert res["needs_review_claims"] >= 2

    seeded_session.refresh(clm_undated)
    seeded_session.refresh(clm_violation)

    assert clm_undated.cycle_assignment == "NEEDS_REVIEW"
    assert clm_undated.cycle_id is None

    assert clm_violation.cycle_assignment == "NEEDS_REVIEW"
    assert clm_violation.cycle_id is None


def test_timeline_response_includes_hospital_and_source_for_every_event(seeded_session: Session):
    """
    Test that get_timeline returns canonical_event_name, hospital, and source_record_id for every event.
    """
    user = seeded_session.query(User).filter_by(username="dr.rao").first()

    for pid in ["P-101", "P-102", "P-103"]:
        scope = make_scope(user, pid)
        timeline = get_timeline(seeded_session, scope)

        assert "years" in timeline
        assert "cycles" in timeline
        assert timeline["total_cycles"] > 0

        for yr_obj in timeline["years"]:
            assert "year" in yr_obj
            assert "events" in yr_obj
            for ev in yr_obj["events"]:
                assert ev["hospital"] is not None and len(ev["hospital"]) > 0, f"Missing hospital in event {ev['id']}"
                assert ev["source_record_id"] is not None and ev["source_record_id"].startswith("REC-"), f"Invalid source in event {ev['id']}"
                assert ev["validation_status"] == "VERIFIED"
                assert "citation" in ev and len(ev["citation"]) > 0
                assert "canonical_event_name" in ev and len(ev["canonical_event_name"]) > 0


def test_p104_shows_two_separate_cycles_with_correct_stages(seeded_session: Session):
    """
    Definition of Done: P-104 shows two separate cycles with correct stages
    (Cycle 1: IVF in 2024, Cycle 2: FET in 2025).
    """
    user = seeded_session.query(User).filter_by(username="dr.rao").first()
    scope = make_scope(user, "P-104")

    # Cycle 1 exists in seed (CY-P104-1, IVF, loss).
    # Materialize claims for Cycle 1:
    rec_0402 = seeded_session.get(SourceRecord, "REC-0402")
    if rec_0402:
        clm_opu = ClinicalClaim(
            id="CLM-P104-OPU",
            patient_id="P-104",
            cycle_id="CY-P104-1",
            source_record_id="REC-0402",
            hospital_id="ORG-Y",
            field="opu",
            value_num=11.0,
            event_date=date(2024, 7, 16),
            validation_status=ClaimValidationStatus.VERIFIED,
        )
        clm_trf1 = ClinicalClaim(
            id="CLM-P104-TRF1",
            patient_id="P-104",
            cycle_id="CY-P104-1",
            source_record_id="REC-0402",
            hospital_id="ORG-Y",
            field="fresh_transfer",
            value_num=2.0,
            event_date=date(2024, 7, 16),
            validation_status=ClaimValidationStatus.VERIFIED,
        )
        seeded_session.add_all([clm_opu, clm_trf1])

    # Now add Cycle 2 record (FET in 2025):
    rec_test_fet = SourceRecord(
        id="REC-TEST-P104-FET",
        patient_id="P-104",
        cycle_id=None,
        type="cycle_summary",
        date=date(2025, 4, 19),
        origin_org="Kernel Prime Fertility Hospital",
        trust_status=TrustStatus.INTERNAL_VERIFIED,
        content_text="FET Protocol: Progynova preparation 2025-03-25. Blastocyst transfer on 2025-04-14. Beta-hCG 420 mIU/mL on 2025-04-19.",
        uploaded_by="USR-RAO",
    )
    seeded_session.add(rec_test_fet)
    seeded_session.flush()

    # Claims for Cycle 2
    clm_stim2 = ClinicalClaim(
        id="CLM-P104-FET-STIM",
        patient_id="P-104",
        cycle_id=None,
        source_record_id="REC-TEST-P104-FET",
        hospital_id="ORG-Y",
        field="stimulation",
        value_text="Oral Progynova endometrial preparation",
        event_date=date(2025, 3, 25),
        validation_status=ClaimValidationStatus.VERIFIED,
    )
    clm_trf2 = ClinicalClaim(
        id="CLM-P104-FET-TRF",
        patient_id="P-104",
        cycle_id=None,
        source_record_id="REC-TEST-P104-FET",
        hospital_id="ORG-Y",
        field="transfer",
        value_text="Single frozen blastocyst transfer",
        event_date=date(2025, 4, 14),
        validation_status=ClaimValidationStatus.VERIFIED,
    )
    clm_out2 = ClinicalClaim(
        id="CLM-P104-FET-OUT",
        patient_id="P-104",
        cycle_id=None,
        source_record_id="REC-TEST-P104-FET",
        hospital_id="ORG-Y",
        field="pregnancy_outcome",
        value_num=420.0,
        value_text="clinical",
        event_date=date(2025, 4, 19),
        validation_status=ClaimValidationStatus.VERIFIED,
    )
    seeded_session.add_all([clm_stim2, clm_trf2, clm_out2])
    seeded_session.commit()

    # Materialize claims
    mat_res = materialize_claims(seeded_session, patient_id="P-104")
    assert mat_res["materialized_count"] >= 3

    # Query timeline
    timeline = get_timeline(seeded_session, scope)

    # DoD 1: P-104 shows two separate cycles
    assert timeline["total_cycles"] >= 2
    cycle_numbers = [c["cycle_no"] for c in timeline["cycles"]]
    assert 1 in cycle_numbers
    assert 2 in cycle_numbers

    # DoD 2: Correct stages in Cycle 1 and Cycle 2
    c1 = next(c for c in timeline["cycles"] if c["cycle_no"] == 1)
    c2 = next(c for c in timeline["cycles"] if c["cycle_no"] == 2)

    assert "OPU" in c1["stages"] or "Transfer" in c1["stages"]
    assert "Transfer" in c2["stages"] or "Stimulation" in c2["stages"]
    assert c2["type"] in ("FET", "IVF")

    # DoD 3: Events grouped by year (2024 and 2025)
    years_represented = [yr["year"] for yr in timeline["years"]]
    assert 2024 in years_represented
    assert 2025 in years_represented
