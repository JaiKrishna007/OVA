import React, { useState, useEffect, useRef } from 'react';
import { claimsApi, ApiClientError } from '../services/api';
import type { ClaimEvidenceResponse } from '../types/api';
import {
  X,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Building2,
  Calendar,
  User,
  FileText,
  Loader2,
  AlertTriangle,
  Fingerprint,
} from 'lucide-react';

interface EvidenceDrawerProps {
  claimId: string | null;
  onClose: () => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({ claimId, onClose }) => {
  const [data, setData] = useState<ClaimEvidenceResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const highlightRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!claimId) {
      setData(null);
      return;
    }

    const fetchEvidence = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const resp = await claimsApi.getEvidence(claimId);
        setData(resp);
      } catch (err: unknown) {
        if (err instanceof ApiClientError) {
          setError(err.message || `Failed to fetch evidence for claim ${claimId}`);
        } else {
          setError('Network error while retrieving claim evidence.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchEvidence();
  }, [claimId]);

  useEffect(() => {
    if (highlightRef.current) {
      const timer = setTimeout(() => {
        highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [data]);

  if (!claimId) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-xs flex justify-end animate-in fade-in duration-200">
      <div className="w-full max-w-xl bg-white shadow-peach-xl flex flex-col h-full border-l border-[#FBC4AB]/40 animate-in slide-in-from-right duration-200">
        {/* Drawer Header */}
        <div className="px-6 py-4.5 border-b border-[#FBC4AB]/30 flex items-center justify-between bg-gradient-to-r from-[#FFF9F7] to-[#FFF5F2]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#FFF0ED] text-[#822828] border border-[#F8AD9D] flex items-center justify-center shadow-peach-xs">
              <ShieldCheck className="w-4 h-4 text-[#F08080]" />
            </div>
            <div>
              <h2 className="text-sm font-extrabold text-slate-900 flex items-center gap-2 tracking-tight">
                <span>Clinical Fact Evidence</span>
                <span className="font-mono text-[11px] font-semibold text-[#822828] bg-[#FFF0ED] px-2 py-0.5 rounded-md border border-[#F8AD9D]/50">
                  {claimId}
                </span>
              </h2>
              <p className="text-[11px] text-slate-500 font-medium">
                Ground-truth provenance and 4-point verification checklist
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-[#822828] hover:bg-[#FFF0ED] btn-interactive transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading && (
            <div className="py-20 text-center">
              <Loader2 className="w-7 h-7 text-[#F08080] animate-spin mx-auto mb-2" />
              <p className="text-xs font-semibold text-slate-600">Retrieving source record and ground-truth text...</p>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Unable to load evidence</p>
                <p className="mt-0.5 text-rose-700">{error}</p>
              </div>
            </div>
          )}

          {data && !isLoading && (
            <>
              {/* 1. Value Card */}
              <div className="bg-[#FFFDFB] rounded-xl border border-[#FBC4AB] p-4.5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Extracted Clinical Fact
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                      data.claim.validation_status === 'VERIFIED'
                        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                        : data.claim.validation_status === 'FLAGGED'
                        ? 'bg-amber-50 text-amber-800 border border-amber-200'
                        : 'bg-rose-50 text-rose-800 border border-rose-200'
                    }`}
                  >
                    {data.claim.validation_status}
                  </span>
                </div>

                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold font-mono text-[#A83232]">
                    {data.claim.value_text ?? data.claim.value_num ?? 'N/A'}
                  </span>
                  {data.claim.unit && (
                    <span className="text-xs text-slate-600 font-semibold">{data.claim.unit}</span>
                  )}
                  <span className="text-xs text-slate-400 font-medium ml-2">
                    ({data.claim.field})
                  </span>
                </div>

                {data.claim.event_date && (
                  <div className="text-xs text-slate-500 flex items-center gap-1.5 pt-2 border-t border-slate-100">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    <span>Event Date: <strong className="text-slate-700 font-mono">{data.claim.event_date}</strong></span>
                  </div>
                )}
              </div>

              {/* 2. Source Record Metadata */}
              <div className="bg-slate-50 rounded-xl border border-slate-200 p-4.5 space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200/60 pb-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-slate-500" />
                    <span>Source Record Metadata</span>
                  </span>
                  <span className="font-mono text-xs font-bold text-[#A83232] bg-white px-2 py-0.5 rounded border border-slate-200">
                    {data.source_record.id}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Origin Hospital</span>
                    <span className="font-semibold text-slate-800 flex items-center gap-1 mt-0.5">
                      <Building2 className="w-3.5 h-3.5 text-[#F08080] shrink-0" />
                      <span className="truncate">{data.source_record.hospital || data.source_record.origin_org || 'Originating Clinic'}</span>
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Record Type</span>
                    <span className="font-semibold text-slate-800 capitalize mt-0.5 block truncate">
                      {(data.source_record.type || 'Clinical Document').replace(/_/g, ' ')}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Record Date</span>
                    <span className="font-mono text-slate-700 mt-0.5 block">
                      {data.source_record.date || 'Not specified'}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Uploader / Author</span>
                    <span className="text-slate-700 flex items-center gap-1 mt-0.5 truncate">
                      <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span>{data.source_record.uploader || 'System Imported'}</span>
                    </span>
                  </div>
                </div>
              </div>

              {/* 3. Evidence Text with Highlighted Span (SAFE PLAIN TEXT RENDERING) */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                    <Fingerprint className="w-4 h-4 text-[#F08080]" />
                    <span>Source Evidence Sentence (Exact Span Highlighted)</span>
                  </label>
                  <span className="text-[10px] font-mono text-slate-400">
                    [{data.evidence.span_start}:{data.evidence.span_end}]
                  </span>
                </div>

                {/* Plain-text JSX container: NEVER renders raw HTML */}
                <div className="bg-white rounded-xl border border-slate-200 p-4 font-mono text-xs leading-relaxed text-slate-800 shadow-2xs whitespace-pre-wrap">
                  <span>{data.evidence.prefix}</span>
                  <mark
                    ref={(el) => { highlightRef.current = el; }}
                    className="bg-[#FFE5DF] text-[#A83232] font-bold px-1.5 py-0.5 rounded border border-[#F8AD9D] inline-block shadow-2xs mx-0.5"
                  >
                    {data.evidence.highlighted_text}
                  </mark>
                  <span>{data.evidence.suffix}</span>
                </div>

                {data.evidence.evidence_sentence && (
                  <p className="text-[11px] text-slate-500 italic pl-1">
                    Isolated statement: &ldquo;{data.evidence.evidence_sentence}&rdquo;
                  </p>
                )}
              </div>

              {/* 4. Verification Checklist (4 items) */}
              <div className="bg-slate-50/70 rounded-xl border border-slate-200 p-4 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-200">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Validation Checks Checklist
                  </h4>
                  <span className="text-[11px] text-slate-500 font-medium">
                    {data.validation_checks.filter((c) => c.passed).length}/{data.validation_checks.length} Passed
                  </span>
                </div>

                <div className="space-y-2.5">
                  {data.validation_checks.map((check, idx) => (
                    <div
                      key={idx}
                      className="bg-white rounded-lg border border-slate-200/80 p-3 flex items-start gap-3 shadow-2xs"
                    >
                      {check.passed ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      ) : (
                        <XCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-bold text-slate-800">
                            {check.label}
                          </span>
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.2 rounded ${
                              check.passed
                                ? 'bg-emerald-50 text-emerald-700'
                                : 'bg-rose-50 text-rose-700'
                            }`}
                          >
                            {check.passed ? 'PASS' : 'FAIL'}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5 leading-normal">
                          {check.detail}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Drawer Footer */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50/60 flex items-center justify-between text-xs text-slate-500">
          <span>Per governance rule: Record text is never modified</span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-lg text-xs transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
