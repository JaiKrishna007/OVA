import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { patientsApi, transfersApi, ApiClientError } from '../services/api';
import type {
  PatientDetailResponse,
  TimelineResponse,
  FollowupsResponse,
  Citation,
  TransferRequestItem,
} from '../types/api';
import { PatientHeader } from '../components/PatientHeader';
import { CycleTimeline } from '../components/CycleTimeline';
import { CycleDrawer } from '../components/CycleDrawer';
import { LongitudinalTimeline } from '../components/LongitudinalTimeline';
import { CyclesTab } from '../components/CyclesTab';
import { SourceViewer } from '../components/SourceViewer';
import { SummaryTab } from '../components/SummaryTab';
import { FollowupsTab } from '../components/FollowupsTab';
import { CompareTab } from '../components/CompareTab';
import { EmbryosTab } from '../components/EmbryosTab';
import { StimulationTab } from '../components/StimulationTab';
import { SourcesTab } from '../components/SourcesTab';
import { AskTheChart } from '../components/AskTheChart';
import { AddRecordModal } from '../components/AddRecordModal';
import { PatientOverviewDashboard } from '../components/PatientOverviewDashboard';
import { EvidenceDrawer } from '../components/EvidenceDrawer';
import { ConflictsTab } from '../components/ConflictsTab';
import { GapsTab } from '../components/GapsTab';
import { ReviewQueueTab } from '../components/ReviewQueueTab';
import { ConsentsAndTransfersTab } from '../components/ConsentsAndTransfersTab';
import { PatientActivityTab } from '../components/PatientActivityTab';
import { useAuth } from '../context/AuthContext';
import {
  ArrowLeft,
  ShieldX,
  Loader2,
  Sparkles,
  Layers,
  RotateCcw,
  Clock,
  Columns,
  Baby,
  Activity,
  FileText,
  Calendar,
  MessageSquare,
  Upload,
  AlertTriangle,
  FileQuestion,
  ShieldAlert,
  ArrowRightLeft,
  CheckCircle2,
  XCircle,
  ShieldCheck,
} from 'lucide-react';

type TabKey =
  | 'summary'
  | 'conflicts'
  | 'gaps'
  | 'review'
  | 'timeline'
  | 'cycles'
  | 'stimulation'
  | 'followups'
  | 'compare'
  | 'embryos'
  | 'sources'
  | 'ask'
  | 'transfers'
  | 'activity';

export const PatientDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const isPatient = user?.role === 'patient';

  const [patient, setPatient] = useState<PatientDetailResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [followups, setFollowups] = useState<FollowupsResponse | null>(null);
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [selectedEvidenceClaimId, setSelectedEvidenceClaimId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>(isPatient ? 'timeline' : 'summary');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusCode, setStatusCode] = useState<number | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  // Patient Transfer Authorization Workflow
  const [pendingTransfers, setPendingTransfers] = useState<TransferRequestItem[]>([]);
  const [transferToConfirm, setTransferToConfirm] = useState<TransferRequestItem | null>(null);
  const [isTransferActionLoading, setIsTransferActionLoading] = useState(false);
  const [transferSuccessMessage, setTransferSuccessMessage] = useState<string | null>(null);
  const [transferErrorMessage, setTransferErrorMessage] = useState<string | null>(null);

  const loadTransfers = async (patientId: string) => {
    try {
      const list = await transfersApi.listTransfers({ patient_id: patientId });
      const requested = (list || []).filter((t) => t.status === 'REQUESTED');
      setPendingTransfers(requested);
    } catch {
      // Non-blocking
    }
  };

  useEffect(() => {
    const loadPatientData = async () => {
      if (!id) return;
      if (isPatient && user?.patient_id && user.patient_id !== id) {
        setIsLoading(false);
        setStatusCode(403);
        setError(
          `Scope Restriction (403 Forbidden): Patients are strictly restricted to accessing their own chart (${user.patient_id}).`
        );
        return;
      }
      setIsLoading(true);
      setError(null);
      setStatusCode(null);

      try {
        // Load patient profile, timeline, and transfer requests in parallel
        const [patientData, timelineData] = await Promise.all([
          patientsApi.getById(id),
          patientsApi.getTimeline(id),
          loadTransfers(id),
        ]);
        setPatient(patientData);
        setTimeline(timelineData);

        // Fetch followups for alert badges
        try {
          const followupsData = await patientsApi.getFollowups(id);
          setFollowups(followupsData);
        } catch {
          // Non-blocking
        }
      } catch (err: unknown) {
        if (err instanceof ApiClientError) {
          setStatusCode(err.status);
          if (err.status === 403) {
            setError(
              `Access Restricted (403 Forbidden): Patient ${id} is not in your assigned patient list. Per clinical governance policy, access is restricted.`
            );
          } else if (err.status === 404) {
            setError(`Patient record ${id} was not found in the EMR.`);
          } else {
            setError(err.message || 'Error loading patient record.');
          }
        } else {
          setError('Network error: Unable to connect to clinical backend.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadPatientData();
  }, [id, isPatient, user?.patient_id]);

  const handleAcceptAndTransfer = (transfer: TransferRequestItem) => {
    setTransferToConfirm(transfer);
    setTransferErrorMessage(null);
    setTransferSuccessMessage(null);
  };

  const handleConfirmTransferSubmit = async () => {
    if (!transferToConfirm) return;
    setIsTransferActionLoading(true);
    setTransferErrorMessage(null);
    try {
      await transfersApi.acceptTransfer(transferToConfirm.id);
      setTransferSuccessMessage(
        `Medical records successfully transferred to ${transferToConfirm.to_hospital_id}! Active consent has been granted to ${transferToConfirm.to_hospital_id}.`
      );
      setTransferToConfirm(null);
      if (id) {
        const [pData, tData] = await Promise.all([
          patientsApi.getById(id),
          patientsApi.getTimeline(id),
          loadTransfers(id),
        ]);
        setPatient(pData);
        setTimeline(tData);
      }
    } catch (err: any) {
      setTransferErrorMessage(err?.message || 'Failed to transfer medical records.');
    } finally {
      setIsTransferActionLoading(false);
    }
  };

  const handleRevokeTransfer = async (transfer: TransferRequestItem) => {
    if (!window.confirm(`Are you sure you want to revoke the transfer request to ${transfer.to_hospital_id}? No medical data will be transferred.`)) {
      return;
    }
    setIsTransferActionLoading(true);
    setTransferErrorMessage(null);
    try {
      await transfersApi.rejectTransfer(transfer.id, 'Revoked by patient');
      setTransferSuccessMessage(`Transfer request to ${transfer.to_hospital_id} has been revoked.`);
      if (id) {
        await loadTransfers(id);
      }
    } catch (err: any) {
      setTransferErrorMessage(err?.message || 'Failed to revoke transfer request.');
    } finally {
      setIsTransferActionLoading(false);
    }
  };

  // Construct clinical alert chips with "Record shows..." wording and source tooltips
  const buildAlerts = () => {
    if (!id || isPatient) return [];
    const alerts: Array<{
      id: string;
      type: 'conflict' | 'missing' | 'overdue' | 'warning' | 'info';
      title: string;
      text: string;
      sourceRefs: string[];
    }> = [];

    if (id === 'P-101') {
      alerts.push({
        id: 'p101-conflict-oocytes',
        type: 'conflict' as const,
        title: 'Conflicting Oocyte Count Across Documents',
        text: 'Record shows: OPU report states 9 oocytes while discharge note states 8',
        sourceRefs: ['REC-0142', 'REC-0143'],
      });
      alerts.push({
        id: 'p101-missing-semen',
        type: 'missing' as const,
        title: 'Missing Baseline Investigation',
        text: 'Record shows: No semen analysis documented on file',
        sourceRefs: [],
      });
      alerts.push({
        id: 'p101-overdue-tsh',
        type: 'overdue' as const,
        title: 'Overdue Laboratory Investigation',
        text: 'Record shows: Repeat TSH (Target < 2.5 mIU/L) overdue since 2025-03-01',
        sourceRefs: ['REC-0101'],
      });
    } else if (id === 'P-102') {
      alerts.push({
        id: 'p102-adverse-ohss',
        type: 'warning' as const,
        title: 'Documented Adverse Event',
        text: 'Record shows: Moderate OHSS managed on 2024-08-16 with Cabergoline and fluid monitoring',
        sourceRefs: ['REC-0242'],
      });
    } else if (id === 'P-103') {
      alerts.push({
        id: 'p103-duplicate-amh',
        type: 'conflict' as const,
        title: 'Conflicting Lab Results on Same Date',
        text: 'Record shows: Duplicate AMH tests on 2024-03-12 state 0.42 vs 0.88 ng/mL',
        sourceRefs: ['REC-0310', 'REC-0311'],
      });
      alerts.push({
        id: 'p103-pending-beta',
        type: 'overdue' as const,
        title: 'Pending Investigation',
        text: 'Record shows: Beta-hCG repeat test scheduled for 2025-03-18',
        sourceRefs: ['REC-0350'],
      });
    } else if (id === 'P-104') {
      alerts.push({
        id: 'p104-pregnancy-loss',
        type: 'warning' as const,
        title: 'Clinical Pregnancy History',
        text: 'Record shows: Spontaneous miscarriage at 8 weeks documented in clinical note',
        sourceRefs: ['REC-0450'],
      });
    } else if (id === 'P-105') {
      alerts.push({
        id: 'p105-missing-hsg',
        type: 'missing' as const,
        title: 'Missing Fallopian Patency Report',
        text: 'Record shows: HSG tubal patency evaluation not documented in records',
        sourceRefs: [],
      });
      alerts.push({
        id: 'p105-semen-analysis',
        type: 'conflict' as const,
        title: 'Severe Male Factor Finding',
        text: 'Record shows: Severe Oligoasthenoteratozoospermia on 2024-05-10',
        sourceRefs: ['REC-0510'],
      });
    }

    // Append dynamic overdue items from followups engine if any
    if (followups && followups.overdue && followups.overdue.length > 0) {
      followups.overdue.forEach((item) => {
        if (!alerts.some((a) => a.text.includes(item.name))) {
          alerts.push({
            id: `overdue-${item.id}`,
            type: 'overdue' as const,
            title: 'Overdue Follow-up Item',
            text: `Record shows: ${item.name} overdue since ${item.due_date}`,
            sourceRefs: item.source_refs || [item.source_id],
          });
        }
      });
    }

    return alerts;
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
        <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
        <p className="text-sm font-semibold text-slate-700">
          Loading clinical chart for {id}...
        </p>
        <p className="text-xs text-slate-400 mt-1">
          Validating clinician scope and reconstructing cycle timeline...
        </p>
      </div>
    );
  }

  // Handle 403 or other scope errors with friendly clinical card
  if (error) {
    return (
      <div className="bg-white rounded-xl border border-rose-200 p-8 shadow-xs max-w-2xl mx-auto my-8">
        <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 mx-auto flex items-center justify-center mb-4">
          <ShieldX className="w-6 h-6" />
        </div>
        <h2 className="text-lg font-bold text-slate-900 text-center mb-2">
          {statusCode === 403 ? 'Scope Restriction (403 Forbidden)' : 'Clinical Chart Unavailable'}
        </h2>
        <p className="text-sm text-slate-600 text-center mb-6 leading-relaxed">
          {error}
        </p>

        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3.5 text-xs text-slate-600 font-mono mb-6 space-y-1">
          <div>Patient ID: {id}</div>
          <div>Status: {statusCode || 'ERROR'}</div>
          <div>Policy Rule: Doctor-Patient Scope Guard (RBAC)</div>
        </div>

        <div className="flex justify-center">
          <Link
            to="/patients"
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Patient Directory</span>
          </Link>
        </div>
      </div>
    );
  }

  if (!patient || !timeline) return null;

  const alerts = buildAlerts();

  return (
    <div className="space-y-6">
      {/* 1. Header Card */}
      <PatientHeader patient={patient} alerts={alerts} />

      {/* Read-Only Transferred Patient Warning Banner */}
      {patient.access_level === 'READ_ONLY' && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 flex items-center justify-between gap-3 text-amber-900 shadow-2xs">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center shrink-0">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-bold">
                Read-only: patient transferred to {patient.transferred_to_hospital || 'another hospital'}
              </p>
              <p className="text-xs text-amber-700">
                Active clinical governance and write permissions transferred to receiving hospital. All historical medical records, laboratory values, and cycles remain accessible in view-only mode.
              </p>
            </div>
          </div>
          <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-200 text-amber-800 border border-amber-300 shrink-0">
            READ ONLY
          </span>
        </div>
      )}

      {/* Transfer Action Success / Error Notifications */}
      {transferSuccessMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-start gap-3 shadow-2xs">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          <div className="flex-1 font-semibold">{transferSuccessMessage}</div>
          <button
            onClick={() => setTransferSuccessMessage(null)}
            className="text-emerald-500 hover:text-emerald-700 font-bold"
          >
            &times;
          </button>
        </div>
      )}

      {transferErrorMessage && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-3 shadow-2xs">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <div className="flex-1 font-semibold">{transferErrorMessage}</div>
          <button
            onClick={() => setTransferErrorMessage(null)}
            className="text-rose-500 hover:text-rose-700 font-bold"
          >
            &times;
          </button>
        </div>
      )}

      {/* PATIENT TRANSFER AUTHORIZATION BANNER (Only Patient holds exclusive grant access authority) */}
      {isPatient && pendingTransfers.length > 0 && (
        <div className="space-y-4">
          {pendingTransfers.map((t) => (
            <div
              key={t.id}
              className="relative overflow-hidden bg-gradient-to-r from-[#FFF5F2] via-[#FFF9F7] to-[#FFF0ED] border-2 border-[#F08080] rounded-2xl p-6 shadow-peach-md"
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F08080] text-white flex items-center gap-1.5 shadow-2xs">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      Action Required: Transfer Medical Data
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-700 bg-white px-2 py-0.5 rounded-md border border-[#F8AD9D]">
                      {t.id}
                    </span>
                    <span className="text-xs text-slate-500 font-medium">
                      From: <strong className="font-mono text-slate-800">{t.from_hospital_id}</strong> &rarr; To:{' '}
                      <strong className="font-mono text-[#822828] font-bold">{t.to_hospital_id}</strong>
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-slate-900">
                    Authorize Transfer of Your Medical Records to{' '}
                    <span className="text-[#822828] font-black">{t.to_hospital_id}</span>
                  </h3>

                  <p className="text-xs text-slate-600 leading-relaxed max-w-2xl">
                    Hospital <strong className="text-slate-800">{t.from_hospital_id}</strong> has initiated a transfer of your clinical care and medical records to <strong className="text-slate-800">{t.to_hospital_id}</strong>.
                    Under patient privacy governance, <strong>grant access is held exclusively by you</strong> (not hospital, doctor, or admin). Please review and select an option below:
                  </p>

                  {t.reason && (
                    <div className="text-xs text-slate-700 italic bg-white/90 p-2.5 rounded-xl border border-[#F8AD9D]/40">
                      Reason: &ldquo;{t.reason}&rdquo;
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  {/* Option 1: Accept & Transfer */}
                  <button
                    type="button"
                    onClick={() => handleAcceptAndTransfer(t)}
                    disabled={isTransferActionLoading}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-peach-xs transition-all cursor-pointer disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Accept &amp; Transfer</span>
                  </button>

                  {/* Option 2: Revoke Transfer */}
                  <button
                    type="button"
                    onClick={() => handleRevokeTransfer(t)}
                    disabled={isTransferActionLoading}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-rose-700 bg-white border border-rose-200 hover:bg-rose-50 shadow-2xs transition-all cursor-pointer disabled:opacity-50"
                  >
                    <XCircle className="w-4 h-4 text-rose-600" />
                    <span>Revoke Transfer</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Non-Patient View: Awaiting Patient Authorization Banner */}
      {!isPatient && pendingTransfers.length > 0 && (
        <div className="bg-amber-50/90 border border-amber-300 rounded-xl p-4 flex items-center justify-between gap-3 text-xs text-amber-900 shadow-2xs">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center shrink-0">
              <Clock className="w-4 h-4" />
            </div>
            <div>
              <p className="font-bold">
                Transfer Request Awaiting Patient Authorization ({pendingTransfers[0].from_hospital_id} &rarr; {pendingTransfers[0].to_hospital_id})
              </p>
              <p className="text-amber-800 mt-0.5">
                Per patient data governance policy, access grant is held strictly and exclusively by the patient. Clinicians or administrators cannot authorize transfer of patient records without patient consent.
              </p>
            </div>
          </div>
          <span className="font-mono text-[11px] px-2.5 py-1 rounded-full bg-amber-200 text-amber-900 font-bold shrink-0">
            Awaiting Patient
          </span>
        </div>
      )}

      {/* 2. Patient Overview Dashboard (Top of patient page - Clinicians only) */}
      {!isPatient && (
        <PatientOverviewDashboard
          patientId={patient.id}
          activeTab={activeTab}
          onSelectTab={(tabKey) => setActiveTab(tabKey as TabKey)}
          onOpenEvidence={(claimId) => setSelectedEvidenceClaimId(claimId)}
        />
      )}

      {/* 3. Navigation Tabs */}
      <div className="bg-white/95 backdrop-blur-md rounded-2xl border border-[#FBC4AB]/50 px-4 pt-2.5 shadow-peach-xs">
        <div className="flex items-center justify-between gap-2 overflow-x-auto border-b border-[#FBC4AB]/25 pb-2">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setActiveTab('summary')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'summary'
                  ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                  : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-[#F08080]" />
              <span>Summary</span>
            </button>

            {!isPatient && (
              <>
                <button
                  onClick={() => setActiveTab('conflicts')}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                    activeTab === 'conflicts'
                      ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                      : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
                  }`}
                >
                  <AlertTriangle className="w-3.5 h-3.5 text-[#F08080]" />
                  <span>Conflicts</span>
                </button>

                <button
                  onClick={() => setActiveTab('gaps')}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                    activeTab === 'gaps'
                      ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                      : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
                  }`}
                >
                  <FileQuestion className="w-3.5 h-3.5 text-amber-500" />
                  <span>Gaps</span>
                </button>

                <button
                  onClick={() => setActiveTab('review')}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                    activeTab === 'review'
                      ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                      : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
                  }`}
                >
                  <ShieldAlert className="w-3.5 h-3.5 text-slate-500" />
                  <span>Review Queue</span>
                </button>
              </>
            )}

          <button
            onClick={() => setActiveTab('timeline')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'timeline'
                ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-[#F08080]" />
            <span>Timeline</span>
            <span className="px-1.5 py-0.2 rounded-full bg-[#FFDAB9]/40 text-[#822828] text-[10px] font-mono">
              {timeline.cycles.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('cycles')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'cycles'
                ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
            }`}
          >
            <RotateCcw className="w-3.5 h-3.5 text-[#F08080]" />
            <span>Cycles</span>
            <span className="px-1.5 py-0.2 rounded-full bg-[#FFDAB9]/40 text-[#822828] text-[10px] font-mono">
              {timeline.cycles.length}
            </span>
          </button>

          {!isPatient && (
            <>
              <button
                onClick={() => setActiveTab('stimulation')}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === 'stimulation'
                    ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                    : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
                }`}
              >
                <Activity className="w-3.5 h-3.5 text-[#F08080]" />
                <span>Stimulation</span>
              </button>

              <button
                onClick={() => setActiveTab('followups')}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === 'followups'
                    ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                    : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
                }`}
              >
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span>Follow-ups</span>
                {followups?.counts?.overdue ? (
                  <span className="px-1.5 py-0.2 rounded-full bg-rose-100 text-rose-800 text-[10px] font-bold">
                    {followups.counts.overdue}
                  </span>
                ) : null}
              </button>

              <button
                onClick={() => setActiveTab('compare')}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === 'compare'
                    ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                    : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
                }`}
              >
                <Columns className="w-3.5 h-3.5 text-slate-400" />
                <span>Compare</span>
              </button>

              <button
                onClick={() => setActiveTab('embryos')}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === 'embryos'
                    ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                    : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
                }`}
              >
                <Baby className="w-3.5 h-3.5 text-slate-400" />
                <span>Embryos</span>
              </button>
            </>
          )}

          <button
            onClick={() => setActiveTab('sources')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'sources'
                ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
            }`}
          >
            <FileText className="w-3.5 h-3.5 text-slate-400" />
            <span>{isPatient ? 'My Records' : 'Sources'}</span>
            <span className="px-1.5 py-0.2 rounded-full bg-[#FFDAB9]/40 text-[#822828] text-[10px] font-mono">
              {patient.source_refs.length}
            </span>
          </button>

          {!isPatient && (
            <button
              onClick={() => setActiveTab('ask')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'ask'
                  ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                  : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5 text-[#F08080]" />
              <span>Ask the Chart</span>
            </button>
          )}

            <button
              onClick={() => setActiveTab('transfers')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'transfers'
                  ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                  : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
              }`}
            >
              <ArrowRightLeft className="w-3.5 h-3.5 text-[#F08080]" />
              <span>Transfers & Consents</span>
            </button>

            {!isPatient && (
              <button
                onClick={() => setActiveTab('activity')}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === 'activity'
                    ? 'bg-gradient-to-r from-[#FFF5F2] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] shadow-peach-xs font-bold'
                    : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF5F2]/50'
                }`}
              >
                <Activity className="w-3.5 h-3.5 text-[#F08080]" />
                <span>Activity</span>
              </button>
            )}
          </div>

          {/* Quick Add Record Action - Clinicians only */}
          {!isPatient && (
            patient.access_level === 'READ_ONLY' ? (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled
                  title="Upload disabled: Hospital access is Read-Only (Patient transferred)"
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-400 bg-slate-100 border border-slate-200 rounded-lg cursor-not-allowed shrink-0"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Add Record</span>
                </button>
                <span className="text-[11px] text-amber-700 font-medium hidden sm:inline">
                  Uploads disabled (Read-Only)
                </span>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setIsUploadModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-gradient-to-r from-[#F08080] to-[#F4978E] hover:from-[#E07070] hover:to-[#F08080] shadow-peach-xs rounded-lg transition-all shrink-0"
              >
                <Upload className="w-3.5 h-3.5" />
                <span>Add Record</span>
              </button>
            )
          )}
        </div>
      </div>

      {/* 3. Tab Contents */}
      {activeTab === 'timeline' && (
        <div className="space-y-6">
          {/* Horizontal Interactive Overview Timeline */}
          <CycleTimeline
            cycles={timeline.cycles}
            selectedCycleId={selectedCycleId}
            onSelectCycle={(cycleId) => setSelectedCycleId(cycleId)}
          />

          {/* Vertical Longitudinal Timeline by Year */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 sm:p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Calendar className="w-4 h-4 text-[#F08080]" />
                <span>Vertical Longitudinal Timeline by Year</span>
              </h3>
              <span className="text-xs text-slate-500 font-mono">
                {timeline.years?.length || 0} years documented
              </span>
            </div>

            <LongitudinalTimeline
              timeline={timeline}
              onSelectCitation={(cit) => setSelectedCitation(cit)}
              onSelectCycle={(cycleId) => setSelectedCycleId(cycleId)}
            />
          </div>
        </div>
      )}

      {/* Cycles Tab with Accordions */}
      {activeTab === 'cycles' && (
        <CyclesTab
          timeline={timeline}
          onSelectCitation={(cit) => setSelectedCitation(cit)}
          onSelectCycle={(cycleId) => setSelectedCycleId(cycleId)}
        />
      )}

      {/* Summary Tab */}
      {activeTab === 'summary' && (
        <SummaryTab patientId={patient.id} />
      )}

      {/* Conflicts Tab */}
      {activeTab === 'conflicts' && (
        <ConflictsTab
          patientId={patient.id}
          onOpenEvidence={(claimId) => setSelectedEvidenceClaimId(claimId)}
        />
      )}

      {/* Gaps Tab */}
      {activeTab === 'gaps' && (
        <GapsTab patientId={patient.id} />
      )}

      {/* Review Queue Tab */}
      {activeTab === 'review' && (
        <ReviewQueueTab
          patientId={patient.id}
          onOpenEvidence={(claimId) => setSelectedEvidenceClaimId(claimId)}
        />
      )}

      {/* Stimulation Tab */}
      {activeTab === 'stimulation' && (
        <StimulationTab patientId={patient.id} />
      )}

      {/* Follow-ups Tab */}
      {activeTab === 'followups' && (
        <FollowupsTab patientId={patient.id} />
      )}

      {/* Compare Tab */}
      {activeTab === 'compare' && (
        <CompareTab patientId={patient.id} />
      )}

      {/* Embryos Tab */}
      {activeTab === 'embryos' && (
        <EmbryosTab patientId={patient.id} />
      )}

      {/* Sources Tab */}
      {activeTab === 'sources' && (
        <SourcesTab patientId={patient.id} />
      )}

      {/* Ask the Chart Tab */}
      {activeTab === 'ask' && (
        <AskTheChart
          patientId={patient.id}
          onOpenEvidence={(claimId) => setSelectedEvidenceClaimId(claimId)}
        />
      )}

      {/* Transfers and Consents Tab */}
      {activeTab === 'transfers' && (
        <ConsentsAndTransfersTab patientId={patient.id} />
      )}

      {/* Patient Activity Feed / Audit Tab */}
      {activeTab === 'activity' && (
        <PatientActivityTab patientId={patient.id} />
      )}

      {/* 4. Drill-Down Cycle Drawer */}
      <CycleDrawer
        patientId={patient.id}
        cycleId={selectedCycleId}
        onClose={() => setSelectedCycleId(null)}
      />

      {/* 5. Evidence Source Viewer Drawer */}
      <SourceViewer
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />

      {/* 6. Claim Evidence Drawer (Reused everywhere a fact appears) */}
      <EvidenceDrawer
        claimId={selectedEvidenceClaimId}
        onClose={() => setSelectedEvidenceClaimId(null)}
      />

      {/* 6. Add Record Modal */}
      <AddRecordModal
        patientId={patient.id}
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onSuccess={async () => {
          // Re-fetch timeline and patient data dynamically without page reload
          if (id) {
            try {
              const [updatedTimeline, updatedPatient] = await Promise.all([
                patientsApi.getTimeline(id),
                patientsApi.getById(id),
              ]);
              setTimeline(updatedTimeline);
              setPatient(updatedPatient);
            } catch (e) {
              console.error('Failed to reload timeline after upload', e);
            }
          }
          setActiveTab('timeline');
        }}
      />

      {/* 7. Confirm Medical Record Transfer Modal */}
      {transferToConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-[#F8AD9D] shadow-2xl max-w-md w-full p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-2xs">
                  <ShieldCheck className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Confirm Medical Record Transfer</h3>
                  <p className="text-[11px] text-slate-500 font-medium">Patient Authorization Required</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setTransferToConfirm(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3.5 text-xs text-slate-600">
              <div className="p-3.5 bg-[#FFF5F2] rounded-xl border border-[#F8AD9D]/50 text-slate-800">
                <p className="font-bold text-sm text-[#822828] mb-1">
                  Are you sure you want to transfer your medical data to {transferToConfirm.to_hospital_id}?
                </p>
                <p className="text-xs text-slate-700 leading-relaxed">
                  Pressing <strong>&ldquo;Yes, Confirm Transfer&rdquo;</strong> will execute the transfer of your complete medical history, treatment cycles, and diagnostic records to <strong>{transferToConfirm.to_hospital_id}</strong>.
                </p>
              </div>

              <div className="space-y-2 text-[11px] bg-slate-50 p-3 rounded-xl border border-slate-100">
                <div className="flex items-center gap-2 text-emerald-800 font-semibold">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Active patient consent recorded automatically for {transferToConfirm.to_hospital_id}</span>
                </div>
                <div className="flex items-center gap-2 text-emerald-800 font-semibold">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{transferToConfirm.to_hospital_id} doctor granted Full Read/Write Clinical Care Access</span>
                </div>
                <div className="flex items-center gap-2 text-slate-700 font-semibold">
                  <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>Sending clinic ({transferToConfirm.from_hospital_id}) converted to Read-Only archive status</span>
                </div>
                <div className="flex items-center gap-2 text-[#822828] font-bold">
                  <ShieldCheck className="w-4 h-4 text-[#F08080] shrink-0" />
                  <span>Access grant authority remains exclusively yours as the patient</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setTransferToConfirm(null)}
                disabled={isTransferActionLoading}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmTransferSubmit}
                disabled={isTransferActionLoading}
                className="flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-peach-xs transition-all disabled:opacity-50 cursor-pointer"
              >
                {isTransferActionLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-4 h-4" />
                )}
                <span>Yes, Confirm Transfer</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
