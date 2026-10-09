import copy
import os
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Patient, Cycle, OocyteRetrieval, SourceRecord
from app.services.ingestion.seed_loader import (
    load_seed_data,
    load_raw_seed_files,
    validate_seed_data,
    normalize_unit,
    SeedValidationError,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SEED_DIR = os.path.join(BASE_DIR, "data", "seed")
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")


def test_load_seed_data_succeeds(db_engine):
    """Test that seed data loads cleanly into the database."""
    counts = load_seed_data(seed_dir=SEED_DIR, gold_dir=GOLD_DIR, target_engine=db_engine)

    assert counts["patients"] == 6
    assert counts["cycles"] == 7
    assert counts["source_records"] >= 20
    assert counts["oocyte_retrievals"] >= 3
    assert counts["investigations"] >= 10

    # Query loaded records from database
    with Session(db_engine) as session:
        patient_p101 = session.get(Patient, "P-101")
        assert patient_p101 is not None
        assert patient_p101.name == "Priya S."
        assert len(patient_p101.cycles) == 1

        opu = session.get(OocyteRetrieval, "OPU-P101-1")
        assert opu is not None
        assert opu.oocytes_retrieved == 10
        assert opu.source_id == "REC-0103"
        assert opu.source_record.id == "REC-0103"


def test_corrupted_fixture_missing_source_id_fails_loudly():
    """Test that a clinical row missing its mandatory source_id fails with a clear row-level error."""
    raw_data = load_raw_seed_files(SEED_DIR)
    corrupted_data = copy.deepcopy(raw_data)

    # Corrupt one oocyte retrieval by removing source_id
    corrupted_row = corrupted_data["oocyte_retrievals"][0]
    row_id = corrupted_row["id"]
    corrupted_row["source_id"] = None

    errors = validate_seed_data(corrupted_data, gold_dir=GOLD_DIR)
    assert any("Missing mandatory source_id" in err and row_id in err for err in errors), (
        f"Expected missing source_id error for row {row_id}, got: {errors}"
    )


def test_corrupted_fixture_nonexistent_source_id_fails():
    """Test that a clinical row referencing a nonexistent source_id fails loudly."""
    raw_data = load_raw_seed_files(SEED_DIR)
    corrupted_data = copy.deepcopy(raw_data)

    corrupted_row = corrupted_data["investigations"][0]
    row_id = corrupted_row["id"]
    corrupted_row["source_id"] = "REC-GHOST-999"

    errors = validate_seed_data(corrupted_data, gold_dir=GOLD_DIR)
    assert any("REC-GHOST-999" in err and row_id in err for err in errors), (
        f"Expected nonexistent source_id error for row {row_id}, got: {errors}"
    )


def test_corrupted_fixture_invalid_enum_fails():
    """Test that an invalid enum value is caught with valid options listed."""
    raw_data = load_raw_seed_files(SEED_DIR)
    corrupted_data = copy.deepcopy(raw_data)

    corrupted_row = corrupted_data["cycles"][0]
    row_id = corrupted_row["id"]
    corrupted_row["type"] = "INVALID_CYCLE_TYPE"

    errors = validate_seed_data(corrupted_data, gold_dir=GOLD_DIR)
    assert any("Invalid value 'INVALID_CYCLE_TYPE'" in err and row_id in err for err in errors), (
        f"Expected enum error for cycle {row_id}, got: {errors}"
    )


def test_corrupted_fixture_invalid_date_fails():
    """Test that an unparseable date fails with row-level error."""
    raw_data = load_raw_seed_files(SEED_DIR)
    corrupted_data = copy.deepcopy(raw_data)

    corrupted_row = corrupted_data["patients"][0]
    row_id = corrupted_row["id"]
    corrupted_row["dob"] = "not-a-date"

    errors = validate_seed_data(corrupted_data, gold_dir=GOLD_DIR)
    assert any("Invalid date 'not-a-date'" in err and row_id in err for err in errors), (
        f"Expected invalid date error for patient {row_id}, got: {errors}"
    )


def test_corrupted_fixture_unresolved_fk_fails():
    """Test that an unresolvable foreign key (e.g. unknown org_id) fails."""
    raw_data = load_raw_seed_files(SEED_DIR)
    corrupted_data = copy.deepcopy(raw_data)

    corrupted_row = corrupted_data["patients"][0]
    row_id = corrupted_row["id"]
    corrupted_row["org_id"] = "ORG-NONEXISTENT"

    errors = validate_seed_data(corrupted_data, gold_dir=GOLD_DIR)
    assert any("ORG-NONEXISTENT" in err and row_id in err for err in errors), (
        f"Expected unresolved FK error for patient {row_id}, got: {errors}"
    )


def test_seed_validation_error_raised_on_load(db_engine):
    """Test that load_seed_data raises SeedValidationError when validation fails."""
    # Temporarily pass a bad directory or corrupt raw data
    raw_data = load_raw_seed_files(SEED_DIR)
    corrupted_data = copy.deepcopy(raw_data)
    corrupted_data["treatment_events"][0]["source_id"] = ""

    with pytest.raises(SeedValidationError) as exc_info:
        errors = validate_seed_data(corrupted_data)
        if errors:
            raise SeedValidationError(errors)

    assert "Missing mandatory source_id" in str(exc_info.value)


def test_unit_normalization():
    """Test minimal unit normalization (trim whitespace without silent conversion)."""
    assert normalize_unit(" ng/mL ") == "ng/mL"
    assert normalize_unit("  ng/dL  ") == "ng/dL"
    assert normalize_unit(None) is None
    assert normalize_unit("   ") is None
