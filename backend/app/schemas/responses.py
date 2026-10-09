from datetime import date as dt_date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.enums import FollowupStatus


class PatientListItem(BaseModel):
    id: str = Field(..., description="Unique Patient Identifier", examples=["P-101"])
    name: str = Field(..., description="Patient Full Name", examples=["Priya S."])
    dob: dt_date = Field(..., description="Date of birth", examples=["1991-05-20"])
    sex: str = Field(..., description="Patient sex", examples=["female"])
    org_id: str = Field(..., description="Organization ID", examples=["ORG-Y"])
    diagnosis: Optional[Any] = Field(None, description="Primary & secondary clinical diagnosis", examples=[{"primary": "Diminished Ovarian Reserve (DOR)", "secondary": "Primary Infertility 3 yrs"}])
    partner_id: Optional[str] = Field(None, description="Partner Identifier", examples=["PART-P101"])
    blood_group: Optional[str] = Field(None, description="Blood group", examples=["B+"])
    bmi: Optional[float] = Field(None, description="Body Mass Index", examples=[22.4])
    phone_masked: Optional[str] = Field(None, description="Masked contact phone number", examples=["+91-98450*****"])
    current_stage: str = Field(..., description="Derived current fertility stage relative to AS_OF_DATE", examples=["Stimulation day 8, cycle 3"])
    source_refs: List[str] = Field(default_factory=list, description="Associated source records provenance", examples=[["REC-0010"]])


class PatientDetailResponse(BaseModel):
    id: str = Field(..., description="Unique Patient Identifier", examples=["P-101"])
    name: str = Field(..., description="Patient Full Name", examples=["Priya S."])
    dob: dt_date = Field(..., description="Date of birth", examples=["1991-05-20"])
    sex: str = Field(..., description="Patient sex", examples=["female"])
    org_id: str = Field(..., description="Organization ID", examples=["ORG-Y"])
    diagnosis: Optional[Any] = Field(None, description="Primary & secondary clinical diagnosis", examples=[{"primary": "Diminished Ovarian Reserve (DOR)"}])
    partner_id: Optional[str] = Field(None, description="Partner Identifier", examples=["PART-P101"])
    blood_group: Optional[str] = Field(None, description="Blood group", examples=["B+"])
    bmi: Optional[float] = Field(None, description="Body Mass Index", examples=[22.4])
    phone_masked: Optional[str] = Field(None, description="Masked contact phone number", examples=["+91-98450*****"])
    current_stage: str = Field(..., description="Derived current fertility stage relative to AS_OF_DATE", examples=["Stimulation day 8, cycle 3"])
    source_refs: List[str] = Field(default_factory=list, description="Associated source records provenance", examples=[["REC-0010", "REC-0011"]])
    access_level: Optional[str] = Field(None, description="Current user's hospital access level (READ_WRITE or READ_ONLY)")
    transferred_to_hospital: Optional[str] = Field(None, description="Target hospital ID if transferred")


class TimelineResponse(BaseModel):
    patient_id: str = Field(..., description="Patient Identifier", examples=["P-101"])
    stage: str = Field(..., description="Current clinical stage", examples=["Stimulation day 8, cycle 3"])
    total_cycles: int = Field(..., description="Total treatment cycles recorded", examples=[3])
    cycles: List[Dict[str, Any]] = Field(..., description="Chronological treatment cycles with outcome badges and trust tags")
    years: List[Dict[str, Any]] = Field(default_factory=list, description="Chronological events and cycles grouped by year")
    unlinked_events: List[Dict[str, Any]] = Field(default_factory=list, description="Clinical events not tied to a specific cycle")
    source_refs: List[str] = Field(..., description="All source records referenced in timeline", examples=[["REC-0010", "REC-0020"]])


class CycleDetailResponse(BaseModel):
    id: str = Field(..., description="Cycle Identifier", examples=["CY-P101-2"])
    patient_id: str = Field(..., description="Patient Identifier", examples=["P-101"])
    cycle_no: int = Field(..., description="Cycle number", examples=[2])
    type: str = Field(..., description="Treatment cycle type", examples=["IVF"])
    start_date: Optional[dt_date] = Field(None, description="Cycle start date", examples=["2024-05-28"])
    end_date: Optional[dt_date] = Field(None, description="Cycle completion date", examples=["2024-07-02"])
    outcome: Optional[str] = Field(None, description="Recorded outcome string", examples=["biochemical_pregnancy"])
    outcome_badge: str = Field(..., description="Formatted outcome badge", examples=["Biochemical Pregnancy"])
    origin_org: str = Field(..., description="Originating organization", examples=["ORG-Y"])
    trust_status: str = Field(..., description="Trust verification level", examples=["internal_verified"])
    events: List[Dict[str, Any]] = Field(default_factory=list, description="Treatment events in this cycle")
    stimulation_summary: Optional[Dict[str, Any]] = Field(None, description="Stimulation statistics")
    opu: Optional[Dict[str, Any]] = Field(None, description="Oocyte retrieval details")
    embryos: List[Dict[str, Any]] = Field(default_factory=list, description="Embryos cultured in this cycle")
    transfers: List[Dict[str, Any]] = Field(default_factory=list, description="Embryo transfers performed")
    pregnancy_outcome: Optional[Dict[str, Any]] = Field(None, description="Pregnancy test and outcome")
    adverse_events: List[Dict[str, Any]] = Field(default_factory=list, description="Recorded adverse events")
    source_refs: List[str] = Field(..., description="All source records for this cycle", examples=[["REC-0050", "REC-0051"]])


class CycleComparisonResponse(BaseModel):
    patient_id: str = Field(..., description="Patient Identifier", examples=["P-101"])
    comparison_matrix: List[Dict[str, Any]] = Field(..., description="Comparative parameters across all cycles")
    source_refs: List[str] = Field(..., description="All source records referenced", examples=[["REC-0010", "REC-0051"]])
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="Active conflicts for this patient")


class EmbryosResponse(BaseModel):
    patient_id: str = Field(..., description="Patient Identifier", examples=["P-101"])
    total_count: int = Field(..., description="Total embryos tracked across cycles", examples=[4])
    remaining_frozen: int = Field(..., description="Embryos currently remaining in frozen storage", examples=[1])
    transferred_count: int = Field(..., description="Embryos transferred", examples=[1])
    discarded_count: int = Field(..., description="Embryos arrested or discarded", examples=[2])
    embryos: List[Dict[str, Any]] = Field(..., description="Detailed embryo inventory with morphology & PGT status")
    source_refs: List[str] = Field(..., description="All source records supporting embryo data", examples=[["REC-0052"]])


class StimulationResponse(BaseModel):
    patient_id: str = Field(..., description="Patient Identifier", examples=["P-101"])
    cycle_id: str = Field(..., description="Cycle Identifier", examples=["CY-P101-2"])
    summary: Dict[str, Any] = Field(..., description="Stimulation summary metrics (days, peak E2, max follicles)")
    days: List[Dict[str, Any]] = Field(..., description="Daily follicular tracking, hormones, and dose notes")
    medications: List[Dict[str, Any]] = Field(default_factory=list, description="Medications administered during stimulation")
    trigger: Optional[Dict[str, Any]] = Field(None, description="Ovulation trigger details")
    source_refs: List[str] = Field(..., description="All source records supporting stimulation data", examples=[["REC-0050"]])


class FollowupsResponse(BaseModel):
    patient_id: str = Field(..., description="Patient Identifier", examples=["P-101"])
    as_of_date: str = Field(..., description="Reference date for overdue evaluation", examples=["2025-03-14"])
    counts: Dict[str, int] = Field(..., description="Counts of items by status", examples=[{"overdue": 1, "scheduled": 0, "pending": 0, "done": 0}])
    overdue: List[Dict[str, Any]] = Field(..., description="Overdue investigations and consultations")
    scheduled: List[Dict[str, Any]] = Field(..., description="Scheduled upcoming follow-ups")
    pending: List[Dict[str, Any]] = Field(..., description="Pending follow-ups")
    done: List[Dict[str, Any]] = Field(..., description="Completed follow-ups")
    source_refs: List[str] = Field(..., description="All source records supporting followups", examples=[["REC-0010"]])


class FollowupUpdateRequest(BaseModel):
    status: Optional[FollowupStatus] = Field(None, description="Updated status", examples=["done"])
    due_date: Optional[dt_date] = Field(None, description="Updated due date", examples=["2025-04-01"])
    name: Optional[str] = Field(None, description="Followup name", examples=["Repeat TSH"])


class FollowupItemResponse(BaseModel):
    id: str = Field(..., description="Followup Identifier", examples=["FOL-P101-1"])
    patient_id: str = Field(..., description="Patient Identifier", examples=["P-101"])
    cycle_id: Optional[str] = Field(None, description="Associated Cycle Identifier", examples=["CY-P101-3"])
    kind: str = Field(..., description="Followup category", examples=["investigation"])
    name: str = Field(..., description="Followup item name", examples=["Repeat TSH (Target < 2.5 mIU/L)"])
    status: str = Field(..., description="Followup status", examples=["done"])
    due_date: dt_date = Field(..., description="Due date", examples=["2025-03-01"])
    source_id: str = Field(..., description="Source record Identifier", examples=["REC-0010"])
    source_refs: List[str] = Field(..., description="Source record provenance", examples=[["REC-0010"]])


class SourceRecordDetailResponse(BaseModel):
    id: str = Field(..., description="Source Record Identifier", examples=["REC-0142"])
    patient_id: str = Field(..., description="Patient Identifier", examples=["P-101"])
    cycle_id: Optional[str] = Field(None, description="Cycle Identifier", examples=["CY-P101-2"])
    type: str = Field(..., description="Document type (lab, opu_report, discharge_summary, doctor_notes)", examples=["opu_report"])
    date: dt_date = Field(..., description="Document date", examples=["2024-06-12"])
    author: Optional[str] = Field(None, description="Document author or clinician", examples=["Dr. Ramesh"])
    origin_org: str = Field(..., description="Originating organization", examples=["ORG-Y"])
    trust_status: str = Field(..., description="Trust verification tier", examples=["internal_verified"])
    version: int = Field(..., description="Document version (starts at 1)", examples=[1])
    content_text: str = Field(..., description="Full raw content text of the clinical record", examples=["OPU PROCEDURE REPORT..."])
    source_refs: List[str] = Field(..., description="Source provenance", examples=[["REC-0142"]])


class RecordSummaryItem(BaseModel):
    id: str = Field(..., examples=["REC-0010"])
    patient_id: str = Field(..., examples=["P-101"])
    cycle_id: Optional[str] = Field(None, examples=["CY-P101-1"])
    type: str = Field(..., examples=["lab"])
    date: dt_date = Field(..., examples=["2024-01-10"])
    author: Optional[str] = Field(None, examples=["Dr. Rao"])
    origin_org: str = Field(..., examples=["ORG-Y"])
    trust_status: str = Field(..., examples=["internal_verified"])
    version: int = Field(..., examples=[1])
    content_excerpt: str = Field(..., examples=["Baseline Hormonal Profile: AMH 0.82 ng/mL..."])
    content_text: str = Field(..., examples=["Baseline Hormonal Profile..."])
    source_refs: List[str] = Field(..., examples=[["REC-0010"]])


class PaginatedRecordsResponse(BaseModel):
    patient_id: str = Field(..., description="Patient Identifier", examples=["P-101"])
    page: int = Field(..., description="Current page number", examples=[1])
    page_size: int = Field(..., description="Items per page", examples=[20])
    total: int = Field(..., description="Total count matching criteria", examples=[8])
    total_pages: int = Field(..., description="Total pages available", examples=[1])
    records: List[RecordSummaryItem] = Field(..., description="Paginated clinical source records")
    source_refs: List[str] = Field(..., description="All source records in this page", examples=[["REC-0010", "REC-0011"]])


class AskQuestionRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Clinical query regarding patient history or lab findings",
        examples=["What was the peak E2 in Cycle 3?"],
    )


class AskQuestionResponse(BaseModel):
    patient_id: str = Field(..., description="Target patient identifier", examples=["P-101"])
    question: str = Field(..., description="Original question submitted")
    classification: str = Field(
        ...,
        description="Router classification: structured, open_ended, or refusal",
        examples=["structured"],
    )
    status: str = Field(
        ...,
        description="Query outcome: answered, not_found, or refused",
        examples=["answered"],
    )
    answer: str = Field(
        ...,
        description="Synthesized fact-based clinical answer or refusal message",
        examples=["Peak Serum Estradiol (E2) in Cycle 3 was 4890.0 pg/mL on 2024-08-17."],
    )
    claims: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured verified claims backing the answer",
    )
    citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Evidence citations referencing source records",
    )
    source_refs: List[str] = Field(
        default_factory=list,
        description="Provable source IDs",
        examples=[["REC-0205"]],
    )
    matched_rule_id: Optional[str] = Field(
        default=None,
        description="Matched S1 safety rule identifier if blocked or verified",
    )
    hint: Optional[str] = Field(
        default=None,
        description="Clarifying hint for ambiguous questions",
    )

