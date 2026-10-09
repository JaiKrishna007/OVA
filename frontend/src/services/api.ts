import type {
  TokenResponse,
  LoginRequest,
  User,
  PatientListItem,
  PatientDetailResponse,
  TimelineResponse,
  CycleDetailResponse,
  CycleComparisonResponse,
  EmbryosResponse,
  StimulationResponse,
  FollowupsResponse,
  FollowupUpdateRequest,
  FollowupItem,
  SummaryResponse,
  SummaryStatusResponse,
  SourceRecordDetailResponse,
  PaginatedRecordsResponse,
  AskQuestionResponse,
  ApiErrorResponse,
  EvaluationResponse,
  ImportBatch,
  ConsentItem,
  IdentityLinkItem,
  RecordUploadResponse,
  RecordStatusResponse,
  PatientDashboardResponse,
  ClaimEvidenceResponse,
  ClinicalClaimItem,
  ConflictRecordItem,
  DocumentationGapItem,
  TransferRequestItem,
  AuditLogItem,
} from '../types/api';

const API_ORIGIN = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '');
const BASE_URL = API_ORIGIN ? `${API_ORIGIN}/api/v1` : '/api/v1';

export class ApiClientError extends Error {
  code: string;
  requestId?: string;
  status: number;

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('access_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData: ApiErrorResponse | null = null;
    try {
      errorData = await response.json();
    } catch {
      // response wasn't JSON
    }

    const code = errorData?.error?.code || `HTTP_${response.status}`;
    const message = errorData?.error?.message || response.statusText || 'An unexpected error occurred';
    const requestId = errorData?.error?.request_id;

    throw new ApiClientError(response.status, code, message, requestId);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const authApi = {
  login: async (credentials: LoginRequest): Promise<TokenResponse> => {
    return request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  },

  me: async (): Promise<User> => {
    return request<User>('/auth/me');
  },

  logout: async (): Promise<void> => {
    await request<void>('/auth/logout', { method: 'POST' }).catch(() => {});
  },
};

export const patientsApi = {
  search: async (query?: string): Promise<PatientListItem[]> => {
    const params = query ? `?q=${encodeURIComponent(query)}` : '';
    return request<PatientListItem[]>(`/patients${params}`);
  },

  getById: async (patientId: string): Promise<PatientDetailResponse> => {
    return request<PatientDetailResponse>(`/patients/${encodeURIComponent(patientId)}`);
  },

  getTimeline: async (patientId: string): Promise<TimelineResponse> => {
    return request<TimelineResponse>(`/patients/${encodeURIComponent(patientId)}/timeline`);
  },

  getCycleDetail: async (patientId: string, cycleId: string): Promise<CycleDetailResponse> => {
    return request<CycleDetailResponse>(
      `/patients/${encodeURIComponent(patientId)}/cycles/${encodeURIComponent(cycleId)}`
    );
  },

  getCycleComparison: async (patientId: string): Promise<CycleComparisonResponse> => {
    return request<CycleComparisonResponse>(
      `/patients/${encodeURIComponent(patientId)}/cycle-comparison`
    );
  },

  getEmbryos: async (patientId: string): Promise<EmbryosResponse> => {
    return request<EmbryosResponse>(`/patients/${encodeURIComponent(patientId)}/embryos`);
  },

  getStimulation: async (patientId: string, cycleId: string): Promise<StimulationResponse> => {
    return request<StimulationResponse>(
      `/patients/${encodeURIComponent(patientId)}/stimulation/${encodeURIComponent(cycleId)}`
    );
  },

  getFollowups: async (patientId: string): Promise<FollowupsResponse> => {
    return request<FollowupsResponse>(`/patients/${encodeURIComponent(patientId)}/followups`);
  },

  updateFollowup: async (followupId: string, data: FollowupUpdateRequest): Promise<FollowupItem> => {
    return request<FollowupItem>(`/followups/${encodeURIComponent(followupId)}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  getSummary: async (
    patientId: string,
    length: 'snapshot' | 'detailed' = 'detailed'
  ): Promise<SummaryResponse> => {
    return request<SummaryResponse>(
      `/patients/${encodeURIComponent(patientId)}/summary?length=${length}`
    );
  },

  getSummaryStatus: async (patientId: string): Promise<SummaryStatusResponse> => {
    return request<SummaryStatusResponse>(
      `/patients/${encodeURIComponent(patientId)}/summary/status`
    );
  },

  regenerateSummary: async (
    patientId: string,
    sections?: string[]
  ): Promise<SummaryResponse> => {
    return request<SummaryResponse>(
      `/patients/${encodeURIComponent(patientId)}/summary/regenerate`,
      {
        method: 'POST',
        body: JSON.stringify({ sections }),
      }
    );
  },

  getRecords: async (
    patientId: string,
    page: number = 1,
    pageSize: number = 20,
    cycleId?: string,
    type?: string
  ): Promise<PaginatedRecordsResponse> => {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });
    if (cycleId) params.append('cycle_id', cycleId);
    if (type) params.append('type', type);

    return request<PaginatedRecordsResponse>(
      `/patients/${encodeURIComponent(patientId)}/records?${params.toString()}`
    );
  },

  askQuestion: async (
    patientId: string,
    question: string
  ): Promise<AskQuestionResponse> => {
    return request<AskQuestionResponse>(
      `/patients/${encodeURIComponent(patientId)}/ask`,
      {
        method: 'POST',
        body: JSON.stringify({ question }),
      }
    );
  },

  downloadBrief: async (patientId: string): Promise<Blob> => {
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(`${BASE_URL}/patients/${encodeURIComponent(patientId)}/brief`, {
      headers,
    });
    if (!response.ok) {
      let errorData: ApiErrorResponse | null = null;
      try {
        errorData = await response.json();
      } catch {
        // non-JSON error
      }
      const code = errorData?.error?.code || `HTTP_${response.status}`;
      const message = errorData?.error?.message || response.statusText || 'Failed to download brief';
      throw new ApiClientError(response.status, code, message, errorData?.error?.request_id);
    }
    return response.blob();
  },

  uploadRecord: async (
    patientId: string,
    formData: FormData
  ): Promise<RecordUploadResponse> => {
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(`${BASE_URL}/patients/${encodeURIComponent(patientId)}/records/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });
    if (!response.ok) {
      let errorData: ApiErrorResponse | null = null;
      try {
        errorData = await response.json();
      } catch {
        // non-JSON
      }
      const code = errorData?.error?.code || `HTTP_${response.status}`;
      const message = errorData?.error?.message || response.statusText || 'Failed to upload record';
      throw new ApiClientError(response.status, code, message, errorData?.error?.request_id);
    }
    return response.json();
  },

  getDashboard: async (patientId: string): Promise<PatientDashboardResponse> => {
    return request<PatientDashboardResponse>(`/patients/${encodeURIComponent(patientId)}/dashboard`);
  },

  getConflicts: async (patientId: string, status?: string): Promise<ConflictRecordItem[]> => {
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    return request<ConflictRecordItem[]>(`/patients/${encodeURIComponent(patientId)}/conflicts${q}`);
  },

  getGaps: async (patientId: string, status?: string): Promise<DocumentationGapItem[]> => {
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    return request<DocumentationGapItem[]>(`/patients/${encodeURIComponent(patientId)}/gaps${q}`);
  },
};

export const recordsApi = {
  getById: async (sourceId: string): Promise<SourceRecordDetailResponse> => {
    return request<SourceRecordDetailResponse>(`/records/${encodeURIComponent(sourceId)}`);
  },
  getStatus: async (sourceId: string): Promise<RecordStatusResponse> => {
    return request<RecordStatusResponse>(`/records/${encodeURIComponent(sourceId)}/status`);
  },
};

export const summariesApi = {
  submitFeedback: async (
    summaryId: string,
    statementRef: string,
    type: string = 'incorrect_fact',
    comment?: string
  ): Promise<Record<string, unknown>> => {
    return request<Record<string, unknown>>(`/summaries/${encodeURIComponent(summaryId)}/feedback`, {
      method: 'POST',
      body: JSON.stringify({
        statement_ref: statementRef,
        type,
        comment,
      }),
    });
  },
};

export const evalApi = {
  getLatest: async (): Promise<EvaluationResponse> => {
    return request<EvaluationResponse>('/eval/latest');
  },
  runEval: async (adversarial: boolean = false): Promise<EvaluationResponse> => {
    return request<EvaluationResponse>(`/eval/run?adversarial=${adversarial}`, {
      method: 'POST',
    });
  },
};

export const importApi = {
  uploadBatch: async (payload: any): Promise<ImportBatch> => {
    return request<ImportBatch>('/import', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listBatches: async (status?: string): Promise<ImportBatch[]> => {
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    return request<ImportBatch[]>(`/import${q}`);
  },
  getBatch: async (batchId: string): Promise<ImportBatch> => {
    return request<ImportBatch>(`/import/${encodeURIComponent(batchId)}`);
  },
  confirmBatch: async (
    batchId: string,
    confirmData: { target_patient_id: string; confirm_identity?: boolean; override_reasons?: string }
  ): Promise<ImportBatch> => {
    return request<ImportBatch>(`/import/${encodeURIComponent(batchId)}/confirm`, {
      method: 'POST',
      body: JSON.stringify(confirmData),
    });
  },
};

export const consentsApi = {
  recordConsent: async (data: {
    patient_id: string;
    target_hospital_id?: string;
    purpose?: string;
    scope?: string;
    expires_at?: string;
    recorded_on_behalf?: boolean;
    consent_type?: string;
    granted_by?: string;
    status?: string;
  }): Promise<ConsentItem> => {
    return request<ConsentItem>('/consents', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  listConsents: async (patientId?: string): Promise<ConsentItem[]> => {
    if (patientId) {
      return request<ConsentItem[]>(`/patients/${encodeURIComponent(patientId)}/consents`);
    }
    return request<ConsentItem[]>('/consents');
  },
  revokeConsent: async (consentId: string): Promise<ConsentItem> => {
    return request<ConsentItem>(`/consents/${encodeURIComponent(consentId)}`, {
      method: 'DELETE',
    });
  },
  listIdentityLinks: async (patientId?: string): Promise<IdentityLinkItem[]> => {
    const q = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : '';
    return request<IdentityLinkItem[]>(`/identity-links${q}`);
  },
  listTransferRequests: async (patientId?: string): Promise<TransferRequestItem[]> => {
    const q = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : '';
    return request<TransferRequestItem[]>(`/transfers${q}`);
  },
};

export const transfersApi = {
  createTransfer: async (data: {
    patient_id: string;
    from_hospital_id?: string;
    to_hospital_id: string;
    reason?: string;
  }): Promise<TransferRequestItem> => {
    return request<TransferRequestItem>('/transfers', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  listTransfers: async (params?: {
    patient_id?: string;
    direction?: 'incoming' | 'outgoing';
    status?: string;
  }): Promise<TransferRequestItem[]> => {
    const query = new URLSearchParams();
    if (params?.patient_id) query.append('patient_id', params.patient_id);
    if (params?.direction) query.append('direction', params.direction);
    if (params?.status) query.append('status', params.status);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return request<TransferRequestItem[]>(`/transfers${qs}`);
  },
  acceptTransfer: async (transferId: string): Promise<TransferRequestItem> => {
    return request<TransferRequestItem>(`/transfers/${encodeURIComponent(transferId)}/accept`, {
      method: 'POST',
    });
  },
  rejectTransfer: async (transferId: string, reason?: string): Promise<TransferRequestItem> => {
    return request<TransferRequestItem>(`/transfers/${encodeURIComponent(transferId)}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  },
  cancelTransfer: async (transferId: string): Promise<TransferRequestItem> => {
    return request<TransferRequestItem>(`/transfers/${encodeURIComponent(transferId)}/cancel`, {
      method: 'POST',
    });
  },
  clearTransfers: async (): Promise<{ status: string; cleared_transfers_count: number; message: string }> => {
    return request<{ status: string; cleared_transfers_count: number; message: string }>('/transfers/clear', {
      method: 'POST',
    });
  },
};

export const systemApi = {
  getHealth: async (): Promise<{ status: string; llm_provider?: string }> => {
    return request<{ status: string; llm_provider?: string }>('/health');
  },
};

export const claimsApi = {
  getEvidence: async (claimId: string): Promise<ClaimEvidenceResponse> => {
    return request<ClaimEvidenceResponse>(`/claims/${encodeURIComponent(claimId)}/evidence`);
  },
  list: async (params?: { patient_id?: string; status?: string; field?: string }): Promise<ClinicalClaimItem[]> => {
    const searchParams = new URLSearchParams();
    if (params?.patient_id) searchParams.append('patient_id', params.patient_id);
    if (params?.status) searchParams.append('status', params.status);
    if (params?.field) searchParams.append('field', params.field);
    const q = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return request<ClinicalClaimItem[]>(`/claims${q}`);
  },
  accept: async (claimId: string, note?: string): Promise<{ status: string; claim_id: string }> => {
    return request<{ status: string; claim_id: string }>(`/claims/${encodeURIComponent(claimId)}/accept`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    });
  },
  reject: async (claimId: string, note?: string): Promise<{ status: string; claim_id: string }> => {
    return request<{ status: string; claim_id: string }>(`/claims/${encodeURIComponent(claimId)}/reject`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    });
  },
};

export const conflictsApi = {
  list: async (patientId?: string, status?: string): Promise<ConflictRecordItem[]> => {
    if (patientId) {
      return patientsApi.getConflicts(patientId, status);
    }
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    return request<ConflictRecordItem[]>(`/conflicts${q}`);
  },
  acknowledge: async (conflictId: string, note: string): Promise<ConflictRecordItem> => {
    return request<ConflictRecordItem>(`/conflicts/${encodeURIComponent(conflictId)}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    });
  },
};

export const gapsApi = {
  list: async (patientId?: string, status?: string): Promise<DocumentationGapItem[]> => {
    if (patientId) {
      return patientsApi.getGaps(patientId, status);
    }
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    return request<DocumentationGapItem[]>(`/gaps${q}`);
  },
  acknowledge: async (gapId: string, note: string): Promise<DocumentationGapItem> => {
    return request<DocumentationGapItem>(`/gaps/${encodeURIComponent(gapId)}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    });
  },
};

export const auditApi = {
  list: async (params?: {
    limit?: number;
    patient_id?: string;
    user_id?: string;
    event_type?: string;
    outcome?: string;
    date_from?: string;
    date_to?: string;
  }): Promise<AuditLogItem[]> => {
    const q = new URLSearchParams();
    if (params?.limit)       q.append('limit', params.limit.toString());
    if (params?.patient_id)  q.append('patient_id', params.patient_id);
    if (params?.user_id)     q.append('user_id', params.user_id);
    if (params?.event_type)  q.append('event_type', params.event_type);
    if (params?.outcome)     q.append('outcome', params.outcome);
    if (params?.date_from)   q.append('date_from', params.date_from);
    if (params?.date_to)     q.append('date_to', params.date_to);
    const qs = q.toString() ? `?${q.toString()}` : '';
    return request<AuditLogItem[]>(`/audit${qs}`);
  },

  listForPatient: async (patientId: string, params?: {
    limit?: number;
    event_type?: string;
  }): Promise<AuditLogItem[]> => {
    const q = new URLSearchParams();
    if (params?.limit)       q.append('limit', params.limit.toString());
    if (params?.event_type)  q.append('event_type', params.event_type);
    const qs = q.toString() ? `?${q.toString()}` : '';
    return request<AuditLogItem[]>(`/audit/patient/${encodeURIComponent(patientId)}${qs}`);
  },
};




