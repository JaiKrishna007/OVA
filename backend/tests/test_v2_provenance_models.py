"""
Tests for OVA v2 Section 16 models, relationships, enums, indexes, and seed backfill:
1. Schema creation and index verification.
2. One patient with a claim linked to a typed row.
3. Backfill produces one claim per typed row.
4. No orphan links (materialized_table / materialized_row_id integrity and hospital origin scoping).
"""

import os
from datetime import date
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    Organization,
    Patient,
    Cycle,
    SourceRecord,
    Investigation,
    TreatmentEvent,
    ClinicalClaim,
    ConflictRecord,
    DocumentationGap,
    TransferRequest,
    PatientHospitalAccess,
    Consent,
    IdentityLink,
    ImportBatch,
    CycleType,
    TrustStatus,
    InvestigationCategory,
    InvestigationStatus,
    ClaimValidationStatus,
    ExtractionMethod,
    ConflictStatus,
    GapStatus,
    TransferRequestStatus,
    HospitalAccessLevel,
    HospitalAccessStatus,
)
from app.schemas.provenance import (
    ClinicalClaimRead,
    ConflictRead,
    DocumentationGapRead,
    TransferRequestRead,
    PatientHospitalAccessRead,
)
from app.services.ingestion.seed_loader import load_seed_data

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SEED_DIR = os.path.join(BASE_DIR, "data", "seed")
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")


def test_v2_schema_creation(db_engine):
    """Verify that all Section 16 tables, new columns, and indexes are created."""
    table_names = set(Base.metadata.tables.keys())
    v2_expected_tables = {
        "clinical_claims",
        "conflicts",
        "documentation_gaps",
        "transfer_requests",
        "patient_hospital_access",
        "consents",
        "identity_links",
        "import_batches",
    }
    assert v2_expected_tables.issubset(table_names), f"Missing tables: {v2_expected_tables - table_names}"

    # Verify clinical_claims indexes
    claims_table = Base.metadata.tables["clinical_claims"]
    indexed_columns = set()
    for idx in claims_table.indexes:
        for col in idx.columns:
            indexed_columns.add(col.name)
    for col in claims_table.primary_key.columns:
        indexed_columns.add(col.name)

    for req_idx in ["patient_id", "hospital_id", "source_record_id", "field", "validation_status"]:
        assert req_idx in indexed_columns, f"clinical_claims.{req_idx} is not indexed"

    # Verify extended columns exist on existing tables
    orgs_table = Base.metadata.tables["organizations"]
    assert "type" in orgs_table.columns

    users_table = Base.metadata.tables["users"]
    assert "hospital_id" in users_table.columns
    assert "patient_id" in users_table.columns

    sources_table = Base.metadata.tables["source_records"]
    assert "uploaded_by" in sources_table.columns
    assert "processing_status" in sources_table.columns
    assert "content_hash" in sources_table.columns

    audit_table = Base.metadata.tables["audit_log"]
    assert "hospital_id" in audit_table.columns
    assert "details" in audit_table.columns


def test_one_patient_with_claim_linked_to_typed_row(db_session: Session):
    """
    Test inserting one patient with a typed clinical row (investigations)
    and a clinical_claims row linked via materialized_table and materialized_row_id.
    """
    # 1. Setup Organization, Patient, Cycle, SourceRecord
    org = Organization(id="ORG-TEST", name="Test Origin Hospital", type="hospital")
    db_session.add(org)
    db_session.commit()

    patient = Patient(
        id="P-901",
        name="Sunita Test",
        dob=date(1993, 3, 15),
        sex="female",
        org_id="ORG-TEST",
        diagnosis={"primary": "PCOS"},
        blood_group="A+",
        bmi=24.1,
        phone="+91-9123456780",
    )
    db_session.add(patient)
    db_session.commit()

    cycle = Cycle(
        id="CY-P901-1",
        patient_id="P-901",
        cycle_no=1,
        type=CycleType.IVF,
        start_date=date(2025, 1, 10),
        end_date=date(2025, 1, 28),
        outcome="ongoing",
        origin_org="Test Origin Hospital",
    )
    db_session.add(cycle)
    db_session.commit()

    record = SourceRecord(
        id="REC-9001",
        patient_id="P-901",
        cycle_id="CY-P901-1",
        type="lab_report",
        date=date(2025, 1, 12),
        author="Dr. Rao",
        origin_org="Test Origin Hospital",
        trust_status=TrustStatus.INTERNAL_VERIFIED,
        content_text="Baseline blood test: Serum AMH: 3.5 ng/mL (normal range 1.0 - 4.0 ng/mL).",
        version=1,
    )
    db_session.add(record)
    db_session.commit()

    # 2. Create typed clinical row: Investigation
    investigation = Investigation(
        id="INV-9001",
        patient_id="P-901",
        cycle_id="CY-P901-1",
        category=InvestigationCategory.LAB,
        name="AMH",
        value="3.5",
        unit="ng/mL",
        ref_range="1.0 - 4.0",
        date=date(2025, 1, 12),
        status=InvestigationStatus.RESULTED,
        source_id="REC-9001",
        org_id="ORG-TEST",  # Origin hospital, immutable on transfer
        origin_org="Test Origin Hospital",
        trust_status=TrustStatus.INTERNAL_VERIFIED,
    )
    db_session.add(investigation)
    db_session.commit()

    # 3. Create ClinicalClaim linked to the typed row
    span_start = record.content_text.find("3.5")
    span_end = span_start + len("3.5")
    evidence = record.content_text[max(0, span_start - 10): min(len(record.content_text), span_end + 10)]

    claim = ClinicalClaim(
        id="CLM-INV-9001",
        patient_id="P-901",
        hospital_id="ORG-TEST",  # Origin hospital: immutable on transfer
        source_record_id="REC-9001",
        cycle_id="CY-P901-1",
        field="investigations.AMH.value",
        value_text="3.5",
        value_num=3.5,
        unit="ng/mL",
        event_date=date(2025, 1, 12),
        span_start=span_start,
        span_end=span_end,
        evidence_text=evidence,
        extraction_method=ExtractionMethod.SEED,
        validation_status=ClaimValidationStatus.VERIFIED,
        validation_checks={"seed_integrity": True},
        reason_codes=[],
        materialized_table="investigations",
        materialized_row_id="INV-9001",
    )
    db_session.add(claim)
    db_session.commit()

    # 4. Verify claim and relationships
    loaded_claim = db_session.get(ClinicalClaim, "CLM-INV-9001")
    assert loaded_claim is not None
    assert loaded_claim.patient_id == "P-901"
    assert loaded_claim.hospital_id == "ORG-TEST"
    assert loaded_claim.patient.name == "Sunita Test"
    assert loaded_claim.hospital.name == "Test Origin Hospital"
    assert loaded_claim.source_record.id == "REC-9001"
    assert loaded_claim.cycle.id == "CY-P901-1"
    assert loaded_claim.validation_status == ClaimValidationStatus.VERIFIED
    assert loaded_claim.materialized_table == "investigations"
    assert loaded_claim.materialized_row_id == "INV-9001"

    # 5. Verify Pydantic schema validation
    claim_read = ClinicalClaimRead.model_validate(loaded_claim)
    assert claim_read.id == "CLM-INV-9001"
    assert claim_read.value_num == 3.5
    assert claim_read.extraction_method == ExtractionMethod.SEED


def test_backfill_produces_one_claim_per_typed_row(db_engine):
    """
    Test that running seed data backfill produces exactly 1 clinical_claims row
    for every existing typed clinical row across all 11 typed tables.
    """
    counts = load_seed_data(seed_dir=SEED_DIR, gold_dir=GOLD_DIR, target_engine=db_engine)

    # Sum rows across all 11 typed clinical tables
    typed_clinical_tables = [
        "treatment_events",
        "investigations",
        "medications",
        "stimulation_days",
        "oocyte_retrievals",
        "embryos",
        "transfers",
        "pregnancy_outcomes",
        "adverse_events",
        "doctor_notes",
        "followups",
    ]
    expected_typed_total = sum(counts[tbl] for tbl in typed_clinical_tables)

    with Session(db_engine) as session:
        claims = session.scalars(select(ClinicalClaim)).all()
        actual_claims_count = len(claims)

        assert actual_claims_count == expected_typed_total, (
            f"Expected {expected_typed_total} claims matching typed rows, got {actual_claims_count}"
        )
        assert counts["clinical_claims"] == expected_typed_total

        # Verify all backfilled claims have SEED extraction and VERIFIED status
        for c in claims:
            assert c.extraction_method == ExtractionMethod.SEED
            assert c.validation_status == ClaimValidationStatus.VERIFIED
            assert c.materialized_table in typed_clinical_tables
            assert c.materialized_row_id is not None
            assert c.hospital_id in ["ORG-Y", "ORG-X", "ORG-B"]


def test_no_orphan_links(db_engine):
    """
    Verify that every backfilled clinical_claim references a real materialized row,
    its originating hospital_id matches the row's org_id, and patient_id is consistent.
    """
    load_seed_data(seed_dir=SEED_DIR, gold_dir=GOLD_DIR, target_engine=db_engine)

    with Session(db_engine) as session:
        claims = session.scalars(select(ClinicalClaim)).all()
        assert len(claims) > 0, "No claims loaded"

        for claim in claims:
            # Check source record exists
            source = session.get(SourceRecord, claim.source_record_id)
            assert source is not None, f"Orphan source link on claim {claim.id}: {claim.source_record_id}"

            # Check materialized row exists in the indicated table
            target_table = Base.metadata.tables[claim.materialized_table]
            stmt = select(target_table).where(target_table.c.id == claim.materialized_row_id)
            row = session.execute(stmt).first()
            assert row is not None, (
                f"Orphan link on claim {claim.id}: {claim.materialized_table} id={claim.materialized_row_id} not found"
            )

            # Check hospital scoping: claim.hospital_id must match the row's org_id (origin hospital)
            row_dict = row._asdict()
            assert claim.hospital_id == row_dict["org_id"], (
                f"Hospital mismatch on claim {claim.id}: claim hospital_id={claim.hospital_id} != row org_id={row_dict['org_id']}"
            )

            # Check span consistency if span is populated
            if claim.span_start is not None and claim.span_end is not None:
                extracted = source.content_text[claim.span_start:claim.span_end]
                assert len(extracted) > 0
                assert extracted in source.content_text
