"""
Seed Data Loader with strict referential validation and load reporting.
Drops and recreates DB tables, validates FKs, dates, enums, clinical source_ids,
and spans before inserting into the database.
"""

import json
import os
import sys
from datetime import date, datetime, timezone
from typing import Dict, List, Any, Optional

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy.orm import Session
from app.db.base import Base
from app.db.session import engine, SessionLocal, create_all
from app.models import (
    Organization,
    User,
    DoctorPatient,
    Patient,
    SourceRecord,
    Cycle,
    TreatmentEvent,
    Investigation,
    Medication,
    StimulationDay,
    OocyteRetrieval,
    Embryo,
    Transfer,
    PregnancyOutcome,
    AdverseEvent,
    DoctorNote,
    Followup,
    UserRole,
    TrustStatus,
    CycleType,
    TreatmentEventKind,
    InvestigationCategory,
    InvestigationStatus,
    EmbryoFate,
    TransferKind,
    PregnancyResult,
    FollowupStatus,
    ClinicalClaim,
    ClaimValidationStatus,
    ExtractionMethod,
    PatientHospitalAccess,
    HospitalAccessLevel,
    HospitalAccessStatus,
    Consent,
    TransferRequest,
    TransferRequestStatus,
)


class SeedValidationError(Exception):
    """Raised when seed data validation fails."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        message = f"Seed data validation failed with {len(errors)} error(s):\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


def parse_date(val: Any, field_name: str, row_id: str, table_name: str, errors: List[str]) -> Optional[date]:
    if val is None or val == "":
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(val)
    except Exception as exc:
        errors.append(f"[{table_name}] Row '{row_id}': Invalid date '{val}' for field '{field_name}' ({exc})")
        return None


def parse_enum(enum_cls: Any, val: Any, field_name: str, row_id: str, table_name: str, errors: List[str]) -> Any:
    if val is None or val == "":
        return None
    try:
        return enum_cls(val)
    except Exception:
        valid_options = [e.value for e in enum_cls]
        errors.append(
            f"[{table_name}] Row '{row_id}': Invalid value '{val}' for enum {enum_cls.__name__} in field '{field_name}'. "
            f"Valid options: {valid_options}"
        )
        return None


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    """Normalizes units minimally (strip whitespace) without silent unit conversion."""
    if unit is None:
        return None
    stripped = unit.strip()
    return stripped if stripped else None


def load_raw_seed_files(seed_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    """Loads all seed tables from backend/data/seed/*.json or seed.json."""
    combined_file = os.path.join(seed_dir, "seed.json")
    if os.path.exists(combined_file):
        with open(combined_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fallback to loading individual table files
    tables = [
        "organizations",
        "users",
        "doctor_patients",
        "patients",
        "source_records",
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
    ]
    raw_data = {}
    for table in tables:
        path = os.path.join(seed_dir, f"{table}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw_data[table] = json.load(f)
        else:
            raw_data[table] = []
    return raw_data


def validate_seed_data(raw_data: Dict[str, List[Dict[str, Any]]], gold_dir: Optional[str] = None) -> List[str]:
    """
    Performs comprehensive validation:
    1. Foreign key resolution (org_id, patient_id, cycle_id, doctor_id)
    2. Date parsing
    3. Enum validation
    4. Mandatory source_id presence and existence on EVERY clinical row
    5. Span verification against source record text
    """
    errors: List[str] = []

    # Build primary key sets
    org_ids = {row["id"] for row in raw_data.get("organizations", [])}
    user_ids = {row["id"] for row in raw_data.get("users", [])}
    patient_ids = {row["id"] for row in raw_data.get("patients", [])}
    cycle_ids = {row["id"] for row in raw_data.get("cycles", [])}
    source_record_map = {row["id"]: row.get("content_text", "") for row in raw_data.get("source_records", [])}

    # 1. Organizations
    for row in raw_data.get("organizations", []):
        if not row.get("id") or not row.get("name"):
            errors.append(f"[organizations] Row '{row.get('id')}': Missing id or name")

    # 2. Users
    for row in raw_data.get("users", []):
        rid = row.get("id", "UNKNOWN")
        if row.get("org_id") not in org_ids:
            errors.append(f"[users] Row '{rid}': Foreign key org_id '{row.get('org_id')}' not found in organizations")
        parse_enum(UserRole, row.get("role"), "role", rid, "users", errors)

    # 3. DoctorPatients
    for row in raw_data.get("doctor_patients", []):
        did = row.get("doctor_id")
        pid = row.get("patient_id")
        if did not in user_ids:
            errors.append(f"[doctor_patients]: Foreign key doctor_id '{did}' not found in users")
        if pid not in patient_ids:
            errors.append(f"[doctor_patients]: Foreign key patient_id '{pid}' not found in patients")

    # 4. Patients
    for row in raw_data.get("patients", []):
        rid = row.get("id", "UNKNOWN")
        if row.get("org_id") not in org_ids:
            errors.append(f"[patients] Row '{rid}': Foreign key org_id '{row.get('org_id')}' not found in organizations")
        parse_date(row.get("dob"), "dob", rid, "patients", errors)

    # 5. Source Records
    for row in raw_data.get("source_records", []):
        rid = row.get("id", "UNKNOWN")
        if row.get("patient_id") not in patient_ids:
            errors.append(f"[source_records] Row '{rid}': Foreign key patient_id '{row.get('patient_id')}' not found in patients")
        if row.get("cycle_id") and row.get("cycle_id") not in cycle_ids:
            errors.append(f"[source_records] Row '{rid}': Foreign key cycle_id '{row.get('cycle_id')}' not found in cycles")
        parse_date(row.get("date"), "date", rid, "source_records", errors)
        parse_enum(TrustStatus, row.get("trust_status"), "trust_status", rid, "source_records", errors)
        if not row.get("content_text"):
            errors.append(f"[source_records] Row '{rid}': content_text is missing or empty")

    # 6. Cycles
    for row in raw_data.get("cycles", []):
        rid = row.get("id", "UNKNOWN")
        if row.get("patient_id") not in patient_ids:
            errors.append(f"[cycles] Row '{rid}': Foreign key patient_id '{row.get('patient_id')}' not found in patients")
        parse_enum(CycleType, row.get("type"), "type", rid, "cycles", errors)
        parse_date(row.get("start_date"), "start_date", rid, "cycles", errors)
        parse_date(row.get("end_date"), "end_date", rid, "cycles", errors)
        if row.get("source_id") and row.get("source_id") not in source_record_map:
            errors.append(f"[cycles] Row '{rid}': Foreign key source_id '{row.get('source_id')}' not found in source_records")

    # Clinical tables list
    clinical_tables = [
        ("treatment_events", TreatmentEventKind, "kind", "cycle_id"),
        ("investigations", InvestigationCategory, "category", "cycle_id"),
        ("medications", None, None, "cycle_id"),
        ("stimulation_days", None, None, "cycle_id"),
        ("oocyte_retrievals", None, None, "cycle_id"),
        ("embryos", EmbryoFate, "fate", "cycle_id"),
        ("transfers", TransferKind, "kind", "cycle_id"),
        ("pregnancy_outcomes", PregnancyResult, "result", "cycle_id"),
        ("adverse_events", None, None, "cycle_id"),
        ("doctor_notes", None, None, "cycle_id"),
        ("followups", FollowupStatus, "status", "cycle_id"),
    ]

    for table_name, enum_cls, enum_field, cycle_field in clinical_tables:
        for row in raw_data.get(table_name, []):
            rid = row.get("id", "UNKNOWN")
            sid = row.get("source_id")

            # Mandatory source_id rule
            if not sid:
                errors.append(f"[{table_name}] Row '{rid}': Missing mandatory source_id (clinical row has no source reference)")
            elif sid not in source_record_map:
                errors.append(f"[{table_name}] Row '{rid}': source_id '{sid}' does not exist in source_records")

            # Mandatory org_id rule
            oid = row.get("org_id")
            if not oid or oid not in org_ids:
                errors.append(f"[{table_name}] Row '{rid}': Invalid or missing org_id '{oid}'")

            # Mandatory trust_status
            parse_enum(TrustStatus, row.get("trust_status"), "trust_status", rid, table_name, errors)

            # Cycle ID reference
            cid = row.get(cycle_field)
            if cid and cid not in cycle_ids:
                errors.append(f"[{table_name}] Row '{rid}': cycle_id '{cid}' not found in cycles")

            # Patient ID reference (if table has patient_id)
            pid = row.get("patient_id")
            if pid and pid not in patient_ids:
                errors.append(f"[{table_name}] Row '{rid}': patient_id '{pid}' not found in patients")

            # Table-specific enums and dates
            if enum_cls and enum_field:
                parse_enum(enum_cls, row.get(enum_field), enum_field, rid, table_name, errors)

            if "date" in row:
                parse_date(row.get("date"), "date", rid, table_name, errors)
            if "start_date" in row:
                parse_date(row.get("start_date"), "start_date", rid, table_name, errors)
            if "end_date" in row:
                parse_date(row.get("end_date"), "end_date", rid, table_name, errors)
            if "ordered_date" in row:
                parse_date(row.get("ordered_date"), "ordered_date", rid, table_name, errors)
            if "due_date" in row:
                parse_date(row.get("due_date"), "due_date", rid, table_name, errors)
            if "beta_hcg_date" in row:
                parse_date(row.get("beta_hcg_date"), "beta_hcg_date", rid, table_name, errors)

            if table_name == "investigations":
                parse_enum(InvestigationStatus, row.get("status"), "status", rid, table_name, errors)

    # 7. Span text verification from gold set if provided
    if gold_dir and os.path.exists(gold_dir):
        facts_path = os.path.join(gold_dir, "facts.json")
        if os.path.exists(facts_path):
            with open(facts_path, "r", encoding="utf-8") as f:
                facts = json.load(f)
            for fact in facts:
                span = fact.get("span")
                if span:
                    rec_id = span.get("record_id")
                    if rec_id not in source_record_map:
                        errors.append(f"[gold/facts] Span references nonexistent source_id '{rec_id}'")
                    else:
                        full_text = source_record_map[rec_id]
                        start, end = span.get("start", 0), span.get("end", 0)
                        extracted = full_text[start:end]
                        if extracted != str(fact.get("value")):
                            errors.append(
                                f"[gold/facts] Span mismatch in {rec_id} [{start}:{end}]: "
                                f"extracted '{extracted}', expected '{fact.get('value')}'"
                            )

    return errors


def load_seed_data(seed_dir: Optional[str] = None, gold_dir: Optional[str] = None, target_engine=None) -> Dict[str, int]:
    """
    Validates, drops, recreates schema, and loads seed data into the database.
    Returns table row counts.
    """
    s_dir = seed_dir or os.path.join(backend_dir, "data", "seed")
    g_dir = gold_dir or os.path.join(backend_dir, "data", "gold")
    eng = target_engine or engine

    raw_data = load_raw_seed_files(s_dir)

    # Validate before touching the database
    errors = validate_seed_data(raw_data, g_dir)
    if errors:
        raise SeedValidationError(errors)

    # Drop all and recreate schema
    import app.models  # ensure all models (ConflictRecord, DocumentationGap, etc.) are registered for drop_all
    Base.metadata.drop_all(bind=eng)
    create_all(target_engine=eng)

    counts: Dict[str, int] = {}

    with Session(eng) as session:
        # 1. Organizations
        for r in raw_data.get("organizations", []):
            session.add(Organization(id=r["id"], name=r["name"]))
        session.flush()
        counts["organizations"] = len(raw_data.get("organizations", []))

        # 2. Users
        for r in raw_data.get("users", []):
            session.add(
                User(
                    id=r["id"],
                    username=r["username"],
                    password_hash=r["password_hash"],
                    role=UserRole(r["role"]),
                    org_id=r["org_id"],
                    hospital_id=r.get("hospital_id", r["org_id"]),
                    patient_id=r.get("patient_id"),
                )
            )
        session.flush()
        counts["users"] = len(raw_data.get("users", []))

        # 3. Patients
        for r in raw_data.get("patients", []):
            session.add(
                Patient(
                    id=r["id"],
                    name=r["name"],
                    dob=date.fromisoformat(r["dob"]),
                    sex=r["sex"],
                    org_id=r["org_id"],
                    diagnosis=r.get("diagnosis"),
                    partner_id=r.get("partner_id"),
                    blood_group=r.get("blood_group"),
                    bmi=r.get("bmi"),
                    phone=r.get("phone"),
                )
            )
        session.flush()
        counts["patients"] = len(raw_data.get("patients", []))

        # 3b. PatientHospitalAccess (Home hospital READ_WRITE + Cross-hospital delegation)
        pha_rows = []
        for p in raw_data.get("patients", []):
            # Home hospital grant: READ_WRITE, ACTIVE
            pha_rows.append(
                PatientHospitalAccess(
                    id=f"PHA-HOME-{p['id']}",
                    patient_id=p["id"],
                    hospital_id=p["org_id"],
                    access_level=HospitalAccessLevel.READ_WRITE,
                    status=HospitalAccessStatus.ACTIVE,
                    since=datetime.now(timezone.utc),
                )
            )
        # Cross-hospital delegation grant for P-102 at Hospital B (ORG-B and ORG-X): READ_ONLY, ACTIVE
        pha_rows.append(
            PatientHospitalAccess(
                id="PHA-DELEGATE-P102-ORGB",
                patient_id="P-102",
                hospital_id="ORG-B",
                access_level=HospitalAccessLevel.READ_ONLY,
                status=HospitalAccessStatus.ACTIVE,
                since=datetime.now(timezone.utc),
            )
        )
        pha_rows.append(
            PatientHospitalAccess(
                id="PHA-DELEGATE-P102-ORGX",
                patient_id="P-102",
                hospital_id="ORG-X",
                access_level=HospitalAccessLevel.READ_ONLY,
                status=HospitalAccessStatus.ACTIVE,
                since=datetime.now(timezone.utc),
            )
        )
        session.add_all(pha_rows)
        session.flush()
        counts["patient_hospital_access"] = len(pha_rows)

        # 3c. Consents
        for r in raw_data.get("consents", []):
            grant_dt = datetime.fromisoformat(r["granted_at"].replace("Z", "+00:00")) if r.get("granted_at") else datetime.now(timezone.utc)
            session.add(
                Consent(
                    id=r["id"],
                    patient_id=r["patient_id"],
                    org_id=r["org_id"],
                    granted_to_hospital_id=r.get("granted_to_hospital_id"),
                    purpose=r.get("purpose"),
                    scope=r.get("scope"),
                    consent_type=r.get("consent_type", "treatment_transfer"),
                    status=r.get("status", "ACTIVE"),
                    granted_at=grant_dt,
                    granted_by=r.get("granted_by", "patient"),
                    recorded_on_behalf=r.get("recorded_on_behalf", False),
                )
            )
        session.flush()
        counts["consents"] = len(raw_data.get("consents", []))

        # 3d. Transfer Requests
        for r in raw_data.get("transfer_requests", []):
            cr_dt = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) if r.get("created_at") else datetime.now(timezone.utc)
            session.add(
                TransferRequest(
                    id=r["id"],
                    patient_id=r["patient_id"],
                    from_hospital_id=r["from_hospital_id"],
                    to_hospital_id=r["to_hospital_id"],
                    requested_by=r["requested_by"],
                    status=TransferRequestStatus(r.get("status", "REQUESTED")),
                    consent_id=r.get("consent_id"),
                    reason=r.get("reason"),
                    created_at=cr_dt,
                )
            )
        session.flush()
        counts["transfer_requests"] = len(raw_data.get("transfer_requests", []))

        # 4. DoctorPatients
        for r in raw_data.get("doctor_patients", []):
            session.add(DoctorPatient(doctor_id=r["doctor_id"], patient_id=r["patient_id"]))
        session.flush()
        counts["doctor_patients"] = len(raw_data.get("doctor_patients", []))

        # 5. Source Records
        for r in raw_data.get("source_records", []):
            session.add(
                SourceRecord(
                    id=r["id"],
                    patient_id=r["patient_id"],
                    cycle_id=r.get("cycle_id"),
                    type=r["type"],
                    date=date.fromisoformat(r["date"]),
                    author=r.get("author"),
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                    content_text=r["content_text"],
                    version=r.get("version", 1),
                )
            )
        session.flush()
        counts["source_records"] = len(raw_data.get("source_records", []))

        # 6. Cycles
        for r in raw_data.get("cycles", []):
            session.add(
                Cycle(
                    id=r["id"],
                    patient_id=r["patient_id"],
                    cycle_no=r["cycle_no"],
                    type=CycleType(r["type"]),
                    start_date=date.fromisoformat(r["start_date"]),
                    end_date=date.fromisoformat(r["end_date"]) if r.get("end_date") else None,
                    outcome=r.get("outcome"),
                    origin_org=r.get("origin_org"),
                    external_cycle_no=r.get("external_cycle_no"),
                    source_id=r.get("source_id"),
                    org_id=r.get("org_id"),
                    trust_status=TrustStatus(r["trust_status"]) if r.get("trust_status") else None,
                )
            )
        session.flush()
        counts["cycles"] = len(raw_data.get("cycles", []))

        # 7. Treatment Events
        for r in raw_data.get("treatment_events", []):
            session.add(
                TreatmentEvent(
                    id=r["id"],
                    cycle_id=r["cycle_id"],
                    kind=TreatmentEventKind(r["kind"]),
                    date=date.fromisoformat(r["date"]),
                    detail=r.get("detail"),
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["treatment_events"] = len(raw_data.get("treatment_events", []))

        # 8. Investigations
        for r in raw_data.get("investigations", []):
            session.add(
                Investigation(
                    id=r["id"],
                    patient_id=r["patient_id"],
                    cycle_id=r.get("cycle_id"),
                    category=InvestigationCategory(r["category"]),
                    name=r["name"],
                    value=r["value"],
                    unit=normalize_unit(r.get("unit")),
                    ref_range=r.get("ref_range"),
                    date=date.fromisoformat(r["date"]) if r.get("date") else None,
                    status=InvestigationStatus(r["status"]),
                    ordered_date=date.fromisoformat(r["ordered_date"]) if r.get("ordered_date") else None,
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["investigations"] = len(raw_data.get("investigations", []))

        # 9. Medications
        for r in raw_data.get("medications", []):
            session.add(
                Medication(
                    id=r["id"],
                    cycle_id=r["cycle_id"],
                    name=r["name"],
                    dose=r["dose"],
                    route=r["route"],
                    start_date=date.fromisoformat(r["start_date"]) if r.get("start_date") else None,
                    end_date=date.fromisoformat(r["end_date"]) if r.get("end_date") else None,
                    purpose=r.get("purpose"),
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["medications"] = len(raw_data.get("medications", []))

        # 10. Stimulation Days
        for r in raw_data.get("stimulation_days", []):
            session.add(
                StimulationDay(
                    id=r["id"],
                    cycle_id=r["cycle_id"],
                    day_no=r["day_no"],
                    date=date.fromisoformat(r["date"]),
                    follicles=r["follicles"],
                    e2=r.get("e2"),
                    lh=r.get("lh"),
                    p4=r.get("p4"),
                    endometrium_mm=r.get("endometrium_mm"),
                    dose_note=r.get("dose_note"),
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["stimulation_days"] = len(raw_data.get("stimulation_days", []))

        # 11. Oocyte Retrievals
        for r in raw_data.get("oocyte_retrievals", []):
            session.add(
                OocyteRetrieval(
                    id=r["id"],
                    cycle_id=r["cycle_id"],
                    date=date.fromisoformat(r["date"]),
                    oocytes_retrieved=r["oocytes_retrieved"],
                    mii=r.get("mii"),
                    mi=r.get("mi"),
                    gv=r.get("gv"),
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["oocyte_retrievals"] = len(raw_data.get("oocyte_retrievals", []))

        # 12. Embryos
        for r in raw_data.get("embryos", []):
            session.add(
                Embryo(
                    id=r["id"],
                    cycle_id=r["cycle_id"],
                    embryo_label=r["embryo_label"],
                    day=r["day"],
                    grade=r.get("grade"),
                    pgt_status=r.get("pgt_status"),
                    fate=EmbryoFate(r["fate"]),
                    storage_location=r.get("storage_location"),
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["embryos"] = len(raw_data.get("embryos", []))

        # 13. Transfers
        for r in raw_data.get("transfers", []):
            session.add(
                Transfer(
                    id=r["id"],
                    cycle_id=r["cycle_id"],
                    date=date.fromisoformat(r["date"]),
                    kind=TransferKind(r["kind"]),
                    embryo_ids=r["embryo_ids"],
                    endometrium_mm=r.get("endometrium_mm"),
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["transfers"] = len(raw_data.get("transfers", []))

        # 14. Pregnancy Outcomes
        for r in raw_data.get("pregnancy_outcomes", []):
            session.add(
                PregnancyOutcome(
                    id=r["id"],
                    cycle_id=r["cycle_id"],
                    beta_hcg_value=r.get("beta_hcg_value"),
                    beta_hcg_date=date.fromisoformat(r["beta_hcg_date"]) if r.get("beta_hcg_date") else None,
                    result=PregnancyResult(r["result"]),
                    gestation_note=r.get("gestation_note"),
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["pregnancy_outcomes"] = len(raw_data.get("pregnancy_outcomes", []))

        # 15. Adverse Events
        for r in raw_data.get("adverse_events", []):
            session.add(
                AdverseEvent(
                    id=r["id"],
                    cycle_id=r["cycle_id"],
                    kind=r["kind"],
                    severity=r["severity"],
                    date=date.fromisoformat(r["date"]),
                    management_note=r.get("management_note"),
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["adverse_events"] = len(raw_data.get("adverse_events", []))

        # 16. Doctor Notes
        for r in raw_data.get("doctor_notes", []):
            session.add(
                DoctorNote(
                    id=r["id"],
                    patient_id=r["patient_id"],
                    cycle_id=r.get("cycle_id"),
                    date=date.fromisoformat(r["date"]),
                    author=r["author"],
                    text=r["text"],
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["doctor_notes"] = len(raw_data.get("doctor_notes", []))

        # 17. Followups
        for r in raw_data.get("followups", []):
            session.add(
                Followup(
                    id=r["id"],
                    patient_id=r["patient_id"],
                    cycle_id=r.get("cycle_id"),
                    kind=r["kind"],
                    name=r["name"],
                    status=FollowupStatus(r["status"]),
                    due_date=date.fromisoformat(r["due_date"]),
                    source_id=r["source_id"],
                    org_id=r["org_id"],
                    origin_org=r["origin_org"],
                    trust_status=TrustStatus(r["trust_status"]),
                )
            )
        session.flush()
        counts["followups"] = len(raw_data.get("followups", []))

        # 18. Backfill Clinical Claims (one row per existing typed clinical row)
        claims_count, claims_per_patient = _backfill_clinical_claims(session, raw_data)
        counts["clinical_claims"] = claims_count
        counts["_claims_per_patient"] = claims_per_patient

        session.commit()

    return counts


def _find_span_and_evidence(content_text: str, candidate_text: Optional[Any], fallback_text: Optional[str] = None):
    """Finds character offset span and surrounding evidence window for extracted values."""
    if not content_text:
        return None, None, None
    for cand in [candidate_text, fallback_text]:
        if not cand:
            continue
        c_str = str(cand).strip()
        if not c_str:
            continue
        idx = content_text.find(c_str)
        if idx != -1:
            s = idx
            e = idx + len(c_str)
            ctx_s = max(0, s - 30)
            ctx_e = min(len(content_text), e + 30)
            return s, e, content_text[ctx_s:ctx_e].strip()
        # Case insensitive match
        idx_lower = content_text.lower().find(c_str.lower())
        if idx_lower != -1:
            s = idx_lower
            e = idx_lower + len(c_str)
            ctx_s = max(0, s - 30)
            ctx_e = min(len(content_text), e + 30)
            return s, e, content_text[ctx_s:ctx_e].strip()

    # Fallback snippet
    snippet = content_text[:120].strip() if content_text else None
    return None, None, snippet


def _backfill_clinical_claims(session: Session, raw_data: Dict[str, List[Dict[str, Any]]]):
    """
    Backfills one clinical_claims row (extraction_method=seed, validation_status=VERIFIED)
    for every existing typed clinical row, linked via materialized_table/materialized_row_id.
    Explicit hospital scoping: org_id on clinical rows is the hospital that created it (origin),
    which does not change on transfer.
    """
    cycle_to_patient = {c["id"]: c["patient_id"] for c in raw_data.get("cycles", [])}
    source_records_text = {s["id"]: s.get("content_text", "") for s in raw_data.get("source_records", [])}

    claims_per_patient: Dict[str, int] = {p["id"]: 0 for p in raw_data.get("patients", [])}
    total_claims = 0

    clinical_tables = [
        ("treatment_events", "treatment_event"),
        ("investigations", "investigation"),
        ("medications", "medication"),
        ("stimulation_days", "stimulation_day"),
        ("oocyte_retrievals", "oocyte_retrieval"),
        ("embryos", "embryo"),
        ("transfers", "transfer"),
        ("pregnancy_outcomes", "pregnancy_outcome"),
        ("adverse_events", "adverse_event"),
        ("doctor_notes", "doctor_note"),
        ("followups", "followup"),
    ]

    for table_name, default_field in clinical_tables:
        rows = raw_data.get(table_name, [])
        for r in rows:
            cid = r.get("cycle_id")
            pid = r.get("patient_id") or (cycle_to_patient.get(cid) if cid else None)
            if not pid:
                continue

            field_name = default_field
            val_text: Optional[str] = None
            val_num: Optional[float] = None
            unit: Optional[str] = None
            date_val: Optional[date] = None
            candidate_for_span: Optional[Any] = None
            fallback_for_span: Optional[str] = None

            if table_name == "treatment_events":
                field_name = r.get("kind", default_field)
                val_text = r.get("detail") or r.get("kind")
                candidate_for_span = r.get("detail") or r.get("kind")
                if r.get("date"):
                    date_val = date.fromisoformat(r["date"])
            elif table_name == "investigations":
                field_name = r.get("name", default_field)
                val_text = str(r.get("value")) if r.get("value") is not None else None
                try:
                    if val_text:
                        val_num = float(val_text)
                except ValueError:
                    val_num = None
                unit = normalize_unit(r.get("unit"))
                candidate_for_span = val_text
                fallback_for_span = r.get("name")
                if r.get("date"):
                    date_val = date.fromisoformat(r["date"])
            elif table_name == "medications":
                field_name = r.get("name", default_field)
                val_text = f"{r.get('name')} {r.get('dose')}".strip()
                candidate_for_span = r.get("name")
                fallback_for_span = r.get("dose")
                if r.get("start_date"):
                    date_val = date.fromisoformat(r["start_date"])
            elif table_name == "stimulation_days":
                field_name = f"day_{r.get('day_no')}"
                val_text = f"Day {r.get('day_no')}"
                val_num = float(r["day_no"]) if r.get("day_no") is not None else None
                candidate_for_span = f"Day {r.get('day_no')}"
                fallback_for_span = str(r.get("day_no"))
                if r.get("date"):
                    date_val = date.fromisoformat(r["date"])
            elif table_name == "oocyte_retrievals":
                field_name = "oocytes_retrieved"
                val_text = str(r.get("oocytes_retrieved"))
                val_num = float(r["oocytes_retrieved"]) if r.get("oocytes_retrieved") is not None else None
                candidate_for_span = str(r.get("oocytes_retrieved"))
                fallback_for_span = "oocytes"
                if r.get("date"):
                    date_val = date.fromisoformat(r["date"])
            elif table_name == "embryos":
                field_name = f"embryo_{r.get('embryo_label')}"
                val_text = r.get("grade") or r.get("embryo_label")
                candidate_for_span = r.get("grade")
                fallback_for_span = r.get("embryo_label")
            elif table_name == "transfers":
                field_name = "transfer_kind"
                val_text = r.get("kind")
                candidate_for_span = r.get("kind")
                if r.get("date"):
                    date_val = date.fromisoformat(r["date"])
            elif table_name == "pregnancy_outcomes":
                field_name = "pregnancy_outcome"
                val_text = r.get("result")
                if r.get("beta_hcg_value") is not None:
                    try:
                        val_num = float(r["beta_hcg_value"])
                    except ValueError:
                        pass
                candidate_for_span = r.get("result")
                fallback_for_span = str(r.get("beta_hcg_value")) if r.get("beta_hcg_value") is not None else None
                if r.get("beta_hcg_date"):
                    date_val = date.fromisoformat(r["beta_hcg_date"])
            elif table_name == "adverse_events":
                field_name = "adverse_event"
                val_text = f"{r.get('kind')} ({r.get('severity')})".strip()
                candidate_for_span = r.get("kind")
                fallback_for_span = r.get("severity")
                if r.get("date"):
                    date_val = date.fromisoformat(r["date"])
            elif table_name == "doctor_notes":
                field_name = "doctor_note"
                val_text = r.get("text", "")[:100]
                candidate_for_span = r.get("text", "")[:30]
                if r.get("date"):
                    date_val = date.fromisoformat(r["date"])
            elif table_name == "followups":
                field_name = "followup"
                val_text = r.get("name")
                candidate_for_span = r.get("name")
                if r.get("due_date"):
                    date_val = date.fromisoformat(r["due_date"])

            src_id = r["source_id"]
            src_text = source_records_text.get(src_id, "")
            span_start, span_end, evidence = _find_span_and_evidence(src_text, candidate_for_span, fallback_for_span)

            claim = ClinicalClaim(
                id=f"CLM-{r['id']}",
                patient_id=pid,
                hospital_id=r["org_id"],  # Originating hospital, immutable on transfer
                source_record_id=src_id,
                cycle_id=cid,
                field=field_name,
                value_text=val_text,
                value_num=val_num,
                unit=unit,
                event_date=date_val,
                span_start=span_start,
                span_end=span_end,
                evidence_text=evidence,
                extraction_method=ExtractionMethod.SEED,
                validation_status=ClaimValidationStatus.VERIFIED,
                validation_checks={"seed_source_valid": True, "fk_consistent": True},
                reason_codes=[],
                uploaded_by=None,
                created_at=datetime.now(timezone.utc),
                materialized_table=table_name,
                materialized_row_id=r["id"],
            )
            session.add(claim)
            total_claims += 1
            claims_per_patient[pid] = claims_per_patient.get(pid, 0) + 1

    session.flush()

    # Pre-persist conflicts and gaps for all patients
    from app.services.engines.conflicts import recompute_and_persist_conflicts
    from app.services.engines.gaps import recompute_and_persist_gaps
    for p in raw_data.get("patients", []):
        try:
            recompute_and_persist_conflicts(session, p["id"])
            recompute_and_persist_gaps(session, p["id"])
        except Exception:
            pass

    session.flush()
    return total_claims, claims_per_patient


def print_load_report(counts: Dict[str, int], raw_data: Dict[str, List[Dict[str, Any]]]) -> None:
    """Prints a clear load report with table, patient-level summaries, and clinical claims per patient."""
    print("\n" + "=" * 80)
    print("                    SEED INGESTION REPORT (LOAD COMPLETE)")
    print("=" * 80)
    print("TABLES LOADED:")
    for tbl, count in sorted(counts.items()):
        if not tbl.startswith("_"):
            print(f"  - {tbl:<22}: {count:>4} rows")
    print("-" * 80)

    claims_per_patient = counts.get("_claims_per_patient", {})
    if claims_per_patient:
        print("CLINICAL CLAIMS BACKFILLED PER PATIENT (1 CLAIM PER TYPED ROW):")
        for p in raw_data.get("patients", []):
            pid = p["id"]
            cnt = claims_per_patient.get(pid, 0)
            print(f"  - {pid:<10} ({p['name']:<14}) : {cnt:>4} claims [origin: {p.get('org_id')}]")
        print(f"  Total Claims Backfilled : {sum(claims_per_patient.values()):>4} claims")
        print("-" * 80)

    print(f"{'Patient ID':<12} | {'Name':<14} | {'Cycles':<6} | {'Records':<8} | {'Labs':<6} | {'OPU/Embryo':<10} | {'Notes/FOL':<9}")
    print("-" * 80)

    for p in raw_data.get("patients", []):
        pid = p["id"]
        c_count = len([c for c in raw_data.get("cycles", []) if c["patient_id"] == pid])
        r_count = len([r for r in raw_data.get("source_records", []) if r["patient_id"] == pid])
        l_count = len([i for i in raw_data.get("investigations", []) if i["patient_id"] == pid])
        opu_count = len([
            o for o in raw_data.get("oocyte_retrievals", [])
            if any(c["id"] == o["cycle_id"] and c["patient_id"] == pid for c in raw_data.get("cycles", []))
        ])
        emb_count = len([
            e for e in raw_data.get("embryos", [])
            if any(c["id"] == e["cycle_id"] and c["patient_id"] == pid for c in raw_data.get("cycles", []))
        ])
        note_count = len([n for n in raw_data.get("doctor_notes", []) if n["patient_id"] == pid])
        fol_count = len([f for f in raw_data.get("followups", []) if f["patient_id"] == pid])

        print(
            f"{pid:<12} | {p['name']:<14} | {c_count:<6} | {r_count:<8} | {l_count:<6} | "
            f"{f'{opu_count}/{emb_count}':<10} | {f'{note_count}/{fol_count}':<9}"
        )
    print("=" * 80 + "\n")


def seed_demo_p102_claims(target_engine=None):
    """Seeds cross-hospital AMH claims for P-102 and precomputes conflicts for interactive demo."""
    eng = target_engine or engine
    with Session(eng) as session:
        p102_amh_a = session.get(ClinicalClaim, "CLM-TEST-P102-AMH-A")
        if not p102_amh_a:
            claim_a = ClinicalClaim(
                id="CLM-TEST-P102-AMH-A",
                patient_id="P-102",
                hospital_id="ORG-Y",
                source_record_id="REC-0201",
                field="amh",
                value_text="2.4",
                value_num=2.4,
                unit="ng/mL",
                event_date=date(2026, 6, 14),
                evidence_text="Serum AMH was 2.4 ng/mL.",
                span_start=14,
                span_end=17,
                extraction_method=ExtractionMethod.SEED,
                validation_status=ClaimValidationStatus.VERIFIED,
                validation_checks={"seed_source_valid": True, "fk_consistent": True},
                reason_codes=[],
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
                event_date=date(2026, 6, 16),
                evidence_text="Serum AMH documented as 1.2 ng/mL.",
                span_start=25,
                span_end=28,
                extraction_method=ExtractionMethod.SEED,
                validation_status=ClaimValidationStatus.VERIFIED,
                validation_checks={"seed_source_valid": True, "fk_consistent": True},
                reason_codes=[],
                created_at=datetime.now(timezone.utc),
            )
            session.add_all([claim_a, claim_b])
            session.commit()
            from app.services.engines.conflicts import recompute_and_persist_conflicts
            recompute_and_persist_conflicts(session, "P-102")
            session.commit()


def main():
    try:
        s_dir = os.path.join(backend_dir, "data", "seed")
        g_dir = os.path.join(backend_dir, "data", "gold")
        raw_data = load_raw_seed_files(s_dir)
        counts = load_seed_data(seed_dir=s_dir, gold_dir=g_dir)
        print_load_report(counts, raw_data)
        print("PASS: Database seeded successfully.")
    except SeedValidationError as e:
        print(f"\nFATAL: Seed data validation failed:\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nFATAL: Database load error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
