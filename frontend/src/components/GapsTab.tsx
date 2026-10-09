import React, { useState, useEffect } from 'react';
import { gapsApi, ApiClientError } from '../services/api';
import type { DocumentationGapItem } from '../types/api';
import {
  FileQuestion,
  CheckCircle2,
  Loader2,
  Calendar,
  ShieldCheck,
} from 'lucide-react';

interface GapsTabProps {
  patientId: string;
}

export const GapsTab: React.FC<GapsTabProps> = ({ patientId }) => {
  const [gaps, setGaps] = useState<DocumentationGapItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Acknowledgment Modal
  const [activeGapForAck, setActiveGapForAck] = useState<DocumentationGapItem | null>(null);
  const [ackNote, setAckNote] = useState('');
  const [isSubmittingAck, setIsSubmittingAck] = useState(false);
  const [ackError, setAckError] = useState<string | null>(null);

  const loadGaps = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await gapsApi.list(patientId);
      setGaps(data);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Failed to load documentation gaps.');
      } else {
        setError('Network error while retrieving care gaps.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadGaps();
  }, [patientId]);

  const handleAcknowledgeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeGapForAck || !ackNote.trim()) return;

    setIsSubmittingAck(true);
    setAckError(null);
    try {
      await gapsApi.acknowledge(activeGapForAck.id, ackNote.trim());
      setActiveGapForAck(null);
      setAckNote('');
      await loadGaps();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setAckError(err.message || 'Failed to acknowledge documentation gap.');
      } else {
        setAckError('Network error while recording gap acknowledgment.');
      }
    } finally {
      setIsSubmittingAck(false);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
        <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
        <p className="text-xs font-semibold text-slate-700">Evaluating clinical gap rules...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
        <p className="font-semibold">Unable to load clinical gaps</p>
        <p className="mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <div className="bg-amber-50/70 rounded-xl border border-amber-300 p-5 shadow-2xs flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-amber-500 text-white flex items-center justify-center shrink-0 shadow-xs">
          <FileQuestion className="w-5 h-5" />
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">
              Expected Clinical Protocol Documentation Gaps
            </h3>
            <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-white text-amber-900 border border-amber-300">
              {gaps.length} Expected Items
            </span>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Safety Rule S3: Missing tests or delayed follow-ups are explicitly identified as &ldquo;Not documented in records&rdquo;. The system never guesses or fills gaps. Clinicians can acknowledge or order the missing investigation.
          </p>
        </div>
      </div>

      {/* 2. Gaps List */}
      {gaps.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-2xs space-y-2">
          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
          <h4 className="text-sm font-bold text-slate-800">No Open Protocol Documentation Gaps</h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            All expected investigations and protocol records are documented for current treatment cycles.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {gaps.map((gap) => {
            const isAck = gap.status === 'ACKNOWLEDGED';

            return (
              <div
                key={gap.id}
                className="bg-white rounded-xl border border-amber-200 p-5 shadow-2xs flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 border-b border-slate-100 pb-2.5">
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">
                        {gap.expected_item}
                      </h4>
                      <span className="font-mono text-[10px] text-amber-800 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 mt-1 inline-block">
                        {gap.rule_id}
                      </span>
                    </div>

                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        isAck
                          ? 'bg-slate-100 text-slate-700 border border-slate-200'
                          : 'bg-amber-100 text-amber-900 border border-amber-300'
                      }`}
                    >
                      {gap.status}
                    </span>
                  </div>

                  {/* Triggering record & context */}
                  <div className="mt-3 space-y-2 text-xs text-slate-600">
                    {gap.trigger_event && (
                      <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 space-y-1">
                        <span className="text-[10px] uppercase font-bold text-slate-400 block">
                          Triggering Clinical Event
                        </span>
                        <p className="text-slate-800 font-medium">
                          {gap.trigger_event}
                        </p>
                        {gap.trigger_claim_id && (
                          <span className="font-mono text-[10px] text-slate-500 block">
                            Trigger claim: {gap.trigger_claim_id}
                          </span>
                        )}
                      </div>
                    )}

                    {gap.window_days && (
                      <p className="text-[11px] text-slate-500 flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-slate-400" />
                        <span>Expected within {gap.window_days} days of triggering event.</span>
                      </p>
                    )}
                  </div>
                </div>

                {/* Footer with Ack info or button */}
                <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                  {isAck ? (
                    <div className="space-y-1 w-full">
                      <div className="flex items-center gap-1.5 text-slate-700">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        <span className="text-[11px]">
                          Acknowledged by <strong>{gap.ack_by || 'Dr. Rao'}</strong>
                        </span>
                      </div>
                      {gap.ack_note && (
                        <p className="text-[11px] text-slate-500 italic bg-slate-50 p-1.5 rounded">
                          &ldquo;{gap.ack_note}&rdquo;
                        </p>
                      )}
                    </div>
                  ) : (
                    <>
                      <span className="text-slate-400 text-[11px] italic">
                        Not documented in records
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          setActiveGapForAck(gap);
                          setAckNote('');
                          setAckError(null);
                        }}
                        className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-lg text-xs transition-colors shadow-2xs"
                      >
                        Acknowledge Gap
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 3. Acknowledgment Modal */}
      {activeGapForAck && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-700 border border-amber-300 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    Acknowledge Expected Clinical Gap
                  </h3>
                  <p className="text-xs text-slate-500">
                    {activeGapForAck.expected_item} ({activeGapForAck.rule_id})
                  </p>
                </div>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Recording clinical acknowledgment indicates this protocol expectation was reviewed by the medical team. This item will remain marked as &ldquo;Not documented&rdquo; with the clinician&rsquo;s note attached.
            </p>

            {ackError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                {ackError}
              </div>
            )}

            <form onSubmit={handleAcknowledgeSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-800 mb-1.5">
                  Review Note <span className="text-[#A83232]">* (Required)</span>
                </label>
                <textarea
                  required
                  rows={3}
                  value={ackNote}
                  onChange={(e) => setAckNote(e.target.value)}
                  placeholder="e.g. Investigation ordered at external laboratory; awaiting results before scheduling transfer."
                  className="w-full text-xs p-3 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-300 focus:border-amber-500 placeholder:text-slate-400"
                />
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setActiveGapForAck(null)}
                  disabled={isSubmittingAck}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!ackNote.trim() || isSubmittingAck}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-xs transition-colors flex items-center gap-1.5"
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
