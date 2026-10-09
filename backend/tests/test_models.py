from datetime import date
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Organization,
    Patient,
    Cycle,
    SourceRecord,
    OocyteRetrieval,
    CycleType,
    TrustStatus,
)
from app.schemas import (
    PatientRead,
    CycleRead,
    SourceRecordRead,
    OocyteRetrievalRead,
)


def test_schema_created_successfully(db_engine):
    """Test that all tables from the spec are created."""
    from app.db.base import Base

    table_names = set(Base.metadata.tables.keys())
    expected_tables = {
        "organizations",
        "users",
        "doctor_patients",
        "patients",
        "cycles",
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
        "source_records",
        "summaries",
        "summary_feedback",
        "eval_runs",
        "audit_log",
    }
    assert expected_tables.issubset(table_names)


def test_insert_patient_cycle_opu_linked_to_source_record(db_session: Session):
    """
    Test creating the schema and inserting one patient with one cycle
    and one OPU (oocyte retrieval) row linked to a source record.
    """
    # 1. Create Organization
    org = Organization(id="ORG-Y", name="Kernel Prime Fertility")
    db_session.add(org)
    db_session.commit()

    # 2. Create Patient
    patient = Patient(
        id="P-101",
        name="Priya S.",
        dob=date(1991, 5, 20),
        sex="female",
        org_id="ORG-Y",
        diagnosis={"primary": "Diminished ovarian reserve"},
        blood_group="B+",
        bmi=22.4,
        phone="+91-9876543210",
    )
    db_session.add(patient)
    db_session.commit()

    # 3. Create Cycle
    cycle = Cycle(
        id="CY-P101-2",
        patient_id="P-101",
        cycle_no=2,
        type=CycleType.IVF,
        start_date=date(2024, 6, 1),
        end_date=date(2024, 6, 20),
        outcome="biochemical",
        origin_org="Kernel Prime Fertility",
        external_cycle_no=None,
    )
    db_session.add(cycle)
    db_session.commit()

    # 4. Create SourceRecord
    record = SourceRecord(
        id="REC-0051",
        patient_id="P-101",
        cycle_id="CY-P101-2",
        type="opu_report",
        date=date(2024, 6, 12),
        author="Dr. Rao",
        origin_org="Kernel Prime Fertility",
        trust_status=TrustStatus.INTERNAL_VERIFIED,
        content_text="OPU performed under GA. 9 oocytes retrieved: 7 MII, 1 MI, 1 GV.",
        version=1,
    )
    db_session.add(record)
    db_session.commit()

    # 5. Create OocyteRetrieval linked to SourceRecord and Cycle
    opu = OocyteRetrieval(
        id="OPU-P101-2",
        cycle_id="CY-P101-2",
        date=date(2024, 6, 12),
        oocytes_retrieved=9,
        mii=7,
        mi=1,
        gv=1,
        source_id="REC-0051",
        org_id="ORG-Y",
        origin_org="Kernel Prime Fertility",
        trust_status=TrustStatus.INTERNAL_VERIFIED,
    )
    db_session.add(opu)
    db_session.commit()

    # Query and verify
    stmt = select(OocyteRetrieval).where(OocyteRetrieval.id == "OPU-P101-2")
    loaded_opu = db_session.scalar(stmt)

    assert loaded_opu is not None
    assert loaded_opu.oocytes_retrieved == 9
    assert loaded_opu.source_id == "REC-0051"
    assert loaded_opu.cycle_id == "CY-P101-2"
    assert loaded_opu.org_id == "ORG-Y"
    assert loaded_opu.trust_status == TrustStatus.INTERNAL_VERIFIED

    # Check relationships
    assert loaded_opu.source_record.id == "REC-0051"
    assert loaded_opu.source_record.content_text.startswith("OPU performed")
    assert loaded_opu.cycle.id == "CY-P101-2"
    assert loaded_opu.cycle.patient.id == "P-101"
    assert loaded_opu.cycle.patient.name == "Priya S."

    # Validate against Pydantic read schemas
    patient_schema = PatientRead.model_validate(loaded_opu.cycle.patient)
    assert patient_schema.id == "P-101"
    assert patient_schema.name == "Priya S."

    cycle_schema = CycleRead.model_validate(loaded_opu.cycle)
    assert cycle_schema.id == "CY-P101-2"
    assert cycle_schema.cycle_no == 2
    assert cycle_schema.type == CycleType.IVF

    record_schema = SourceRecordRead.model_validate(loaded_opu.source_record)
    assert record_schema.id == "REC-0051"
    assert record_schema.version == 1

    opu_schema = OocyteRetrievalRead.model_validate(loaded_opu)
    assert opu_schema.id == "OPU-P101-2"
    assert opu_schema.oocytes_retrieved == 9
    assert opu_schema.source_id == "REC-0051"


def test_source_record_unique_id_version_constraint(db_session: Session):
    """Test that (id, version) uniqueness constraint is enforced."""
    org = Organization(id="ORG-Z", name="Org Z")
    patient = Patient(
        id="P-999",
        name="Test Patient",
        dob=date(1995, 1, 1),
        sex="female",
        org_id="ORG-Z",
    )
    db_session.add_all([org, patient])
    db_session.commit()

    rec1 = SourceRecord(
        id="REC-9999",
        patient_id="P-999",
        type="lab",
        date=date(2025, 1, 1),
        origin_org="Org Z",
        trust_status=TrustStatus.INTERNAL_VERIFIED,
        content_text="Lab record v1",
        version=1,
    )
    db_session.add(rec1)
    db_session.commit()

    db_session.expunge(rec1)
    # Same id and same version should raise IntegrityError
    rec2 = SourceRecord(
        id="REC-9999",
        patient_id="P-999",
        type="lab",
        date=date(2025, 1, 1),
        origin_org="Org Z",
        trust_status=TrustStatus.INTERNAL_VERIFIED,
        content_text="Duplicate record",
        version=1,
    )
    db_session.add(rec2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_indexes_on_patient_cycle_source_ids():
    """Verify that every table with patient_id, cycle_id, or source_id has them indexed."""
    from app.db.base import Base
    import app.models  # noqa: F401

    target_columns = {"patient_id", "cycle_id", "source_id"}
    for table_name, table in Base.metadata.tables.items():
        indexed_cols = set()
        for idx in table.indexes:
            for c in idx.columns:
                indexed_cols.add(c.name)
        for pk_col in table.primary_key.columns:
            indexed_cols.add(pk_col.name)

        for col in target_columns:
            if col in table.columns:
                assert col in indexed_cols, f"Column {col} in table {table_name} is not indexed"
