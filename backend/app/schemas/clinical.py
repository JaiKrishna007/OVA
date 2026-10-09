from datetime import date
from typing import Optional, Any
from app.models.enums import (
    TrustStatus,
    TreatmentEventKind,
    InvestigationCategory,
    InvestigationStatus,
    EmbryoFate,
    TransferKind,
    PregnancyResult,
    FollowupStatus,
)
from app.schemas.base import BaseReadSchema


class ClinicalReadBase(BaseReadSchema):
    source_id: str
    org_id: str
    origin_org: str
    trust_status: TrustStatus


class TreatmentEventRead(ClinicalReadBase):
    id: str
    cycle_id: str
    kind: TreatmentEventKind
    date: date
    detail: Optional[str] = None


class InvestigationRead(ClinicalReadBase):
    id: str
    patient_id: str
    cycle_id: Optional[str] = None
    category: InvestigationCategory
    name: str
    value: str
    unit: Optional[str] = None
    ref_range: Optional[str] = None
    date: Optional[date] = None
    status: InvestigationStatus
    ordered_date: Optional[date] = None


class MedicationRead(ClinicalReadBase):
    id: str
    cycle_id: str
    name: str
    dose: str
    route: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    purpose: Optional[str] = None


class StimulationDayRead(ClinicalReadBase):
    id: str
    cycle_id: str
    day_no: int
    date: date
    follicles: Any
    e2: Optional[float] = None
    lh: Optional[float] = None
    p4: Optional[float] = None
    endometrium_mm: Optional[float] = None
    dose_note: Optional[str] = None


class OocyteRetrievalRead(ClinicalReadBase):
    id: str
    cycle_id: str
    date: date
    oocytes_retrieved: int
    mii: Optional[int] = None
    mi: Optional[int] = None
    gv: Optional[int] = None


class EmbryoRead(ClinicalReadBase):
    id: str
    cycle_id: str
    embryo_label: str
    day: int
    grade: Optional[str] = None
    pgt_status: Optional[str] = None
    fate: EmbryoFate
    storage_location: Optional[str] = None


class TransferRead(ClinicalReadBase):
    id: str
    cycle_id: str
    date: date
    kind: TransferKind
    embryo_ids: Any
    endometrium_mm: Optional[float] = None


class PregnancyOutcomeRead(ClinicalReadBase):
    id: str
    cycle_id: str
    beta_hcg_value: Optional[float] = None
    beta_hcg_date: Optional[date] = None
    result: PregnancyResult
    gestation_note: Optional[str] = None


class AdverseEventRead(ClinicalReadBase):
    id: str
    cycle_id: str
    kind: str
    severity: str
    date: date
    management_note: Optional[str] = None


class DoctorNoteRead(ClinicalReadBase):
    id: str
    patient_id: str
    cycle_id: Optional[str] = None
    date: date
    author: str
    text: str


class FollowupRead(ClinicalReadBase):
    id: str
    patient_id: str
    cycle_id: Optional[str] = None
    kind: str
    name: str
    status: FollowupStatus
    due_date: date
