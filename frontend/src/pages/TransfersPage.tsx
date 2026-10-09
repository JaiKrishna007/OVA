import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { transfersApi, patientsApi, ApiClientError } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { TransferRequestItem, PatientListItem } from '../types/api';
import {
  ArrowRightLeft,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Send,
  ExternalLink,
  Loader2,
  Building2,
  Trash2,
} from 'lucide-react';

export const TransfersPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const userHospital = user?.hospital_id || user?.org_id || 'ORG-Y';

  const [activeTab, setActiveTab] = useState<'incoming' | 'outgoing'>('incoming');
  const [transfers, setTransfers] = useState<TransferRequestItem[]>([]);
  const [patients, setPatients] = useState<PatientListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Modals
  const [isTransferModalOpen, setIsTransferModalOpen] = useState(false);

  // Transfer Form State
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [toHospitalId, setToHospitalId] = useState(userHospital === 'ORG-Y' ? 'ORG-B' : 'ORG-Y');
  const [transferReason, setTransferReason] = useState('Continuity of care & clinic relocation');

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [transfersData, patientsData] = await Promise.all([
        transfersApi.listTransfers({}),
        patientsApi.search().catch(() => []),
      ]);
      setTransfers(transfersData || []);
      setPatients(patientsData || []);

      if (patientsData && patientsData.length > 0) {
        setSelectedPatientId(patientsData[0].id);
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError('Failed to load transfers data.');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Filter transfers
  const incomingTransfers = transfers.filter((t) => t.to_hospital_id === userHospital);
  const outgoingTransfers = transfers.filter((t) => t.from_hospital_id === userHospital);

  const pendingIncomingCount = incomingTransfers.filter((t) => t.status === 'REQUESTED').length;
  const pendingOutgoingCount = outgoingTransfers.filter((t) => t.status === 'REQUESTED').length;
  const completedCount = transfers.filter((t) => t.status === 'COMPLETED').length;

  const handleAcceptTransfer = async (transferId: string) => {
    setIsActionLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await transfersApi.acceptTransfer(transferId);
      setSuccessMessage('Transfer accepted! Access permissions updated in single atomic transaction: sending hospital is now READ_ONLY, receiving hospital is READ_WRITE.');
      await loadData();
    } catch (err: any) {
      const msg = err?.message || 'Failed to accept transfer.';
      if (msg.includes('CONSENT_REQUIRED')) {
        setError('409 Conflict: CONSENT_REQUIRED. Active patient consent for your hospital is strictly required before accepting a transfer.');
      } else {
        setError(msg);
      }
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRejectTransfer = async (transferId: string) => {
    const reason = window.prompt('Please enter reason for rejecting this transfer (optional):');
    if (reason === null) return;
    setIsActionLoading(true);
    setError(null);
    try {
      await transfersApi.rejectTransfer(transferId, reason || undefined);
      setSuccessMessage('Transfer request rejected.');
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to reject transfer.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleCancelTransfer = async (transferId: string) => {
    if (!window.confirm('Are you sure you want to cancel this transfer request?')) return;
    setIsActionLoading(true);
    setError(null);
    try {
      await transfersApi.cancelTransfer(transferId);
      setSuccessMessage('Transfer request cancelled.');
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to cancel transfer.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleClearAllTransfers = async () => {
    if (!window.confirm('Are you sure you want to clear all transfer data? This will reset all transfer requests, temporary records, and access permissions back to baseline.')) {
      return;
    }
    setIsActionLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await transfersApi.clearTransfers();
      setSuccessMessage(res.message || 'All transfer data cleared successfully.');
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to clear transfer data.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRequestTransferSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId) return;
    setIsActionLoading(true);
    setError(null);
    try {
      await transfersApi.createTransfer({
        patient_id: selectedPatientId,
        from_hospital_id: userHospital,
        to_hospital_id: toHospitalId,
        reason: transferReason,
      });
      setSuccessMessage('Transfer request created successfully (Status: REQUESTED).');
      setIsTransferModalOpen(false);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to submit transfer request.');
    } finally {
      setIsActionLoading(false);
    }
  };


  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-[#FFF5F2] via-[#FFF9F7] to-[#FFF0ED] border border-[#F8AD9D]/60 rounded-2xl p-6 shadow-peach-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#F08080] to-[#F4978E] text-white flex items-center justify-center shadow-peach-xs shrink-0">
              <ArrowRightLeft className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                  Hospital Transfers
                </h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FFDAB9]/60 text-[#822828] border border-[#F8AD9D]">
                  {userHospital}
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-1">
                Cross-hospital record exchange and atomic care transfers
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            <button
              type="button"
              onClick={handleClearAllTransfers}
              disabled={isActionLoading}
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold text-rose-700 bg-white border border-rose-200 hover:bg-rose-50 rounded-xl shadow-2xs transition-all cursor-pointer disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5 text-rose-600" />
              <span>Clear All Transfers</span>
            </button>

            <button
              type="button"
              onClick={() => setIsTransferModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 text-xs font-bold text-white bg-gradient-to-r from-[#F08080] to-[#F4978E] hover:from-[#E07070] hover:to-[#F08080] rounded-xl shadow-peach-xs transition-all cursor-pointer"
            >
              <Send className="w-4 h-4" />
              <span>Request Transfer</span>
            </button>
          </div>
        </div>

        {/* Metrics Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6 pt-5 border-t border-[#F8AD9D]/30">
          <div className="bg-white/80 backdrop-blur-xs rounded-xl p-3 border border-slate-200/80 shadow-2xs">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Incoming Requests</div>
            <div className="text-xl font-black text-slate-900 mt-0.5 flex items-center gap-2">
              {incomingTransfers.length}
              {pendingIncomingCount > 0 && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200">
                  {pendingIncomingCount} pending
                </span>
              )}
            </div>
          </div>

          <div className="bg-white/80 backdrop-blur-xs rounded-xl p-3 border border-slate-200/80 shadow-2xs">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Outgoing Requests</div>
            <div className="text-xl font-black text-slate-900 mt-0.5 flex items-center gap-2">
              {outgoingTransfers.length}
              {pendingOutgoingCount > 0 && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800 border border-indigo-200">
                  {pendingOutgoingCount} pending
                </span>
              )}
            </div>
          </div>

          <div className="bg-white/80 backdrop-blur-xs rounded-xl p-3 border border-slate-200/80 shadow-2xs">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Completed Transfers</div>
            <div className="text-xl font-black text-emerald-700 mt-0.5 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              {completedCount}
            </div>
          </div>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
          <div className="flex-1 font-medium">{error}</div>
          <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700 font-bold">&times;</button>
        </div>
      )}

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <div className="flex-1 font-medium">{successMessage}</div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-500 hover:text-emerald-700 font-bold">&times;</button>
        </div>
      )}

      {/* Nav Tabs */}
      <div className="flex border-b border-slate-200 gap-2">
        <button
          onClick={() => setActiveTab('incoming')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
            activeTab === 'incoming'
              ? 'border-[#F08080] text-[#822828] bg-[#FFF5F2]/50'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Building2 className="w-4 h-4 text-[#F08080]" />
          <span>Incoming Transfers ({incomingTransfers.length})</span>
          {pendingIncomingCount > 0 && (
            <span className="w-2 h-2 rounded-full bg-amber-500" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('outgoing')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
            activeTab === 'outgoing'
              ? 'border-[#F08080] text-[#822828] bg-[#FFF5F2]/50'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Send className="w-4 h-4 text-[#F08080]" />
          <span>Outgoing Transfers ({outgoingTransfers.length})</span>
        </button>
      </div>

      {/* Loading */}
      {isLoading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-2xs">
          <Loader2 className="w-6 h-6 text-[#F08080] animate-spin mx-auto mb-2" />
          <p className="text-xs font-semibold text-slate-600">Loading transfers...</p>
        </div>
      ) : (
        <>
          {/* TAB 1: INCOMING TRANSFERS */}
          {activeTab === 'incoming' && (
            <div className="space-y-4">
              {incomingTransfers.length === 0 ? (
                <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-2xs">
                  <ArrowRightLeft className="w-8 h-8 text-slate-300 mx-auto mb-3" />
                  <p className="text-sm font-bold text-slate-800">No incoming transfer requests</p>
                  <p className="text-xs text-slate-500 mt-1">
                    When external fertility clinics request a patient transfer to {userHospital}, requests will appear here for review.
                  </p>
                </div>
              ) : (
                <div className="space-y-3.5">
                  {incomingTransfers.map((t) => {
                    const isRequested = t.status === 'REQUESTED';
                    const isCompleted = t.status === 'COMPLETED';
                    const hasActiveConsent = t.has_active_consent;

                    return (
                      <div
                        key={t.id}
                        className="bg-white rounded-2xl border border-slate-200/80 hover:border-[#F8AD9D] p-5 shadow-2xs transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
                      >
                        <div className="space-y-2">
                          <div className="flex items-center gap-2.5 flex-wrap">
                            <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2.5 py-1 rounded-lg">
                              {t.id}
                            </span>
                            <span
                              className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${
                                isCompleted
                                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                  : t.status === 'REJECTED'
                                  ? 'bg-rose-50 text-rose-700 border-rose-200'
                                  : t.status === 'CANCELLED'
                                  ? 'bg-slate-100 text-slate-600 border-slate-200'
                                  : 'bg-amber-50 text-amber-800 border-amber-200'
                              }`}
                            >
                              {t.status}
                            </span>

                            {/* Consent Status Badge */}
                            {isRequested && (
                              hasActiveConsent ? (
                                <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1">
                                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                                  Active Patient Consent Verified
                                </span>
                              ) : (
                                <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-900 border border-amber-200 flex items-center gap-1">
                                  <ShieldAlert className="w-3.5 h-3.5 text-amber-600" />
                                  Consent Required (Safety Rule S7)
                                </span>
                              )
                            )}
                          </div>

                          <div className="text-xs text-slate-700">
                            Patient:{' '}
                            <strong className="font-bold text-slate-900">
                              {t.patient_name || t.patient_id}
                            </strong>{' '}
                            <span className="font-mono text-slate-500">({t.patient_id})</span> &bull; Sending Hospital:{' '}
                            <strong className="font-mono text-slate-800">{t.from_hospital_id}</strong>
                          </div>

                          {t.reason && (
                            <p className="text-xs text-slate-600 italic bg-[#FFF9F7] p-2.5 rounded-xl border border-[#F8AD9D]/30">
                              &ldquo;{t.reason}&rdquo;
                            </p>
                          )}

                          {isRequested && !hasActiveConsent && (
                            <p className="text-[11px] text-amber-800 font-medium flex items-center gap-1.5 bg-amber-50 p-2.5 rounded-xl border border-amber-200">
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                              Awaiting Patient Authorization: Medical records cannot be transferred until the patient accepts and confirms the transfer in their portal. Only the patient holds the authority to grant data access.
                            </p>
                          )}
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2.5 shrink-0">
                          {isRequested && (
                            <>
                              <button
                                type="button"
                                onClick={() => handleAcceptTransfer(t.id)}
                                disabled={isActionLoading || !hasActiveConsent}
                                title={!hasActiveConsent ? 'Cannot accept without active patient consent' : 'Accept incoming transfer'}
                                className={`px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-2xs ${
                                  hasActiveConsent
                                    ? 'text-white bg-emerald-600 hover:bg-emerald-700 cursor-pointer shadow-peach-xs'
                                    : 'text-slate-400 bg-slate-100 border border-slate-200 cursor-not-allowed'
                                }`}
                              >
                                {isActionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Accept Transfer'}
                              </button>

                              <button
                                type="button"
                                onClick={() => handleRejectTransfer(t.id)}
                                disabled={isActionLoading}
                                className="px-3 py-2 rounded-xl text-xs font-bold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 transition-colors cursor-pointer"
                              >
                                Reject
                              </button>
                            </>
                          )}

                          {isCompleted && (
                            <button
                              type="button"
                              onClick={() => navigate(`/patients/${t.patient_id}`)}
                              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-[#822828] bg-[#FFF0ED] hover:bg-[#FEEBE3] border border-[#F8AD9D] transition-all cursor-pointer"
                            >
                              <ExternalLink className="w-3.5 h-3.5 text-[#F08080]" />
                              <span>Open Patient Chart</span>
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: OUTGOING TRANSFERS */}
          {activeTab === 'outgoing' && (
            <div className="space-y-4">
              {outgoingTransfers.length === 0 ? (
                <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-2xs">
                  <Send className="w-8 h-8 text-slate-300 mx-auto mb-3" />
                  <p className="text-sm font-bold text-slate-800">No outgoing transfer requests</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Click &ldquo;Request Transfer&rdquo; above to transfer a patient chart to another fertility clinic.
                  </p>
                </div>
              ) : (
                <div className="space-y-3.5">
                  {outgoingTransfers.map((t) => {
                    const isRequested = t.status === 'REQUESTED';
                    const isCompleted = t.status === 'COMPLETED';

                    return (
                      <div
                        key={t.id}
                        className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4"
                      >
                        <div className="space-y-2">
                          <div className="flex items-center gap-2.5 flex-wrap">
                            <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2.5 py-1 rounded-lg">
                              {t.id}
                            </span>
                            <span
                              className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${
                                isCompleted
                                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                  : t.status === 'REJECTED'
                                  ? 'bg-rose-50 text-rose-700 border-rose-200'
                                  : t.status === 'CANCELLED'
                                  ? 'bg-slate-100 text-slate-600 border-slate-200'
                                  : 'bg-amber-50 text-amber-800 border-amber-200'
                              }`}
                            >
                              {t.status}
                            </span>
                          </div>

                          <div className="text-xs text-slate-700">
                            Patient:{' '}
                            <strong className="font-bold text-slate-900">
                              {t.patient_name || t.patient_id}
                            </strong>{' '}
                            <span className="font-mono text-slate-500">({t.patient_id})</span> &bull; Destination Hospital:{' '}
                            <strong className="font-mono text-slate-800">{t.to_hospital_id}</strong>
                          </div>

                          {t.reason && (
                            <p className="text-xs text-slate-600 italic bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                              &ldquo;{t.reason}&rdquo;
                            </p>
                          )}
                        </div>

                        <div className="flex items-center gap-2.5 shrink-0">
                          {isRequested && (
                            <button
                              type="button"
                              onClick={() => handleCancelTransfer(t.id)}
                              disabled={isActionLoading}
                              className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 border border-slate-200 transition-colors"
                            >
                              Cancel Request
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={() => navigate(`/patients/${t.patient_id}`)}
                            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-[#822828] bg-[#FFF0ED] hover:bg-[#FEEBE3] border border-[#F8AD9D] transition-all cursor-pointer"
                          >
                            <ExternalLink className="w-3.5 h-3.5 text-[#F08080]" />
                            <span>View Chart</span>
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}


        </>
      )}

      {/* MODAL 1: REQUEST TRANSFER */}
      {isTransferModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 max-w-lg w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Send className="w-4 h-4 text-[#F08080]" />
                <span>Initiate Hospital Transfer Request</span>
              </h3>
              <button onClick={() => setIsTransferModalOpen(false)} className="text-slate-400 hover:text-slate-600 font-bold">&times;</button>
            </div>

            <form onSubmit={handleRequestTransferSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Select Patient</label>
                <select
                  value={selectedPatientId}
                  onChange={(e) => setSelectedPatientId(e.target.value)}
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#F08080]/30 outline-none"
                  required
                >
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.id})
                    </option>
                  ))}
                  {patients.length === 0 && (
                    <option value="P-101">Priya S. (P-101)</option>
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Destination Hospital</label>
                <select
                  value={toHospitalId}
                  onChange={(e) => setToHospitalId(e.target.value)}
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#F08080]/30 outline-none"
                  required
                >
                  <option value="ORG-B">Hospital B (ORG-B - Bangalore Fertility Centre)</option>
                  <option value="ORG-Y">Hospital A (ORG-Y - Yashodha Fertility Clinic)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Clinical Reason for Transfer</label>
                <input
                  type="text"
                  value={transferReason}
                  onChange={(e) => setTransferReason(e.target.value)}
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#F08080]/30 outline-none"
                  placeholder="e.g. Relocation & continuity of care"
                  required
                />
              </div>

              {/* Duplicate Transfer Guard */}
              {transfers.some((t) => t.patient_id === selectedPatientId && t.status === 'REQUESTED') && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="block font-bold">Duplicate Transfer Blocked</strong>
                    <span>A transfer request for patient {selectedPatientId} is already pending. Concurrent duplicate transfers are not permitted.</span>
                  </div>
                </div>
              )}

              {userHospital === toHospitalId && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-900 flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="block font-bold">Invalid Destination</strong>
                    <span>Sending and destination hospitals cannot be the same ({userHospital}).</span>
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsTransferModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={
                    isActionLoading ||
                    transfers.some((t) => t.patient_id === selectedPatientId && t.status === 'REQUESTED') ||
                    userHospital === toHospitalId
                  }
                  className="px-4 py-2 text-xs font-bold text-white bg-gradient-to-r from-[#F08080] to-[#F4978E] hover:from-[#E07070] hover:to-[#F08080] rounded-xl shadow-peach-xs flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
                >
                  {isActionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Submit Transfer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}


    </div>
  );
};
