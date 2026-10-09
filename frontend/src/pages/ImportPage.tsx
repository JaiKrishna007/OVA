import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  RefreshCw,
  ArrowRight,
  Database,
  Building,
  Layers,
} from 'lucide-react';
import { importApi, consentsApi, ApiClientError } from '../services/api';
import type { ImportBatch, ConsentItem } from '../types/api';

const SAMPLE_TRANSFER_PAYLOAD = {
  origin_org: "St. Jude Fertility Clinic",
  patient: {
    external_id: "SJ-9981",
    name: "Priya S.",
    dob: "1991-05-20",
    phone: "+91-9845012341",
  },
  records: [
    {
      type: "external_summary",
      date: "2024-01-15",
      author: "Dr. Miller",
      content_text: "Prior IVF cycle 1 at St. Jude. 8 oocytes retrieved, 2 blastocysts frozen.",
    },
  ],
  cycles: [
    {
      cycle_no: 1,
      type: "IVF",
      start_date: "2024-01-02",
      end_date: "2024-01-20",
      outcome: "completed",
    },
  ],
};

const SAMPLE_NAME_ONLY_PAYLOAD = {
  origin_org: "City Health General Hospital",
  patient: {
    external_id: "CHG-102",
    name: "Priya S.",
    dob: "1980-01-01", // Different DOB
    phone: "+91-9999999999", // Different phone
  },
  records: [
    {
      type: "external_consult",
      date: "2023-04-10",
      author: "Dr. John Doe",
      content_text: "General consultation note for patient named Priya S.",
    },
  ],
  cycles: [],
};

export const ImportPage: React.FC = () => {
  const navigate = useNavigate();
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [selectedBatch, setSelectedBatch] = useState<ImportBatch | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Upload state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [jsonInput, setJsonInput] = useState(JSON.stringify(SAMPLE_TRANSFER_PAYLOAD, null, 2));
  const [uploading, setUploading] = useState(false);

  // Confirmation state
  const [targetPatientId, setTargetPatientId] = useState('');
  const [confirmIdentity, setConfirmIdentity] = useState(false);
  const [overrideReasons, setOverrideReasons] = useState('');
  const [confirming, setConfirming] = useState(false);

  // Consent checking state
  const [consents, setConsents] = useState<ConsentItem[]>([]);
  const [recordingConsent, setRecordingConsent] = useState(false);

  const fetchBatches = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await importApi.listBatches();
      setBatches(data);
      if (data.length > 0 && !selectedBatchId) {
        setSelectedBatchId(data[0].id);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load import batches.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
  }, []);

  useEffect(() => {
    if (!selectedBatchId) {
      setSelectedBatch(null);
      return;
    }
    const loadBatchDetail = async () => {
      try {
        const b = await importApi.getBatch(selectedBatchId);
        setSelectedBatch(b);
        const bestCandidate = b.identity_match_json?.best_match?.patient_id;
        const candidateId = b.target_patient_id || bestCandidate || 'P-101';
        setTargetPatientId(candidateId);
        setConfirmIdentity(false);

        // Fetch consents for this candidate
        if (candidateId) {
          const cList = await consentsApi.listConsents(candidateId);
          setConsents(cList);
        }
      } catch (err: any) {
        setErrorMsg(err.message || 'Failed to fetch batch detail.');
      }
    };
    loadBatchDetail();
  }, [selectedBatchId]);

  const handlePatientSelectChange = async (newId: string) => {
    setTargetPatientId(newId);
    try {
      const cList = await consentsApi.listConsents(newId);
      setConsents(cList);
    } catch (err) {
      console.error(err);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);
    setUploading(true);
    try {
      const parsed = JSON.parse(jsonInput);
      const newBatch = await importApi.uploadBatch(parsed);
      setSuccessMsg(`Quarantine batch ${newBatch.id} created successfully.`);
      setShowUploadModal(false);
      await fetchBatches();
      setSelectedBatchId(newBatch.id);
    } catch (err: any) {
      setErrorMsg(err.message || 'Invalid JSON format or upload rejected.');
    } finally {
      setUploading(false);
    }
  };

  const handleRecordConsent = async () => {
    if (!targetPatientId) return;
    setRecordingConsent(true);
    setErrorMsg(null);
    try {
      await consentsApi.recordConsent({
        patient_id: targetPatientId,
        consent_type: 'external_transfer',
        granted_by: `${selectedBatch?.raw_payload_json?.patient?.name || 'Patient'} (Authorized)`,
        status: 'active',
      });
      const cList = await consentsApi.listConsents(targetPatientId);
      setConsents(cList);
      setSuccessMsg(`Active transfer consent recorded for ${targetPatientId}.`);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to record consent.');
    } finally {
      setRecordingConsent(false);
    }
  };

  const handleConfirmMerge = async () => {
    if (!selectedBatchId || !targetPatientId) return;
    setConfirming(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await importApi.confirmBatch(selectedBatchId, {
        target_patient_id: targetPatientId,
        confirm_identity: confirmIdentity,
        override_reasons: overrideReasons || undefined,
      });
      setSelectedBatch(res);
      setSuccessMsg(
        `Batch ${res.id} successfully confirmed! Records committed with origin "${res.origin_org}" and trust status "external_unverified". Patient summary marked stale.`
      );
      await fetchBatches();
    } catch (err: any) {
      if (err instanceof ApiClientError) {
        if (err.status === 409) {
          setErrorMsg(
            `[409 Conflict] Active patient consent is strictly required before merging external records into ${targetPatientId}. Please record consent first.`
          );
        } else {
          setErrorMsg(`[Error ${err.status}] ${err.message}`);
        }
      } else {
        setErrorMsg(err.message || 'Failed to confirm batch.');
      }
    } finally {
      setConfirming(false);
    }
  };

  const hasActiveConsent = consents.some((c) => c.status === 'active');
  const bestMatch = selectedBatch?.identity_match_json?.best_match;

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-[#FFF0ED] text-[#B84E4E] border border-[#FBC4AB] flex items-center justify-center font-bold">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Staff Transfer Flow & Quarantine Queue
              </h1>
              <p className="text-xs text-slate-500">
                Staff-only ingest of external clinic records into a quarantine store with strict consent & identity matching verification.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchBatches}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg shadow-2xs transition-all cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh Queue
          </button>
          <button
            type="button"
            onClick={() => setShowUploadModal(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-[#E07A5F] hover:bg-[#D0694E] rounded-lg shadow-xs transition-all cursor-pointer"
          >
            <UploadCloud className="w-4 h-4" />
            Upload External Batch
          </button>
        </div>
      </div>

      {/* Global Alerts */}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-start gap-3 shadow-2xs animate-fade-in">
          <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 font-medium leading-relaxed">{errorMsg}</div>
        </div>
      )}

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-3 shadow-2xs animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 font-medium leading-relaxed">{successMsg}</div>
        </div>
      )}

      {/* Split Queue Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Review Queue List (4 cols) */}
        <div className="lg:col-span-4 space-y-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
              Quarantine Queue ({batches.length})
            </span>
            <span className="text-[11px] text-slate-500">Ordered by recency</span>
          </div>

          <div className="space-y-2.5 max-h-[700px] overflow-y-auto pr-1">
            {batches.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500 text-xs">
                No import batches currently in queue.
              </div>
            ) : (
              batches.map((b) => {
                const isSelected = selectedBatchId === b.id;
                const isConfirmed = b.status === 'confirmed';
                return (
                  <div
                    key={b.id}
                    onClick={() => setSelectedBatchId(b.id)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer bg-white shadow-2xs space-y-2 ${
                      isSelected
                        ? 'border-[#F8AD9D] ring-2 ring-[#F08080]/30 bg-[#FFFDFB]'
                        : 'border-slate-200 hover:border-[#FBC4AB]'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-800">
                        {b.id}
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                          isConfirmed
                            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                            : 'bg-amber-50 text-amber-800 border border-amber-200'
                        }`}
                      >
                        {b.status}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-900">
                      <Building className="w-3.5 h-3.5 text-slate-400" />
                      <span className="truncate">{b.origin_org}</span>
                    </div>

                    <div className="text-[11px] text-slate-500 flex items-center justify-between pt-1 border-t border-slate-100">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-400" />
                        {new Date(b.created_at).toLocaleDateString()}
                      </span>
                      <span>
                        {b.validation_report_json?.records_count ?? 0} recs •{' '}
                        {b.validation_report_json?.cycles_count ?? 0} cycles
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right: Selected Batch Review & Confirmation Panel (8 cols) */}
        <div className="lg:col-span-8">
          {selectedBatch ? (
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-6">
              {/* Batch Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                      Batch Details
                    </span>
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-800">
                      {selectedBatch.id}
                    </span>
                  </div>
                  <h2 className="text-lg font-bold text-slate-900 mt-1">
                    {selectedBatch.origin_org}
                  </h2>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-bold px-2.5 py-1 rounded-full uppercase ${
                      selectedBatch.status === 'confirmed'
                        ? 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                        : 'bg-amber-100 text-amber-900 border border-amber-300'
                    }`}
                  >
                    {selectedBatch.status}
                  </span>
                  {selectedBatch.target_patient_id && (
                    <button
                      type="button"
                      onClick={() => navigate(`/patients/${selectedBatch.target_patient_id}`)}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-[#A83232] hover:underline"
                    >
                      <span>Chart: {selectedBatch.target_patient_id}</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>

              {/* 1. Structural Validation Report */}
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-slate-500" />
                  Structural Validation Report
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center">
                    <span className="block text-[11px] text-slate-500">Syntax</span>
                    <span className="text-xs font-bold text-emerald-700">
                      {selectedBatch.validation_report_json?.syntax_valid ? 'Valid JSON' : 'Errors'}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center">
                    <span className="block text-[11px] text-slate-500">Records</span>
                    <span className="text-sm font-bold text-slate-800">
                      {selectedBatch.validation_report_json?.records_count ?? 0}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center">
                    <span className="block text-[11px] text-slate-500">Cycles</span>
                    <span className="text-sm font-bold text-slate-800">
                      {selectedBatch.validation_report_json?.cycles_count ?? 0}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center">
                    <span className="block text-[11px] text-slate-500">Cycle Suggestions</span>
                    <span className="text-sm font-bold text-slate-800">
                      {selectedBatch.cycle_suggestions_json?.length ?? 0}
                    </span>
                  </div>
                </div>
              </div>

              {/* 2. Identity Match & Anti-Auto-Merge Rules */}
              <div className="space-y-3 p-4 rounded-xl bg-slate-50 border border-slate-200">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <UserCheck className="w-4 h-4 text-[#E07A5F]" />
                    Cross-Clinic Identity Match Confidence
                  </h3>
                  {bestMatch && (
                    <span
                      className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                        bestMatch.confidence === 'high'
                          ? 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                          : bestMatch.confidence === 'medium'
                          ? 'bg-amber-100 text-amber-900 border border-amber-300'
                          : 'bg-red-100 text-red-900 border border-red-300'
                      }`}
                    >
                      {bestMatch.confidence.toUpperCase()} CONFIDENCE ({(bestMatch.score * 100).toFixed(0)}%)
                    </span>
                  )}
                </div>

                {bestMatch ? (
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between bg-white p-2.5 rounded-lg border border-slate-200">
                      <span className="text-slate-600">Matched Candidate:</span>
                      <span className="font-bold text-slate-900">
                        {bestMatch.patient_name} ({bestMatch.patient_id})
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      <div className="p-2 bg-white rounded border border-slate-200 text-center">
                        <span className="text-[10px] text-slate-500 block">Name Match</span>
                        <span className={`font-bold text-xs ${bestMatch.criteria?.name_match ? 'text-emerald-700' : 'text-slate-400'}`}>
                          {bestMatch.criteria?.name_match ? '✓ Matched' : '✗ No'}
                        </span>
                      </div>
                      <div className="p-2 bg-white rounded border border-slate-200 text-center">
                        <span className="text-[10px] text-slate-500 block">DOB Match</span>
                        <span className={`font-bold text-xs ${bestMatch.criteria?.dob_match ? 'text-emerald-700' : 'text-amber-700'}`}>
                          {bestMatch.criteria?.dob_match ? '✓ Matched' : '✗ Unverified'}
                        </span>
                      </div>
                      <div className="p-2 bg-white rounded border border-slate-200 text-center">
                        <span className="text-[10px] text-slate-500 block">Phone Match</span>
                        <span className={`font-bold text-xs ${bestMatch.criteria?.phone_match ? 'text-emerald-700' : 'text-amber-700'}`}>
                          {bestMatch.criteria?.phone_match ? '✓ Matched' : '✗ Unverified'}
                        </span>
                      </div>
                    </div>

                    {/* Strict Auto-Merge Warning */}
                    <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-2 mt-2">
                      <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                      <div className="space-y-0.5">
                        <strong className="font-semibold">Safety Invariant: Never auto-merge on name alone.</strong>
                        <p className="text-[11px] text-amber-800">
                          {bestMatch.notes}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic">No candidate patients matched demographic filters.</p>
                )}
              </div>

              {/* 3. Recorded Patient Consent Enforcement */}
              <div className="p-4 rounded-xl border border-slate-200 space-y-3 bg-white">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-sky-600" />
                    Patient Transfer Consent Status
                  </h3>
                  <span
                    className={`text-xs font-bold px-2 py-0.5 rounded ${
                      hasActiveConsent
                        ? 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                        : 'bg-red-100 text-red-900 border border-red-300'
                    }`}
                  >
                    {hasActiveConsent ? 'Active Consent Verified' : 'Missing Consent (409 Gate)'}
                  </span>
                </div>

                <p className="text-xs text-slate-600 leading-relaxed">
                  Per HIPAA & clinical safety policy, importing external records into an active patient chart requires a legally recorded consent.
                </p>

                {!hasActiveConsent && (
                  <div className="pt-2 flex items-center gap-3">
                    <button
                      type="button"
                      onClick={handleRecordConsent}
                      disabled={recordingConsent || !targetPatientId}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-sky-700 hover:bg-sky-800 rounded-lg shadow-2xs transition-all cursor-pointer"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {recordingConsent ? 'Recording...' : `Record Patient Consent for ${targetPatientId}`}
                    </button>
                    <span className="text-[11px] text-slate-500">
                      Will record standard transfer consent from authorized patient representative.
                    </span>
                  </div>
                )}
              </div>

              {/* 4. Staff Confirmation & Merge Action */}
              {selectedBatch.status === 'quarantined' && (
                <div className="p-5 rounded-xl bg-[#FFF9F6] border border-[#F8AD9D] space-y-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#A83232] flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-[#E07A5F]" />
                    Confirm & Commit Quarantine Batch
                  </h3>

                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Target Patient ID:
                      </label>
                      <input
                        type="text"
                        value={targetPatientId}
                        onChange={(e) => handlePatientSelectChange(e.target.value)}
                        className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-2 focus:ring-[#E07A5F]"
                        placeholder="e.g. P-101"
                      />
                    </div>

                    <div className="flex items-start gap-2 pt-1">
                      <input
                        type="checkbox"
                        id="confirmIdentity"
                        checked={confirmIdentity}
                        onChange={(e) => setConfirmIdentity(e.target.checked)}
                        className="mt-0.5 rounded border-slate-300 text-[#E07A5F] focus:ring-[#E07A5F] cursor-pointer"
                      />
                      <label htmlFor="confirmIdentity" className="text-xs text-slate-700 cursor-pointer font-medium">
                        I confirm that demographic identity match has been verified with external records and patient consent is on file.
                      </label>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Override / Staff Notes (Optional):
                      </label>
                      <input
                        type="text"
                        value={overrideReasons}
                        onChange={(e) => setOverrideReasons(e.target.value)}
                        className="w-full text-xs px-3 py-1.5 rounded-lg border border-slate-300 bg-white"
                        placeholder="e.g. Cross-checked with phone contact and transfer referral letter"
                      />
                    </div>

                    <div className="pt-2 flex items-center gap-3">
                      <button
                        type="button"
                        onClick={handleConfirmMerge}
                        disabled={confirming}
                        className="inline-flex items-center gap-2 px-5 py-2.5 text-xs font-bold text-white bg-[#E07A5F] hover:bg-[#D0694E] rounded-lg shadow-xs transition-all cursor-pointer disabled:opacity-50"
                      >
                        <Database className="w-4 h-4" />
                        {confirming ? 'Committing...' : 'Commit Records to Patient Chart'}
                      </button>
                      <span className="text-[11px] text-slate-500">
                        Commits records with <code className="font-mono text-amber-800">trust_status=external_unverified</code> and marks summary stale.
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500 text-xs">
              Select a batch from the queue on the left to review validation, identity match, and consent.
            </div>
          )}
        </div>
      </div>

      {/* Upload JSON Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-2xl w-full p-6 space-y-4 animate-scale-in">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-[#E07A5F]" />
                Upload External Clinic Transfer JSON
              </h2>
              <button
                type="button"
                onClick={() => setShowUploadModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setJsonInput(JSON.stringify(SAMPLE_TRANSFER_PAYLOAD, null, 2))}
                className="text-[11px] font-semibold px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700"
              >
                Load Sample High-Confidence Payload (St. Jude)
              </button>
              <button
                type="button"
                onClick={() => setJsonInput(JSON.stringify(SAMPLE_NAME_ONLY_PAYLOAD, null, 2))}
                className="text-[11px] font-semibold px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700"
              >
                Load Sample Name-Only Risk Payload (City Health)
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-4">
              <textarea
                value={jsonInput}
                onChange={(e) => setJsonInput(e.target.value)}
                rows={14}
                className="w-full font-mono text-xs p-3 rounded-xl border border-slate-300 bg-slate-50 focus:outline-hidden focus:ring-2 focus:ring-[#E07A5F]"
                required
              />

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading}
                  className="px-4 py-2 text-xs font-bold text-white bg-[#E07A5F] hover:bg-[#D0694E] rounded-lg shadow-xs cursor-pointer"
                >
                  {uploading ? 'Uploading to Quarantine...' : 'Upload to Quarantine'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
