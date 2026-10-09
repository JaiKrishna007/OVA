import React, { useState, useEffect } from 'react';
import { claimsApi, ApiClientError } from '../services/api';
import type { ClinicalClaimItem } from '../types/api';
import {
  ShieldAlert,
  CheckCircle2,
  Loader2,
  ExternalLink,
  Check,
  X,
  Building2,
  Calendar,
} from 'lucide-react';

interface ReviewQueueTabProps {
  patientId: string;
  onOpenEvidence?: (claimId: string) => void;
}

export const ReviewQueueTab: React.FC<ReviewQueueTabProps> = ({
  patientId,
  onOpenEvidence,
}) => {
  const [claims, setClaims] = useState<ClinicalClaimItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'FLAGGED' | 'REJECTED'>('ALL');

  // Action states
  const [processingClaimId, setProcessingClaimId] = useState<string | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);

  const loadClaims = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const allData = await claimsApi.list({ patient_id: patientId });
      // Filter for candidate claims that require clinician attention
      const candidateClaims = allData.filter(
        (c) => c.validation_status === 'FLAGGED' || c.validation_status === 'REJECTED'
      );
      setClaims(candidateClaims);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Failed to load claims review queue.');
      } else {
        setError('Network error while retrieving candidate claims.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadClaims();
  }, [patientId]);

  const handleAccept = async (claimId: string) => {
    setProcessingClaimId(claimId);
    setActionSuccessMessage(null);
    try {
      await claimsApi.accept(claimId, 'Clinician confirmed value matches clinical context');
      setActionSuccessMessage(`Claim ${claimId} accepted and promoted to VERIFIED.`);
      await loadClaims();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to accept claim');
    } finally {
      setProcessingClaimId(null);
    }
  };

  const handleReject = async (claimId: string) => {
    setProcessingClaimId(claimId);
    setActionSuccessMessage(null);
    try {
      await claimsApi.reject(claimId, 'Clinician rejected: inconsistent with source text');
      setActionSuccessMessage(`Claim ${claimId} marked as REJECTED.`);
      await loadClaims();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to reject claim');
    } finally {
      setProcessingClaimId(null);
    }
  };

  const filteredClaims = claims.filter((c) => {
    if (statusFilter === 'ALL') return true;
    return c.validation_status === statusFilter;
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
        <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
        <p className="text-xs font-semibold text-slate-700">Loading candidate claims review queue...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D] flex items-center justify-center shrink-0">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Clinician Extraction Review Queue
            </h3>
            <p className="text-xs text-slate-500">
              Review AI-extracted candidate claims flagged for verification or rejected by safety checks
            </p>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-lg text-xs font-semibold">
          <button
            type="button"
            onClick={() => setStatusFilter('ALL')}
            className={`px-3 py-1 rounded-md transition-colors ${
              statusFilter === 'ALL'
                ? 'bg-white text-slate-900 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            All ({claims.length})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('FLAGGED')}
            className={`px-3 py-1 rounded-md transition-colors ${
              statusFilter === 'FLAGGED'
                ? 'bg-amber-100 text-amber-900 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Flagged ({claims.filter((c) => c.validation_status === 'FLAGGED').length})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('REJECTED')}
            className={`px-3 py-1 rounded-md transition-colors ${
              statusFilter === 'REJECTED'
                ? 'bg-rose-100 text-rose-900 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Rejected ({claims.filter((c) => c.validation_status === 'REJECTED').length})
          </button>
        </div>
      </div>

      {actionSuccessMessage && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionSuccessMessage}</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
          {error}
        </div>
      )}

      {/* 2. Claims List */}
      {filteredClaims.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-2xs space-y-2">
          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
          <h4 className="text-sm font-bold text-slate-800">No Candidate Claims Pending Review</h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            All extracted facts for this patient are verified. No claims require manual doctor reconciliation.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredClaims.map((claim) => {
            const isFlagged = claim.validation_status === 'FLAGGED';
            const isProcessing = processingClaimId === claim.id;

            return (
              <div
                key={claim.id}
                className="bg-white rounded-xl border border-slate-200 p-4.5 shadow-2xs space-y-3 hover:border-slate-300 transition-colors"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-900">
                      {claim.field}
                    </span>
                    <span className="font-mono text-[10px] text-slate-400">
                      ({claim.id})
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        isFlagged
                          ? 'bg-amber-100 text-amber-900 border border-amber-300'
                          : 'bg-rose-100 text-rose-900 border border-rose-300'
                      }`}
                    >
                      {claim.validation_status}
                    </span>
                  </div>
                </div>

                {/* Claim details */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Candidate Value</span>
                    <span className="text-base font-bold font-mono text-[#A83232] mt-0.5 block">
                      {claim.value_text ?? claim.value_num ?? 'N/A'} {claim.unit || ''}
                    </span>
                  </div>

                  <div>
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Source & Hospital</span>
                    <span className="font-medium text-slate-700 flex items-center gap-1 mt-0.5 truncate">
                      <Building2 className="w-3.5 h-3.5 text-[#F08080] shrink-0" />
                      <span className="truncate">{claim.hospital_id || 'Origin Clinic'}</span>
                    </span>
                    <span className="font-mono text-[10px] text-slate-500 block">
                      Record: {claim.source_record_id}
                    </span>
                  </div>

                  <div>
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Event Date</span>
                    <span className="font-mono text-slate-700 mt-0.5 flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span>{claim.event_date || 'Undated'}</span>
                    </span>
                  </div>
                </div>

                {/* Reason codes */}
                {claim.reason_codes && claim.reason_codes.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="text-[10px] text-slate-400 font-semibold">Flags:</span>
                    {claim.reason_codes.map((rc, rIdx) => (
                      <span
                        key={rIdx}
                        className="font-mono text-[10px] px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded"
                      >
                        {rc}
                      </span>
                    ))}
                  </div>
                )}

                {/* Actions Bar */}
                <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => onOpenEvidence?.(claim.id)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-[#A83232] bg-[#FFF0ED] hover:bg-[#FEEBE3] border border-[#F8AD9D] rounded-lg transition-colors"
                  >
                    <span>Inspect Ground-Truth Evidence</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={isProcessing}
                      onClick={() => handleReject(claim.id)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-800 text-xs font-semibold rounded-lg border border-rose-300 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      <span>Reject</span>
                    </button>

                    <button
                      type="button"
                      disabled={isProcessing}
                      onClick={() => handleAccept(claim.id)}
                      className="inline-flex items-center gap-1 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow-2xs transition-colors disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Accept as Verified</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
