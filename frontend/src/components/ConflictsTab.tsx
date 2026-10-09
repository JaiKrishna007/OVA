import React, { useState, useEffect } from 'react';
import { conflictsApi, ApiClientError } from '../services/api';
import type { ConflictRecordItem } from '../types/api';
import {
  AlertTriangle,
  ArrowRightLeft,
  Building2,
  Calendar,
  CheckCircle2,
  Loader2,
  ExternalLink,
  MessageSquare,
  ShieldAlert,
} from 'lucide-react';

interface ConflictsTabProps {
  patientId: string;
  onOpenEvidence?: (claimId: string) => void;
}

export const ConflictsTab: React.FC<ConflictsTabProps> = ({ patientId, onOpenEvidence }) => {
  const [conflicts, setConflicts] = useState<ConflictRecordItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Acknowledgment Modal state
  const [activeConflictForAck, setActiveConflictForAck] = useState<ConflictRecordItem | null>(null);
  const [ackNote, setAckNote] = useState('');
  const [isSubmittingAck, setIsSubmittingAck] = useState(false);
  const [ackError, setAckError] = useState<string | null>(null);

  const loadConflicts = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await conflictsApi.list(patientId);
      setConflicts(data);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Failed to load patient conflicts.');
      } else {
        setError('Network error while retrieving clinical conflicts.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadConflicts();
  }, [patientId]);

  const handleAcknowledgeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeConflictForAck || !ackNote.trim()) return;

    setIsSubmittingAck(true);
    setAckError(null);
    try {
      await conflictsApi.acknowledge(activeConflictForAck.id, ackNote.trim());
      setActiveConflictForAck(null);
      setAckNote('');
      await loadConflicts();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setAckError(err.message || 'Failed to acknowledge conflict.');
      } else {
        setAckError('Network error while recording clinician acknowledgment.');
      }
    } finally {
      setIsSubmittingAck(false);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
        <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
        <p className="text-xs font-semibold text-slate-700">Loading cross-record conflicts...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
        <p className="font-semibold">Unable to load conflicts</p>
        <p className="mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Clinical Governance Banner */}
      <div className="bg-[#FFF8F6] rounded-xl border border-[#F4978E] p-5 shadow-2xs flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-[#F08080] text-white flex items-center justify-center shrink-0 shadow-xs">
          <AlertTriangle className="w-5 h-5" />
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">
              Conflicting documented values. Clinician review required.
            </h3>
            <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D]">
              {conflicts.length} Documented
            </span>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Per clinical safety standard S8: When divergent values are documented across hospitals or records, both are displayed side-by-side with full provenance. Clinician acknowledgment is recorded with a note and never alters any source value or chooses a winner.
          </p>
        </div>
      </div>

      {/* 2. Conflicts List */}
      {conflicts.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-2xs space-y-2">
          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
          <h4 className="text-sm font-bold text-slate-800">No Active Clinical Conflicts</h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            All extracted values across source records are concordant and within protocol tolerance.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {conflicts.map((conflict) => {
            const isAck = conflict.status === 'ACKNOWLEDGED';

            return (
              <div
                key={conflict.id}
                className="bg-white rounded-xl border border-[#FBC4AB] p-5 sm:p-6 shadow-2xs space-y-4"
              >
                {/* Conflict Card Header */}
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-[#FFF0ED] text-[#A83232]">
                      <ArrowRightLeft className="w-4 h-4" />
                    </span>
                    <div>
                      <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
                        {conflict.field.replace(/_/g, ' ')}
                      </h4>
                      <span className="font-mono text-[10px] text-slate-400">
                        {conflict.id}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                        isAck
                          ? 'bg-slate-100 text-slate-700 border border-slate-200'
                          : 'bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D]'
                      }`}
                    >
                      {isAck ? 'ACKNOWLEDGED' : 'OPEN - Clinician review required'}
                    </span>
                  </div>
                </div>

                {/* Side-by-Side Comparison */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Side A */}
                  <div className="bg-[#FFFDFB] rounded-xl border border-slate-200 p-4.5 space-y-3">
                    <div className="flex items-center justify-between text-xs border-b border-slate-100 pb-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Documented Record A
                      </span>
                      {conflict.date_a && (
                        <span className="font-mono text-slate-500 text-[11px] flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-slate-400" />
                          <span>{conflict.date_a}</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-baseline gap-2">
                      <span className="text-3xl font-bold font-mono text-[#A83232]">
                        {conflict.value_a ?? 'Unknown'}
                      </span>
                      {conflict.unit_a && (
                        <span className="text-xs text-slate-600 font-semibold">{conflict.unit_a}</span>
                      )}
                    </div>

                    <div className="space-y-1.5 text-xs text-slate-600">
                      <div className="flex items-center gap-1.5">
                        <Building2 className="w-3.5 h-3.5 text-[#F08080] shrink-0" />
                        <span className="font-medium text-slate-800 truncate">
                          {conflict.hospital_a || 'Origin Clinic'}
                        </span>
                      </div>

                      {(conflict.source_id_a || conflict.source_a) && (
                        <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                          <span className="font-mono text-[11px] text-slate-500">
                            Source: {conflict.source_id_a || conflict.source_a}
                          </span>
                          {(conflict.claim_id_a || conflict.claim_a_id) && (
                            <button
                              type="button"
                              onClick={() => onOpenEvidence?.(conflict.claim_id_a || conflict.claim_a_id!)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-[#A83232] bg-[#FFF0ED] hover:bg-[#FEEBE3] border border-[#F8AD9D] rounded-lg transition-colors"
                            >
                              <span>Inspect Evidence</span>
                              <ExternalLink className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {conflict.evidence_text_a && (
                      <p className="text-[11px] font-mono text-slate-500 bg-slate-50 p-2 rounded border border-slate-100">
                        &ldquo;{conflict.evidence_text_a}&rdquo;
                      </p>
                    )}
                  </div>

                  {/* Side B */}
                  <div className="bg-[#FFFDFB] rounded-xl border border-slate-200 p-4.5 space-y-3">
                    <div className="flex items-center justify-between text-xs border-b border-slate-100 pb-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Documented Record B
                      </span>
                      {conflict.date_b && (
                        <span className="font-mono text-slate-500 text-[11px] flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-slate-400" />
                          <span>{conflict.date_b}</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-baseline gap-2">
                      <span className="text-3xl font-bold font-mono text-amber-800">
                        {conflict.value_b ?? 'Unknown'}
                      </span>
                      {conflict.unit_b && (
                        <span className="text-xs text-slate-600 font-semibold">{conflict.unit_b}</span>
                      )}
                    </div>

                    <div className="space-y-1.5 text-xs text-slate-600">
                      <div className="flex items-center gap-1.5">
                        <Building2 className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                        <span className="font-medium text-slate-800 truncate">
                          {conflict.hospital_b || 'External Clinic'}
                        </span>
                      </div>

                      {(conflict.source_id_b || conflict.source_b) && (
                        <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                          <span className="font-mono text-[11px] text-slate-500">
                            Source: {conflict.source_id_b || conflict.source_b}
                          </span>
                          {(conflict.claim_id_b || conflict.claim_b_id) && (
                            <button
                              type="button"
                              onClick={() => onOpenEvidence?.(conflict.claim_id_b || conflict.claim_b_id!)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-300 rounded-lg transition-colors"
                            >
                              <span>Inspect Evidence</span>
                              <ExternalLink className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {conflict.evidence_text_b && (
                      <p className="text-[11px] font-mono text-slate-500 bg-slate-50 p-2 rounded border border-slate-100">
                        &ldquo;{conflict.evidence_text_b}&rdquo;
                      </p>
                    )}
                  </div>
                </div>

                {/* Card Footer: Acknowledgment Action / Status */}
                <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
                  <div className="text-xs text-slate-500">
                    {isAck ? (
                      <div className="flex items-center gap-2 text-slate-700">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>
                          Acknowledged by <strong>{conflict.ack_by || conflict.acknowledged_by || 'Dr. Rao'}</strong> on{' '}
                          <span className="font-mono text-[11px]">{conflict.ack_at || conflict.acknowledged_at || 'Recently'}</span>
                        </span>
                      </div>
                    ) : (
                      <span className="font-medium text-slate-600">
                        Clinical action: Review both records and document acknowledgment note.
                      </span>
                    )}
                  </div>

                  {!isAck && (
                    <button
                      type="button"
                      onClick={() => {
                        setActiveConflictForAck(conflict);
                        setAckNote('');
                        setAckError(null);
                      }}
                      className="px-3.5 py-1.5 bg-[#A83232] hover:bg-[#8F2B2B] text-white text-xs font-semibold rounded-lg shadow-xs transition-colors"
                    >
                      Acknowledge Conflict
                    </button>
                  )}
                </div>

                {/* Display Note if acknowledged */}
                {isAck && (conflict.ack_note || conflict.note) && (
                  <div className="bg-slate-50 rounded-lg p-3 border border-slate-200 text-xs text-slate-700 flex items-start gap-2">
                    <MessageSquare className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold text-slate-800">Clinician Note: </span>
                      <span>{conflict.ack_note || conflict.note}</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 3. Acknowledgment Modal with Required Note */}
      {activeConflictForAck && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D] flex items-center justify-center">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    Acknowledge Contradictory Clinical Findings
                  </h3>
                  <p className="text-xs text-slate-500">
                    Field: {activeConflictForAck.field} ({activeConflictForAck.id})
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-amber-50 rounded-xl p-3 border border-amber-200 text-xs text-amber-900 leading-relaxed">
              <strong>Clinical Governance Reminder:</strong> Acknowledging this conflict records your clinical review in the governance audit trail. Per safety rule S8, this does <em>not</em> alter any underlying documented value or select a winner.
            </div>

            {ackError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                {ackError}
              </div>
            )}

            <form onSubmit={handleAcknowledgeSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-800 mb-1.5">
                  Clinician Review Note <span className="text-[#A83232]">* (Required)</span>
                </label>
                <textarea
                  required
                  rows={3}
                  value={ackNote}
                  onChange={(e) => setAckNote(e.target.value)}
                  placeholder="e.g. Reviewed lab report difference; patient history notes re-test in external laboratory with different calibration standard. Will monitor during upcoming cycle."
                  className="w-full text-xs p-3 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#F8AD9D] focus:border-[#F08080] placeholder:text-slate-400"
                />
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setActiveConflictForAck(null)}
                  disabled={isSubmittingAck}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!ackNote.trim() || isSubmittingAck}
                  className="px-4 py-2 bg-[#A83232] hover:bg-[#8F2B2B] disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-xs transition-colors flex items-center gap-1.5"
                >
                  {isSubmittingAck ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Recording...</span>
                    </>
                  ) : (
                    <span>Confirm Acknowledgment</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
