// TypeScript definitions mirroring backend Pydantic models exactly

export type UserRole = 'doctor' | 'hospital_admin' | 'patient' | 'ova_admin' | 'staff' | 'admin';

export interface User {
  id: string;
  username: string;
  role: UserRole;
  org_id: string;
  hospital_id?: string;
  patient_id?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface ApiError {
  code: string;
  message: string;
  request_id?: string;
  details?: Record<string, unknown>;
}

export interface ApiErrorResponse {
  error: ApiError;
}

export interface PatientListItem {
  id: string;
  name: string;
  dob: string;
  sex: string;
  org_id: string;
  diagnosis?: { primary?: string; secondary?: string } | string | null;
  partner_id?: string | null;
  blood_group?: string | null;
  bmi?: number | null;
  phone_masked?: string | null;
  current_stage: string;
  source_refs: string[];
}

export interface PatientDetailResponse extends PatientListItem {
  access_level?: 'READ_WRITE' | 'READ_ONLY' | null;
  transferred_to_hospital?: string | null;
}

export interface TreatmentEvent {
  id: string;
  kind: string;
  date?: string | null;
  notes?: string | null;
  source_refs?: string[];
}

export interface CycleDetailResponse {
  id: string;
  patient_id: string;
  cycle_no: number;
  type: string; // "OI" | "IUI" | "IVF" | "ICSI" | "FET"
  start_date?: string | null;
  end_date?: string | null;
  outcome?: string | null;
  outcome_badge: string;
  origin_org: string;
  trust_status: string;
  events: TreatmentEvent[];
  stimulation_summary?: Record<string, unknown> | null;
  opu?: Record<string, unknown> | null;
  embryos: Record<string, unknown>[];
  transfers: Record<string, unknown>[];
  pregnancy_outcome?: Record<string, unknown> | null;
  adverse_events: Record<string, unknown>[];
  source_refs: string[];
}

export interface TimelineEvent {
  id: string;
  event_id?: string;
  kind: string;
  canonical_event_name: string;
  stage: string;
  date: string;
  detail?: string;
  hospital: string;
  origin_org?: string;
  source_record_id: string;
  source_refs: string[];
  validation_status: string;
  citation: string;
  cycle_id?: string | null;
  cycle_no?: number | null;
  cycle_assignment?: string;
}

export interface TimelineCycleItem {
  cycle_id: string;
  cycle_no: number;
  type: string;
  start_date?: string | null;
  end_date?: string | null;
  outcome?: string | null;
  outcome_badge: string;
  hospital?: string;
  origin_org: string;
  trust_status: string;
  events_count?: number;
  stages?: string[];
  events: TimelineEvent[];
  source_refs: string[];
}

export interface TimelineYear {
  year: number;
  events_count: number;
  cycles: TimelineCycleItem[];
  events: TimelineEvent[];
}

export interface TimelineResponse {
  patient_id: string;
  stage: string;
  total_cycles: number;
  cycles: TimelineCycleItem[];
  years: TimelineYear[];
  unlinked_events: TimelineEvent[];
  source_refs: string[];
}

export interface CycleComparisonResponse {
  patient_id: string;
  comparison_matrix: Record<string, any>[];
  source_refs: string[];
  conflicts?: any[];
}

export interface EmbryoItem {
  id: string;
  cycle_id: string;
  embryo_label?: string;
  embryo_number?: number;
  day: number;
  grade?: string | null;
  pgt_status?: string | null;
  pgt_result?: string | null;
  fate: 'transferred' | 'frozen' | 'discarded' | string;
  storage_location?: string | null;
  origin_org?: string;
  trust_status?: string;
  notes?: string | null;
  source_refs: string[];
}

export interface EmbryosResponse {
  patient_id: string;
  total_count: number;
  remaining_frozen: number;
  transferred_count: number;
  discarded_count: number;
  embryos: EmbryoItem[];
  source_refs: string[];
}

export interface StimulationDayItem {
  id?: string;
  day_no?: number;
  day_number?: number;
  date: string;
  follicles?: {
    right?: number[];
    left?: number[];
  } | Record<string, any>;
  follicles_right?: number[] | string | null;
  follicles_left?: number[] | string | null;
  e2?: number | null;
  estradiol_pg_ml?: number | null;
  lh?: number | null;
  lh_miu_ml?: number | null;
  p4?: number | null;
  progesterone_ng_ml?: number | null;
  endometrium_mm?: number | null;
  endometrium_thickness_mm?: number | null;
  dose_note?: string | null;
  notes?: string | null;
  origin_org?: string;
  trust_status?: string;
  source_refs: string[];
}

export interface StimulationResponse {
  patient_id: string;
  cycle_id: string;
  summary: Record<string, unknown>;
  days: StimulationDayItem[];
  medications: Record<string, unknown>[];
  trigger?: Record<string, unknown> | null;
  source_refs: string[];
}

export interface FollowupItem {
  id: string;
  patient_id: string;
  cycle_id?: string | null;
  kind: string;
  name: string;
  status: 'pending' | 'scheduled' | 'overdue' | 'done' | 'cancelled';
  due_date: string;
  source_id: string;
  source_refs: string[];
}

export interface FollowupsResponse {
  patient_id: string;
  as_of_date: string;
  counts: {
    overdue: number;
    scheduled: number;
    pending: number;
    done: number;
  };
  overdue: FollowupItem[];
  scheduled: FollowupItem[];
  pending: FollowupItem[];
  done: FollowupItem[];
  source_refs: string[];
}

export interface FollowupUpdateRequest {
  status?: 'pending' | 'scheduled' | 'overdue' | 'done' | 'cancelled';
  due_date?: string;
  name?: string;
}

export interface Citation {
  source_id: string;
  type: string;
  claim_id?: string | null;
  date?: string | null;
  origin?: string | null;
  trust?: string | null;
  span?: {
    page?: number | null;
    start: number;
    end: number;
  } | null;
  field_path?: string | null;
  matching_text?: string | null;
}

export interface Claim {
  claim_id: string;
  type: 'FACT' | 'ABSENCE' | 'CONFLICT';
  subject: string;
  predicate: string;
  value?: unknown;
  unit?: string | null;
  cycle_id?: string | null;
  event_date?: string | null;
  field_path?: string | null;
  display_text: string;
  citations: Citation[];
  status?: 'VERIFIED' | 'BLOCKED';
  block_reason?: string | null;
  assurance_tier?: string | null;
}

export interface SummarySection {
  section_title?: string;
  name?: string;
  text?: string;
  claims?: Claim[];
  statements?: any[];
  mode?: 'llm_grounded' | 'deterministic_fallback' | 'ai_validated';
  degraded_reason?: string | null;
}

export interface ValidatorReport {
  total_claims: number;
  verified_count: number;
  blocked_count: number;
  degradation_ratio: number;
  mode: string;
  findings: Array<{
    claim_id: string;
    code: string;
    message: string;
  }>;
}

export interface SummaryResponse {
  id: string;
  patient_id: string;
  version: number;
  data_version: string;
  generated_at: string;
  length: 'snapshot' | 'detailed';
  is_stale: boolean;
  cache_hit: boolean;
  content: {
    sections: Record<string, SummarySection>;
    snapshot_text?: string;
    conflicts_detected: Array<{
      conflict_type: string;
      field: string;
      items: Array<Record<string, unknown>>;
      source_refs: string[];
    }>;
    missing_items: Array<{
      item: string;
      reason: string;
      rule_id: string;
      source_refs: string[];
    }>;
  };
  validator_report?: ValidatorReport;
}

export interface SummaryStatusResponse {
  patient_id: string;
  ready: boolean;
  is_stale: boolean;
  latest_version?: number | null;
  data_version: string;
  generated_at?: string | null;
}

export interface SourceRecordDetailResponse {
  id: string;
  patient_id: string;
  cycle_id?: string | null;
  type: string;
  date: string;
  author?: string | null;
  origin_org: string;
  trust_status: string;
  version: number;
  content_text: string;
  source_refs: string[];
}

export interface RecordSummaryItem {
  id: string;
  patient_id: string;
  cycle_id?: string | null;
  type: string;
  date: string;
  author?: string | null;
  origin_org: string;
  trust_status: string;
  version: number;
  content_excerpt: string;
  content_text: string;
  source_refs: string[];
}

export interface PaginatedRecordsResponse {
  patient_id: string;
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  records: RecordSummaryItem[];
  source_refs: string[];
}

export interface AskQuestionRequest {
  question: string;
}

export interface AskQuestionResponse {
  patient_id: string;
  question: string;
  classification: 'structured' | 'open_ended' | 'refusal';
  status: 'answered' | 'not_found' | 'refused' | 'BLOCKED_S1';
  answer: string;
  claims: Claim[];
  citations: Citation[];
  source_refs: string[];
  matched_rule_id?: string | null;
  hint?: string | null;
}

export interface EvaluationMetrics {
  fact_recall: number;
  citation_accuracy: number;
  unsupported_claim_rate: number;
  blocked_claim_rate: number;
  conflict_recall: number;
  conflict_false_positive_rate: number;
  absence_recall: number;
  injection_pass_rate: number;
  avg_latency_seconds: number;
  total_claims_generated: number;
  total_claims_verified: number;
  total_claims_blocked: number;
}

export interface PatientEvalResult {
  patient_id: string;
  patient_name: string;
  latency_seconds: number;
  displayed_claims_count: number;
  total_claims: number;
  verified_claims: number;
  blocked_claims: number;
  blocked_reasons: Record<string, number>;
  gold_facts_total: number;
  gold_facts_matched: number;
  fact_recall: number;
  total_citations: number;
  accurate_citations: number;
  citation_accuracy: number;
  unsupported_claims_count: number;
  unsupported_claim_rate: number;
  gold_conflicts_total: number;
  gold_conflicts_matched: number;
  detected_conflicts_total: number;
  conflict_recall: number;
  conflict_fp_rate: number;
  gold_absences_total: number;
  gold_absences_matched: number;
  absence_recall: number;
  injection_passed: boolean;
}

export interface EvaluationResponse {
  run_id: string;
  run_at: string;
  provider: string;
  is_adversarial: boolean;
  summary_metrics: EvaluationMetrics;
  blocked_reasons: Record<string, number>;
  per_patient: PatientEvalResult[];
}

export interface ImportBatch {
  id: string;
  uploaded_by: string;
  org_id: string;
  origin_org: string;
  status: 'quarantined' | 'confirmed' | 'rejected';
  target_patient_id?: string | null;
  created_at: string;
  confirmed_at?: string | null;
  validation_report_json?: {
    records_count: number;
    cycles_count: number;
    syntax_valid: boolean;
    warnings: string[];
  } | null;
  identity_match_json?: {
    best_match?: {
      patient_id: string;
      patient_name: string;
      score: number;
      confidence: 'high' | 'medium' | 'low' | 'none';
      needs_staff_confirmation: boolean;
      notes: string;
      criteria: {
        name_match: boolean;
        dob_match: boolean;
        phone_match: boolean;
      };
    };
    candidates?: any[];
  } | null;
  cycle_suggestions_json?: any[] | null;
  raw_payload_json?: any;
}

export interface ConsentItem {
  id: string;
  patient_id: string;
  org_id: string;
  granted_to_hospital_id?: string | null;
  purpose?: string | null;
  scope?: string | null;
  consent_type: string;
  status: string;
  granted_at: string;
  expires_at?: string | null;
  revoked_at?: string | null;
  granted_by?: string | null;
  recorded_on_behalf?: boolean;
  created_at?: string | null;
}

export interface IdentityLinkItem {
  id: string;
  internal_patient_id: string;
  external_patient_id: string;
  external_org_name: string;
  confidence_score: number;
  status: string;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
}

export interface RecordUploadResponse {
  id: string;
  patient_id: string;
  type: string;
  date?: string | null;
  file_name: string;
  mime_type: string;
  content_hash: string;
  processing_status: 'UPLOADED' | 'EXTRACTING' | 'VALIDATED' | 'FAILED' | 'NEEDS_OCR';
  extracted_char_count: number;
  warnings: string[];
  content_text?: string | null;
  uploaded_at: string;
}

export interface RecordStatusResponse {
  id: string;
  patient_id: string;
  file_name: string;
  mime_type: string;
  content_hash: string;
  processing_status: 'UPLOADED' | 'EXTRACTING' | 'VALIDATED' | 'FAILED' | 'NEEDS_OCR';
  error_message?: string | null;
  warnings: string[];
  uploaded_at: string;
  processed_at?: string | null;
  verified_at?: string | null;
}

export interface TreatmentJourneyStage {
  stage: string;
  label: string;
  status: 'COMPLETED' | 'IN_PROGRESS' | 'PENDING' | 'NOT_STARTED';
  date?: string | null;
  detail?: string | null;
}

export interface DashboardCounts {
  verified_claims: number;
  flagged_claims: number;
  rejected_candidates: number;
  open_conflicts: number;
  open_gaps: number;
  source_records: number;
  hospitals: number;
}

export interface PatientDashboardResponse {
  patient_id: string;
  patient_name: string;
  cycle_id?: string | null;
  cycle_type?: string | null;
  treatment_journey: TreatmentJourneyStage[];
  counts: DashboardCounts;
  distinct_hospitals: string[];
  filter_links: {
    verified_claims: string;
    flagged_claims: string;
    rejected_candidates: string;
    open_conflicts: string;
    open_gaps: string;
    source_records: string;
    hospitals: string;
  };
}

export interface ValidationCheckItem {
  label: string;
  passed: boolean;
  detail: string;
}

export interface ClaimEvidenceResponse {
  claim: {
    id: string;
    patient_id: string;
    hospital_id?: string | null;
    source_record_id: string;
    field: string;
    value_text?: string | null;
    value_num?: number | null;
    unit?: string | null;
    event_date?: string | null;
    validation_status: string;
    created_at?: string | null;
  };
  source_record: {
    id: string;
    hospital?: string | null;
    date?: string | null;
    uploader?: string | null;
    type?: string | null;
    origin_org?: string | null;
  };
  evidence: {
    full_text: string;
    highlighted_text: string;
    prefix: string;
    suffix: string;
    evidence_sentence: string;
    span_start: number;
    span_end: number;
  };
  validation_checks: ValidationCheckItem[];
}

export interface ClinicalClaimItem {
  id: string;
  patient_id: string;
  hospital_id?: string | null;
  source_record_id: string;
  cycle_id?: string | null;
  cycle_assignment?: string | null;
  field: string;
  value_text?: string | null;
  value_num?: number | null;
  unit?: string | null;
  event_date?: string | null;
  span_start?: number | null;
  span_end?: number | null;
  evidence_text?: string | null;
  extraction_method?: string | null;
  validation_status: 'VERIFIED' | 'FLAGGED' | 'REJECTED' | 'UNCHECKED';
  validation_checks?: Record<string, any> | null;
  reason_codes?: string[];
  uploaded_by?: string | null;
  created_at?: string | null;
  materialized_table?: string | null;
  materialized_row_id?: string | null;
}

export interface ConflictRecordItem {
  id: string;
  patient_id: string;
  field: string;
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
  claim_id_a?: string;
  claim_id_b?: string;
  claim_a_id?: string;
  claim_b_id?: string;
  value_a?: string | null;
  value_b?: string | null;
  unit_a?: string | null;
  unit_b?: string | null;
  date_a?: string | null;
  date_b?: string | null;
  hospital_a?: string | null;
  hospital_b?: string | null;
  source_id_a?: string | null;
  source_id_b?: string | null;
  source_a?: string | null;
  source_b?: string | null;
  evidence_text_a?: string | null;
  evidence_text_b?: string | null;
  display_text: string;
  ack_by?: string | null;
  ack_at?: string | null;
  ack_note?: string | null;
  acknowledged_by?: string | null;
  acknowledged_at?: string | null;
  note?: string | null;
  created_at?: string | null;
}

export interface DocumentationGapItem {
  id: string;
  patient_id: string;
  rule_id: string;
  expected_item: string;
  trigger_claim_id?: string | null;
  trigger_event?: string | null;
  window_days?: number | null;
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
  ack_by?: string | null;
  ack_at?: string | null;
  ack_note?: string | null;
  created_at?: string | null;
}

export interface TransferRequestItem {
  id: string;
  patient_id: string;
  patient_name?: string | null;
  from_hospital_id: string;
  to_hospital_id: string;
  requested_by: string;
  status: string;
  consent_id?: string | null;
  has_active_consent?: boolean | null;
  decided_by?: string | null;
  decided_at?: string | null;
  reason?: string | null;
  created_at?: string | null;
}
export interface AuditLogItem {
  id: string;
  org_id: string;
  hospital_id?: string | null;
  user_id: string;
  action: string;
  event_type?: string | null;
  patient_id?: string | null;
  outcome?: string | null;
  details?: Record<string, unknown> | null;
  at: string;
}
