from dataclasses import dataclass
from datetime import date
from typing import Optional, Any
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.cycle import Cycle
from app.models.clinical import (
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
)
from app.models.source_record import SourceRecord


@dataclass
class ResolvedField:
    table: str
    row_id: str
    column: str
    value: Any
    row: Any
    patient_id: Optional[str] = None
    cycle_id: Optional[str] = None
    date: Optional[date] = None
    source_id: Optional[str] = None


TABLE_MODEL_MAP = {
    "patients": Patient,
    "cycles": Cycle,
    "treatment_events": TreatmentEvent,
    "investigations": Investigation,
    "medications": Medication,
    "stimulation_days": StimulationDay,
    "oocyte_retrievals": OocyteRetrieval,
    "embryos": Embryo,
    "transfers": Transfer,
    "pregnancy_outcomes": PregnancyOutcome,
    "adverse_events": AdverseEvent,
    "doctor_notes": DoctorNote,
    "followups": Followup,
    "source_records": SourceRecord,
}


def resolve_field_path(db: Session, field_path: Optional[str]) -> Optional[ResolvedField]:
    """
    Resolves a structured field_path in the format '<table>.<row_id>.<column>'.
    Returns ResolvedField or None if unresolvable.
    """
    if not field_path or not isinstance(field_path, str):
        return None

    parts = field_path.strip().split(".")
    if len(parts) != 3:
        return None

    table_name, row_id, column_name = parts[0], parts[1], parts[2]
    model_cls = TABLE_MODEL_MAP.get(table_name)
    if not model_cls:
        return None

    row = db.get(model_cls, row_id)
    if not row:
        return None

    if not hasattr(row, column_name):
        return None

    raw_val = getattr(row, column_name)
    val = raw_val.value if hasattr(raw_val, "value") else raw_val

    # Derive patient_id, cycle_id, date, and source_id
    patient_id = None
    cycle_id = getattr(row, "cycle_id", None)
    row_date = getattr(row, "date", None)
    source_id = getattr(row, "source_id", None)

    if hasattr(row, "patient_id"):
        patient_id = getattr(row, "patient_id")
    elif isinstance(row, Patient):
        patient_id = row.id
    elif isinstance(row, Cycle):
        patient_id = row.patient_id
        cycle_id = row.id
        row_date = row.start_date
    elif cycle_id:
        cycle = db.get(Cycle, cycle_id)
        if cycle:
            patient_id = cycle.patient_id

    # Fallbacks for specific dates
    if row_date is None and hasattr(row, "beta_hcg_date"):
        row_date = getattr(row, "beta_hcg_date")
    if row_date is None and hasattr(row, "ordered_date"):
        row_date = getattr(row, "ordered_date")
    if row_date is None and hasattr(row, "due_date"):
        row_date = getattr(row, "due_date")

    return ResolvedField(
        table=table_name,
        row_id=row_id,
        column=column_name,
        value=val,
        row=row,
        patient_id=patient_id,
        cycle_id=cycle_id,
        date=row_date,
        source_id=source_id,
    )
