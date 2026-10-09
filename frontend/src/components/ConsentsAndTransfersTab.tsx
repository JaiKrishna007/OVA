import React, { useState, useEffect, useCallback } from 'react';
import { consentsApi, transfersApi, ApiClientError } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { ConsentItem, TransferRequestItem } from '../types/api';
import {
  ArrowRightLeft,
  ShieldCheck,
  Loader2,
  PlusCircle,
  XCircle,
  CheckCircle2,
  Clock,
  Send,
  AlertTriangle,
  UserCheck,
  Inbox,
} from 'lucide-react';

interface ConsentsAndTransfersTabProps {
  patientId: string;
}

export const ConsentsAndTransfersTab: React.FC<ConsentsAndTransfersTabProps> = ({ patientId }) => {
  const { user } = useAuth();
  const isPatient = user?.role === 'patient';
  const isHospitalAdmin = user?.role === 'hospital_admin' || user?.role === 'admin';
  const userHospital = user?.hospital_id || user?.org_id;

  const [consents, setConsents] = useState<ConsentItem[]>([]);
  const [transfers, setTransfers] = useState<TransferRequestItem[]>([]);
  const [inboxTransfers, setInboxTransfers] = useState<TransferRequestItem[]>([]);
  const [inboxFilter, setInboxFilter] = useState<'all' | 'incoming' | 'outgoing'>('incoming');
  const [activeSubView, setActiveSubView] = useState<'chart' | 'inbox'>('chart');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Modal states
  const [isGrantModalOpen, setIsGrantModalOpen] = useState(false);
  const [isTransferModalOpen, setIsTransferModalOpen] = useState(false);
  const [transferToConfirm, setTransferToConfirm] = useState<TransferRequestItem | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);

  // Grant Consent Form
  const [targetHospital, setTargetHospital] = useState('ORG-B');
  const [purpose, setPurpose] = useState('Continuity of fertility care');
  const [scope, setScope] = useState('ALL_RECORDS');
  const [expiresAt, setExpiresAt] = useState('');

  // Request Transfer Form
  const [transferTargetHospital, setTransferTargetHospital] = useState('ORG-B');
  const [transferReason, setTransferReason] = useState('Continuity of care & relocation');

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [consentsData, transfersData] = await Promise.all([
        consentsApi.listConsents(patientId).catch(() => []),
        transfersApi.listTransfers({ patient_id: patientId }).catch(() => []),
      ]);
      setConsents(consentsData || []);
      setTransfers(transfersData || []);

      if (isHospitalAdmin) {
        const allAdminTransfers = await transfersApi.listTransfers({}).catch(() => []);
        setInboxTransfers(allAdminTransfers || []);
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError('Failed to load consents and transfer records.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [patientId, isHospitalAdmin]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleGrantConsent = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsActionLoading(true);
    setError(null);
    try {
      await consentsApi.recordConsent({
        patient_id: patientId,
        target_hospital_id: targetHospital,
        purpose,
        scope,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : undefined,
        recorded_on_behalf: isHospitalAdmin,
      });
      setActionSuccess('Patient consent successfully recorded.');
      setIsGrantModalOpen(false);
      await fetchData();
    } catch (err: any) {
      setError(err?.message || 'Failed to grant consent.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRevokeConsent = async (consentId: string) => {
    if (!window.confirm('Are you sure you want to revoke this consent? Access for that hospital will become REVOKED going forward.')) {
      return;
    }
    setIsActionLoading(true);
    setError(null);
    try {
      await consentsApi.revokeConsent(consentId);
      setActionSuccess('Consent successfully revoked. Associated hospital access has been terminated.');
      await fetchData();
    } catch (err: any) {
      setError(err?.message || 'Failed to revoke consent.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRequestTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsActionLoading(true);
    setError(null);
    try {
      await transfersApi.createTransfer({
        patient_id: patientId,
        to_hospital_id: transferTargetHospital,
        reason: transferReason,
      });
      setActionSuccess('Transfer request submitted successfully (status: REQUESTED).');
      setIsTransferModalOpen(false);
      await fetchData();
    } catch (err: any) {
      setError(err?.message || 'Failed to initiate transfer request.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleAcceptTransfer = async (transferId: string) => {
    setIsActionLoading(true);
    setError(null);
    try {
      await transfersApi.acceptTransfer(transferId);
      setActionSuccess('Transfer accepted! Access permissions updated in single transaction: sending hospital is now READ_ONLY, receiving hospital is READ_WRITE.');
      await fetchData();
    } catch (err: any) {
      const msg = err?.message || 'Failed to accept transfer.';
      if (msg.includes('CONSENT_REQUIRED')) {
        setError('409 Conflict: CONSENT_REQUIRED. Active patient consent for your hospital is required before this transfer can be accepted.');
      } else {
        setError(msg);
      }
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRejectTransfer = async (transferId: string) => {
    const reason = window.prompt('Please enter a reason for rejecting this transfer (optional):');
    if (reason === null) return;
    setIsActionLoading(true);
    setError(null);
    try {
      await transfersApi.rejectTransfer(transferId, reason || undefined);
      setActionSuccess('Transfer request rejected.');
      await fetchData();
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
      setActionSuccess('Transfer request cancelled.');
      await fetchData();
    } catch (err: any) {
      setError(err?.message || 'Failed to cancel transfer.');
    } finally {
      setIsActionLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-2xs">
        <Loader2 className="w-6 h-6 text-[#F08080] animate-spin mx-auto mb-2" />
        <p className="text-xs font-semibold text-slate-600">Loading consents and transfer requests...</p>
      </div>
    );
  }

  // Filtered inbox transfers
  const filteredInbox = inboxTransfers.filter((t) => {
    if (inboxFilter === 'incoming') return t.to_hospital_id === userHospital;
    if (inboxFilter === 'outgoing') return t.from_hospital_id === userHospital;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Notifications */}
      {error && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-2.5 shadow-2xs">
          <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
          <div className="flex-1 font-medium">{error}</div>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-600">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}
      {actionSuccess && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-start gap-2.5 shadow-2xs">
          <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
          <div className="flex-1 font-medium">{actionSuccess}</div>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-400 hover:text-emerald-600">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Hospital Admin Sub-view Switcher */}
      {isHospitalAdmin && (
        <div className="flex items-center gap-2 p-1 bg-slate-100 rounded-xl w-fit">
          <button
            onClick={() => setActiveSubView('chart')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeSubView === 'chart'
                ? 'bg-white text-slate-900 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Hospital Transfers
          </button>
          <button
            onClick={() => setActiveSubView('inbox')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeSubView === 'inbox'
                ? 'bg-white text-slate-900 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Inbox className="w-3.5 h-3.5 text-[#F08080]" />
            <span>Hospital Admin Inbox</span>
            {inboxTransfers.filter((t) => t.to_hospital_id === userHospital && t.status === 'REQUESTED').length > 0 && (
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
            )}
          </button>
        </div>
      )}

      {/* SUBVIEW: Hospital Admin Transfer Inbox */}
      {activeSubView === 'inbox' && isHospitalAdmin ? (
        <div className="bg-white rounded-xl border border-slate-200 p-5 sm:p-6 shadow-2xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-100">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg bg-[#FFF0ED] text-[#B84E4E] flex items-center justify-center">
                <Inbox className="w-5 h-5 text-[#F08080]" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Hospital Admin Transfer Inbox</h3>
                <p className="text-xs text-slate-500">
                  Facility: <strong className="font-mono text-slate-700">{userHospital}</strong>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-lg">
              <button
                onClick={() => setInboxFilter('incoming')}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                  inboxFilter === 'incoming' ? 'bg-white text-slate-900 shadow-2xs font-bold' : 'text-slate-600'
                }`}
              >
                Incoming ({inboxTransfers.filter((t) => t.to_hospital_id === userHospital).length})
              </button>
              <button
                onClick={() => setInboxFilter('outgoing')}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                  inboxFilter === 'outgoing' ? 'bg-white text-slate-900 shadow-2xs font-bold' : 'text-slate-600'
                }`}
              >
                Outgoing ({inboxTransfers.filter((t) => t.from_hospital_id === userHospital).length})
              </button>
              <button
                onClick={() => setInboxFilter('all')}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                  inboxFilter === 'all' ? 'bg-white text-slate-900 shadow-2xs font-bold' : 'text-slate-600'
                }`}
              >
                All ({inboxTransfers.length})
              </button>
            </div>
          </div>

          {filteredInbox.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-xs bg-slate-50 rounded-xl border border-slate-100">
              No transfer requests found in this view.
            </div>
          ) : (
            <div className="space-y-3">
              {filteredInbox.map((t) => {
                const isIncoming = t.to_hospital_id === userHospital;
                const canAccept = isIncoming && t.status === 'REQUESTED';

                return (
                  <div
                    key={t.id}
                    className="p-4 rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-2xs"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-bold text-slate-900">{t.id}</span>
                        <span className="text-xs px-2 py-0.5 rounded-full font-mono bg-slate-100 text-slate-700">
                          Patient: <strong>{t.patient_id}</strong>
                        </span>
                        <span
                          className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${
                            t.status === 'COMPLETED'
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : t.status === 'REJECTED'
                              ? 'bg-rose-50 text-rose-700 border-rose-200'
                              : t.status === 'CANCELLED'
                              ? 'bg-slate-100 text-slate-600 border-slate-200'
                              : 'bg-amber-50 text-amber-700 border-amber-200'
                          }`}
                        >
                          {t.status}
                        </span>
                      </div>
                      <div className="text-xs text-slate-600">
                        Route: <strong className="font-mono text-slate-800">{t.from_hospital_id}</strong> &rarr;{' '}
                        <strong className="font-mono text-slate-800">{t.to_hospital_id}</strong>
                        {t.reason && <span className="ml-2 italic text-slate-500">&mdash; &ldquo;{t.reason}&rdquo;</span>}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {canAccept && (
                        <>
                          <button
                            onClick={() => handleAcceptTransfer(t.id)}
                            disabled={isActionLoading}
                            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 transition-colors disabled:opacity-50"
                          >
                            Accept Transfer
                          </button>
                          <button
                            onClick={() => handleRejectTransfer(t.id)}
                            disabled={isActionLoading}
                            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 transition-colors disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {!isIncoming && t.status === 'REQUESTED' && (
                        <button
                          onClick={() => handleCancelTransfer(t.id)}
                          disabled={isActionLoading}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      )}
                      <span className="text-[11px] text-slate-400 font-mono">
                        {t.created_at ? new Date(t.created_at).toLocaleDateString() : 'Recent'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        <>
          {/* SECTION 1: Patient Consent Records (Exclusive to Patient Account) */}
          {isPatient && (
            <div className="bg-white rounded-xl border border-slate-200 p-5 sm:p-6 shadow-2xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                    <ShieldCheck className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Patient Consent Authorizations</h3>
                    <p className="text-xs text-slate-500">Legal medical data sharing consents on file</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setIsGrantModalOpen(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 rounded-lg transition-colors cursor-pointer"
                  >
                    <PlusCircle className="w-3.5 h-3.5" />
                    <span>Grant New Consent</span>
                  </button>
                  <span className="text-xs font-mono bg-slate-100 px-2 py-0.5 rounded-full text-slate-600">
                    {consents.length} on file
                  </span>
                </div>
              </div>

              {consents.length === 0 ? (
                <div className="p-6 text-center text-slate-500 text-xs bg-slate-50 rounded-lg border border-slate-100">
                  No active cross-clinic consent documents recorded for this chart. Click &ldquo;Grant New Consent&rdquo; to author an authorization.
                </div>
              ) : (
                <div className="space-y-3">
                  {consents.map((c) => {
                    const isRevoked = c.status === 'REVOKED';
                    const isActive = c.status === 'ACTIVE';

                    return (
                      <div
                        key={c.id}
                        className="p-4 rounded-lg border border-slate-200 hover:border-slate-300 transition-colors bg-white flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-xs font-bold text-slate-800">{c.id}</span>
                            <span
                              className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
                                isActive
                                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                  : isRevoked
                                  ? 'bg-rose-50 text-rose-700 border-rose-200'
                                  : 'bg-amber-50 text-amber-700 border-amber-200'
                              }`}
                            >
                              {c.status}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-md bg-slate-100 font-mono text-slate-700">
                              Target: {c.granted_to_hospital_id || c.org_id}
                            </span>
                            {c.recorded_on_behalf && (
                              <span className="text-[11px] px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 border border-purple-200 flex items-center gap-1 font-medium">
                                <UserCheck className="w-3 h-3" /> Recorded on Behalf
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-700 font-medium">
                            Purpose: {c.purpose || 'Continuity of fertility care'} &bull; Scope: {c.scope || 'ALL_RECORDS'}
                          </p>
                          <p className="text-xs text-slate-500">
                            {c.granted_by ? `Granted by: ${c.granted_by}` : 'Authorized patient consent'}
                            {c.expires_at && ` &bull; Expires: ${new Date(c.expires_at).toLocaleDateString()}`}
                            {c.revoked_at && ` &bull; Revoked: ${new Date(c.revoked_at).toLocaleDateString()}`}
                          </p>
                        </div>

                        <div className="flex items-center gap-3 shrink-0">
                          {isActive && (
                            <button
                              type="button"
                              onClick={() => handleRevokeConsent(c.id)}
                              disabled={isActionLoading}
                              className="px-2.5 py-1 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-md transition-colors disabled:opacity-50"
                            >
                              Revoke Consent
                            </button>
                          )}
                          <span className="text-xs text-slate-400 font-mono">
                            {c.granted_at ? new Date(c.granted_at).toLocaleDateString() : 'Recorded'}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* SECTION 2: Cross-Hospital Transfer Requests */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 sm:p-6 shadow-2xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[#FFF0ED] text-[#B84E4E] flex items-center justify-center">
                  <ArrowRightLeft className="w-4 h-4 text-[#F08080]" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Hospital Transfer Requests</h3>
                  <p className="text-xs text-slate-500">Cross-hospital record exchange and transfer workflow</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsTransferModalOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#A83232] bg-[#FFF0ED] border border-[#F8AD9D] hover:bg-[#FEEBE3] rounded-lg transition-colors"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Request Transfer</span>
                </button>
                <span className="text-xs font-mono bg-slate-100 px-2 py-0.5 rounded-full text-slate-600">
                  {transfers.length} records
                </span>
              </div>
            </div>

            {transfers.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs bg-slate-50 rounded-lg border border-slate-100">
                No transfer requests currently registered. Click &ldquo;Request Transfer&rdquo; to initiate a clinic transfer.
              </div>
            ) : (
              <div className="space-y-4">
                {transfers.map((t) => {
                  const isCompleted = t.status === 'COMPLETED';
                  const isRejected = t.status === 'REJECTED';
                  const isCancelled = t.status === 'CANCELLED';
                  const isRequested = t.status === 'REQUESTED';

                  const canAdminDecide = isHospitalAdmin && t.to_hospital_id === userHospital && isRequested;

                  return (
                    <div
                      key={t.id}
                      className="p-4 sm:p-5 rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-colors shadow-2xs space-y-3"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs font-bold text-slate-900">{t.id}</span>
                          <span
                            className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${
                              isCompleted
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : isRejected
                                ? 'bg-rose-50 text-rose-700 border-rose-200'
                                : isCancelled
                                ? 'bg-slate-100 text-slate-600 border-slate-200'
                                : 'bg-amber-50 text-amber-700 border-amber-200'
                            }`}
                          >
                            {t.status}
                          </span>
                          <span className="text-xs text-slate-600">
                            From: <strong className="font-mono text-slate-800">{t.from_hospital_id}</strong> &rarr; To:{' '}
                            <strong className="font-mono text-slate-800">{t.to_hospital_id}</strong>
                          </span>
                          {isRequested && (
                            t.has_active_consent ? (
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1">
                                <ShieldCheck className="w-3 h-3 text-emerald-600" /> Active Consent Verified
                              </span>
                            ) : (
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-900 border border-amber-200 flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3 text-amber-600" /> Consent Required (S7)
                              </span>
                            )
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          {/* PATIENT ACTIONS: Accept & Transfer or Revoke Transfer */}
                          {isPatient && isRequested && (
                            <>
                              <button
                                onClick={() => setTransferToConfirm(t)}
                                disabled={isActionLoading}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-2xs transition-colors cursor-pointer disabled:opacity-50"
                              >
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>Accept &amp; Transfer</span>
                              </button>
                              <button
                                onClick={() => handleRejectTransfer(t.id)}
                                disabled={isActionLoading}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                              >
                                <XCircle className="w-3.5 h-3.5 text-rose-600" />
                                <span>Revoke Transfer</span>
                              </button>
                            </>
                          )}

                          {/* CLINICIAN ACTIONS: Awaiting Patient Authorization when consent is not yet granted */}
                          {!isPatient && isRequested && !t.has_active_consent && (
                            <div className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold text-amber-800 bg-amber-50 border border-amber-200 rounded-lg">
                              <Clock className="w-3.5 h-3.5 text-amber-600" />
                              <span>Awaiting Patient Authorization</span>
                            </div>
                          )}

                          {/* Receiving Hospital Admin finalization once consent is verified */}
                          {!isPatient && canAdminDecide && t.has_active_consent && (
                            <>
                              <button
                                onClick={() => handleAcceptTransfer(t.id)}
                                disabled={isActionLoading}
                                className="px-2.5 py-1 text-xs font-semibold rounded-md text-white bg-emerald-600 hover:bg-emerald-700 cursor-pointer shadow-2xs"
                              >
                                Accept
                              </button>
                              <button
                                onClick={() => handleRejectTransfer(t.id)}
                                disabled={isActionLoading}
                                className="px-2.5 py-1 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-md transition-colors disabled:opacity-50"
                              >
                                Reject
                              </button>
                            </>
                          )}

                          {/* Non-patient cancel button */}
                          {!isPatient && isRequested && (
                            <button
                              onClick={() => handleCancelTransfer(t.id)}
                              disabled={isActionLoading}
                              className="px-2.5 py-1 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors disabled:opacity-50"
                            >
                              Cancel
                            </button>
                          )}
                        </div>
                      </div>

                      {t.reason && (
                        <p className="text-xs text-slate-600 italic bg-slate-50 p-2 rounded border border-slate-100">
                          &ldquo;{t.reason}&rdquo;
                        </p>
                      )}

                      {/* Status Timeline */}
                      <div className="pt-2 border-t border-slate-100">
                        <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2">Workflow Timeline</p>
                        <div className="flex items-center gap-2 text-xs flex-wrap">
                          {/* Step 1: Requested */}
                          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-50 text-amber-800 border border-amber-200">
                            <Clock className="w-3.5 h-3.5" />
                            <span>1. Requested</span>
                          </div>
                          <span className="text-slate-300">&rarr;</span>

                          {/* Step 2: Consent Check */}
                          <div
                            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border ${
                              t.consent_id || isCompleted
                                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                : 'bg-slate-50 text-slate-500 border-slate-200'
                            }`}
                          >
                            <ShieldCheck className="w-3.5 h-3.5" />
                            <span>2. Consent Verified {t.consent_id ? `(${t.consent_id})` : ''}</span>
                          </div>
                          <span className="text-slate-300">&rarr;</span>

                          {/* Step 3: Resolution */}
                          <div
                            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border ${
                              isCompleted
                                ? 'bg-emerald-600 text-white border-emerald-600'
                                : isRejected
                                ? 'bg-rose-600 text-white border-rose-600'
                                : isCancelled
                                ? 'bg-slate-200 text-slate-700 border-slate-300'
                                : 'bg-slate-50 text-slate-400 border-slate-200'
                            }`}
                          >
                            {isCompleted ? (
                              <>
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>3. Completed & Transferred</span>
                              </>
                            ) : isRejected ? (
                              <>
                                <XCircle className="w-3.5 h-3.5" />
                                <span>3. Rejected</span>
                              </>
                            ) : isCancelled ? (
                              <>
                                <XCircle className="w-3.5 h-3.5" />
                                <span>3. Cancelled</span>
                              </>
                            ) : (
                              <span>3. Awaiting Review</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}

      {/* MODAL: Grant Consent */}
      {isGrantModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-600" />
                <h3 className="text-sm font-bold text-slate-900">Grant Patient Transfer Consent</h3>
              </div>
              <button onClick={() => setIsGrantModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleGrantConsent} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Target Hospital Facility ID</label>
                <input
                  type="text"
                  value={targetHospital}
                  onChange={(e) => setTargetHospital(e.target.value)}
                  placeholder="e.g. ORG-B"
                  required
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs font-mono focus:outline-none focus:border-[#F08080]"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Consent Purpose</label>
                <input
                  type="text"
                  value={purpose}
                  onChange={(e) => setPurpose(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-[#F08080]"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Record Scope</label>
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-[#F08080]"
                >
                  <option value="ALL_RECORDS">ALL_RECORDS (Full clinical history)</option>
                  <option value="CYCLE_ONLY">CYCLE_ONLY (Specific treatment cycles)</option>
                  <option value="DIAGNOSTICS_ONLY">DIAGNOSTICS_ONLY (Lab & imaging only)</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Optional Expiry Date</label>
                <input
                  type="date"
                  value={expiresAt}
                  onChange={(e) => setExpiresAt(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-[#F08080]"
                />
              </div>

              {isHospitalAdmin && (
                <div className="p-2.5 bg-purple-50 border border-purple-200 rounded-lg text-[11px] text-purple-800">
                  You are recording this consent as Hospital Admin on the patient&rsquo;s behalf. It will be flagged as such and audited.
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsGrantModalOpen(false)}
                  className="px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isActionLoading}
                  className="px-4 py-1.5 rounded-lg font-semibold text-white bg-emerald-600 hover:bg-emerald-700 transition-colors disabled:opacity-50"
                >
                  {isActionLoading ? 'Saving...' : 'Grant Consent'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Request Transfer */}
      {isTransferModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <ArrowRightLeft className="w-5 h-5 text-[#F08080]" />
                <h3 className="text-sm font-bold text-slate-900">Initiate Hospital Transfer Request</h3>
              </div>
              <button onClick={() => setIsTransferModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleRequestTransfer} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Receiving Target Hospital ID</label>
                <input
                  type="text"
                  value={transferTargetHospital}
                  onChange={(e) => setTransferTargetHospital(e.target.value)}
                  placeholder="e.g. ORG-B"
                  required
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs font-mono focus:outline-none focus:border-[#F08080]"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Transfer Rationale / Reason</label>
                <textarea
                  rows={3}
                  value={transferReason}
                  onChange={(e) => setTransferReason(e.target.value)}
                  placeholder="e.g. Relocation, second opinion, or specialized embryology"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-[#F08080]"
                />
              </div>

              {/* Duplicate Transfer Guard */}
              {transfers.some((t) => t.status === 'REQUESTED') && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="block font-bold">Duplicate Transfer Blocked</strong>
                    <span>A transfer request is already pending for this patient chart. Duplicate or concurrent transfers are not permitted.</span>
                  </div>
                </div>
              )}

              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-[11px] text-amber-800 space-y-1">
                <p className="font-semibold">Transfer Invariants:</p>
                <p>&bull; Records are never moved, copied, or deleted; each keeps its origin badge.</p>
                <p>&bull; Active patient consent must exist before the receiving clinic can accept.</p>
                <p>&bull; Upon acceptance, the sending hospital access becomes Read-Only.</p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsTransferModalOpen(false)}
                  className="px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isActionLoading || transfers.some((t) => t.status === 'REQUESTED')}
                  className="px-4 py-1.5 rounded-lg font-semibold text-white bg-[#F08080] hover:bg-[#B84E4E] transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {isActionLoading ? 'Submitting...' : 'Submit Transfer Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Confirm Transfer */}
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
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
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
                disabled={isActionLoading}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  const targetId = transferToConfirm.id;
                  setTransferToConfirm(null);
                  await handleAcceptTransfer(targetId);
                }}
                disabled={isActionLoading}
                className="flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-peach-xs transition-all disabled:opacity-50 cursor-pointer"
              >
                {isActionLoading ? (
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
