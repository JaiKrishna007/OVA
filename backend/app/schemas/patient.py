from datetime import date
from typing import Optional, Any
from app.schemas.base import BaseReadSchema


class DoctorPatientRead(BaseReadSchema):
    doctor_id: str
    patient_id: str


class PatientRead(BaseReadSchema):
    id: str
    name: str
    dob: date
    sex: str
    org_id: str
    diagnosis: Optional[Any] = None
    partner_id: Optional[str] = None
    blood_group: Optional[str] = None
    bmi: Optional[float] = None
    phone: Optional[str] = None
