import React, { useState, useEffect } from 'react';
import { patientsApi, ApiClientError } from '../services/api';
import type {
  SummaryResponse,
  SummarySection,
  Citation,
} from '../types/api';
import { ConflictsPanel } from './ConflictsPanel';
import { MissingDataPanel } from './MissingDataPanel';
import { SourceViewer } from './SourceViewer';
import { StatementFeedbackModal } from './StatementFeedbackModal';
import {
  Sparkles,
  RefreshCw,
  Clock,
  AlertTriangle,
  FileText,
  CheckCircle2,
  AlertCircle,
  MessageSquare,
  FileCheck,
  Loader2,
  Download,
} from 'lucide-react';

interface SummaryTabProps {
  patientId: string;
}

const SECTION_SPEC_ORDER = [
  'profile_diagnosis',
  'prior_cycles',
  'protocols_medications',
  'follicular_development',
  'oocyte_retrieval',
  'embryo_details',
  'outcomes_pregnancy',
  'adverse_events',
  'current_stage',
  'baseline_profile',
  'stimulation_protocols',
  'oocyte_embryo',
  'transfers_outcomes',
  'complications_safety',
  'pending_followups',
];

const SECTION_TITLES: Record<string, string> = {
  profile_diagnosis: 'Baseline Profile & Diagnosis',
  prior_cycles: 'Prior Cycle History',
  protocols_medications: 'Stimulation Protocols & Medications',
  follicular_development: 'Follicular Development & Monitoring',
  oocyte_retrieval: 'Oocyte Retrieval (OPU)',
  embryo_details: 'Embryology & Embryo Development',
  outcomes_pregnancy: 'Transfers & Pregnancy Outcomes',
  adverse_events: 'Complications & Adverse Events',
  current_stage: 'Current Treatment Stage',
  baseline_profile: 'Baseline Profile & Ovarian Reserve',
  stimulation_protocols: 'Stimulation & Protocols',
  oocyte_embryo: 'Oocyte & Embryo Development',
  transfers_outcomes: 'Transfers & Outcomes',
  complications_safety: 'Complications & Safety',
  pending_followups: 'Pending Actions & Follow-ups',
};

export const SummaryTab: React.FC<SummaryTabProps> = ({ patientId }) => {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [viewMode, setViewMode] = useState<'snapshot' | 'detailed'>('detailed');
  const [isLoading, setIsLoading] = useState(true);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [regeneratingSection, setRegeneratingSection] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Active citation for split-pane source viewer
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  // Active statement for feedback modal
  const [feedbackStatement, setFeedbackStatement] = useState<{
    ref: string;
    text: string;
  } | null>(null);

  const [isDownloadingBrief, setIsDownloadingBrief] = useState(false);

  const loadSummary = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await patientsApi.getSummary(patientId, 'detailed');
      setSummary(data);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Unable to load clinical summary.');
      } else {
        setError('Network error while retrieving summary.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, [patientId]);

  const handleRegenerateWhole = async () => {
    setIsRegenerating(true);
    setError(null);
    try {
      const refreshed = await patientsApi.regenerateSummary(patientId);
      setSummary(refreshed);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Regeneration failed.');
    } finally {
      setIsRegenerating(false);
    }
  };

  const handleRegenerateSection = async (sectionKey: string) => {
    setRegeneratingSection(sectionKey);
    try {
      const refreshed = await patientsApi.regenerateSummary(patientId, [sectionKey]);
      setSummary(refreshed);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : `Failed to regenerate ${sectionKey}`);
    } finally {
      setRegeneratingSection(null);
    }
  };

  const handleDownloadBrief = async () => {
    setIsDownloadingBrief(true);
    try {
      const blob = await patientsApi.downloadBrief(patientId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `brief_${patientId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        alert(`Failed to download brief: ${err.message}`);
      } else {
        alert('Failed to download brief.');
      }
    } finally {
      setIsDownloadingBrief(false);
    }
  };

  const formatCitationChip = (c: Citation): string => {
    const parts = [];
    parts.push(c.source_id || (c.type ? c.type.replace(/_/g, ' ').toUpperCase() : 'DOC'));
    if (c.date) parts.push(c.date);
    if (c.origin) parts.push(c.origin);
    if (c.trust) {
      parts.push(c.trust === 'external_unverified' ? 'external_unverified' : 'verified');
    }
    return parts.join(' • ');
  };

  const getAssuranceBadge = (claim: any) => {
    const tier = claim?.assurance_tier;
    if (tier === 'NOTE_SUPPORTED') {
      return (
        <span
          title="Fact grounded and highlighted in clinical free-text note (Note-supported)"
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-sky-50 text-sky-800 border border-sky-300"
        >
          <FileText className="w-3 h-3 text-sky-600" />
          <span>Note-supported</span>
        </span>
      );
    }
    if (tier === 'STRUCTURED_VERIFIED') {
      return (
        <span
          title="Fact directly cross-referenced against structured EMR database table (Structured-verified)"
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-300"
        >
          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          <span>Structured-verified</span>
        </span>
      );
    }
    const isNoteSupported = Array.isArray(claim?.citations) && claim.citations.some(
      (c: any) =>
        c.type?.toLowerCase().includes('note') ||
        c.type?.toLowerCase().includes('summary') ||
        c.span != null
    );

    if (isNoteSupported) {
      return (
        <span
          title="Fact grounded and highlighted in clinical free-text note (Note-supported)"
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-sky-50 text-sky-800 border border-sky-300"
        >
          <FileText className="w-3 h-3 text-sky-600" />
          <span>Note-supported</span>
        </span>
      );
    }

    return (
      <span
        title="Fact directly cross-referenced against structured EMR database table (Structured-verified)"
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-300"
      >
        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
        <span>Structured-verified</span>
      </span>
    );
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
        <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
        <h3 className="text-base font-bold text-slate-800">
          Generating Grounded Clinical Summary...
        </h3>
        <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
          Building per-section context packs, running programmatic validator, and checking conflicts.
        </p>
      </div>
    );
  }

  if (error && !summary) {
    return (
      <div className="bg-white rounded-xl border border-rose-200 p-8 shadow-xs max-w-2xl mx-auto text-center space-y-4">
        <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto" />
        <h3 className="text-base font-bold text-slate-900">Summary Generation Error</h3>
        <p className="text-sm text-slate-600">{error}</p>
        <button
          onClick={loadSummary}
          className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-800"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      </div>
    );
  }

  if (!summary) return null;

  const summaryAny = summary as any;
  const sectionsMap = summary.content?.sections || summaryAny.sections || {};
  const conflictsList = summary.content?.conflicts_detected || summaryAny.conflicts || [];
  const notDocumentedList = summary.content?.missing_items || summaryAny.not_documented || [];
  const snapshotItems: any[] = Array.isArray(summaryAny.snapshot)
    ? summaryAny.snapshot
    : summary.content?.snapshot_text
    ? summary.content.snapshot_text.split('\n').filter((l: string) => l.trim().length > 0).map((t: string, i: number) => ({ line_no: i + 1, text: t, source_refs: [], assurance_tier: 'structured_verified' }))
    : [];
  const summaryId = summary.id || summaryAny.summary_id || '';
  const versionNum = summary.version || summaryAny.metadata?.version || 1;
  const dataVersionStr = summary.data_version || summaryAny.metadata?.data_version || '';
  const isStale = Boolean(summary.is_stale || summaryAny.is_stale);
  const isCacheHit = Boolean(summary.cache_hit || summaryAny.metadata?.from_cache);
  const genAt = summary.generated_at || summaryAny.metadata?.generated_at;

  const orderedSectionKeys = [
    ...SECTION_SPEC_ORDER.filter((k) => k in sectionsMap),
    ...Object.keys(sectionsMap).filter((k) => !SECTION_SPEC_ORDER.includes(k)),
  ];

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      {/* Left/Main Column: Summary View */}
      <div className="flex-1 min-w-0 space-y-6 w-full">
        {/* Top Controls Bar */}
        <div className="bg-white/95 backdrop-blur-md rounded-2xl border border-[#FBC4AB]/50 p-4 sm:p-5 shadow-peach-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-[#F08080]" />
                <span>AI Clinical Summary</span>
              </span>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#FFDAB9]/30 text-[#822828] border border-[#FBC4AB]/40">
                v{versionNum}
              </span>
              {isCacheHit && (
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200">
                  Cached
                </span>
              )}
            </div>

            <div className="text-xs text-slate-500 flex items-center gap-2 flex-wrap">
              <Clock className="w-3.5 h-3.5 text-[#F08080]" />
              <span>Generated: {genAt ? new Date(genAt).toLocaleString() : 'Recent'}</span>
              <span>&bull;</span>
              <span className="font-mono text-[11px] text-slate-400 truncate max-w-[150px]" title={dataVersionStr}>
                Data Hash: {dataVersionStr.slice(0, 10)}...
              </span>
            </div>
          </div>

          {/* Toggle & Whole Regenerate */}
          <div className="flex items-center gap-2.5 self-start sm:self-center">
            {/* Snapshot Toggle */}
            <div className="bg-[#FFF5F2] p-1 rounded-xl border border-[#FBC4AB]/30 flex items-center text-xs font-semibold">
              <button
                type="button"
                onClick={() => setViewMode('snapshot')}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  viewMode === 'snapshot'
                    ? 'bg-white text-[#822828] shadow-peach-xs font-bold border border-[#F8AD9D]/40'
                    : 'text-slate-600 hover:text-[#822828]'
                }`}
              >
                Snapshot (5 lines)
              </button>
              <button
                type="button"
                onClick={() => setViewMode('detailed')}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  viewMode === 'detailed'
                    ? 'bg-white text-[#822828] shadow-peach-xs font-bold border border-[#F8AD9D]/40'
                    : 'text-slate-600 hover:text-[#822828]'
                }`}
              >
                Detailed View
              </button>
            </div>

            {/* Whole Regenerate Button */}
            <button
              type="button"
              onClick={handleRegenerateWhole}
              disabled={isRegenerating}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#FFF0ED] text-[#822828] border border-[#F8AD9D] hover:bg-[#FEEBE3] text-xs font-bold rounded-lg transition-all shadow-peach-xs disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRegenerating ? 'animate-spin' : ''}`} />
              <span>{isRegenerating ? 'Regenerating...' : 'Regenerate'}</span>
            </button>

            {/* Download Brief Button */}
            <button
              type="button"
              onClick={handleDownloadBrief}
              disabled={isDownloadingBrief}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-gradient-to-r from-[#F08080] to-[#F4978E] hover:from-[#E07070] hover:to-[#F08080] text-white text-xs font-bold rounded-lg transition-all disabled:opacity-50 shadow-peach-xs cursor-pointer"
              title="Download 1-page PDF pre-consult brief"
            >
              {isDownloadingBrief ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5 text-white" />
              )}
              <span>{isDownloadingBrief ? 'Exporting...' : 'Download brief'}</span>
            </button>
          </div>
        </div>

        {/* Stale Data Warning Banner */}
        {isStale && (
          <div className="rounded-xl bg-amber-50 border border-amber-300 p-4 text-amber-900 text-xs flex items-center justify-between gap-3 shadow-2xs">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <div>
                <strong className="font-bold block">Clinical Records Updated Since Generation</strong>
                <span>New records or investigations have been logged. This cached summary may be stale.</span>
              </div>
            </div>
            <button
              onClick={handleRegenerateWhole}
              className="px-3 py-1 bg-white border border-amber-300 text-amber-900 font-bold rounded-lg hover:bg-amber-100 flex-shrink-0"
            >
              Update Now
            </button>
          </div>
        )}

        {/* 1. Prominent Conflicts Panel */}
        <ConflictsPanel
          conflicts={conflictsList}
          onSelectCitation={(cit) => setSelectedCitation(cit)}
        />

        {/* 2. Snapshot View (5 lines) */}
        {viewMode === 'snapshot' && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#F08080]" />
                <span>Executive Snapshot (&le; 5 lines)</span>
              </h3>
              <span className="text-xs text-slate-500 font-mono">Clinician Quick-Brief</span>
            </div>

            <div className="space-y-2 text-xs text-slate-700 leading-relaxed font-sans">
              {snapshotItems.length > 0 ? (
                snapshotItems.map((item: any, idx: number) => {
                  const text = typeof item === 'string' ? item : item.text;
                  const sourceRefs: string[] = typeof item === 'object' && Array.isArray(item.source_refs) ? item.source_refs : [];
                  const assuranceTier: string | undefined = typeof item === 'object' ? item.assurance_tier : undefined;

                  return (
                    <div key={idx} className="flex items-start gap-2.5 p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                      <span className="w-5 h-5 rounded-full bg-[#FFF0ED] text-[#A83232] font-bold text-[11px] flex items-center justify-center flex-shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      <div className="flex-1 space-y-1.5">
                        <span className="font-medium text-slate-900 block">{text}</span>
                        {(sourceRefs.length > 0 || assuranceTier) && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {assuranceTier && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-50 text-emerald-800 border border-emerald-200">
                                {assuranceTier}
                              </span>
                            )}
                            {sourceRefs.map((srcId) => (
                              <button
                                key={srcId}
                                onClick={() => setSelectedCitation({ source_id: srcId, type: 'record', matching_text: text })}
                                className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white text-[#A83232] border border-[#F08080]/40 hover:bg-[#FFF0ED] transition-colors cursor-pointer"
                                title={`Inspect source document ${srcId}`}
                              >
                                [{srcId}]
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="text-slate-500 italic">No snapshot generated.</div>
              )}
            </div>
          </div>
        )}

        {/* 3. Detailed Sections in Spec Order */}
        {viewMode === 'detailed' && (
          <div className="space-y-4">
            {orderedSectionKeys.map((secKey) => {
              const sec: SummarySection = sectionsMap[secKey];
              if (!sec) return null;

              const isFallback = sec.mode === 'deterministic_fallback';
              const isSectionRegen = regeneratingSection === secKey;
              const title = SECTION_TITLES[secKey] || sec.section_title || secKey.replace(/_/g, ' ');

              return (
                <div
                  key={secKey}
                  className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden"
                >
                  {/* Section Header */}
                  <div className="p-4 sm:px-5 bg-slate-50/70 border-b border-slate-200 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-slate-900">
                        {title}
                      </h3>
                      {isFallback ? (
                        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-300">
                          Deterministic Fallback
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-300">
                          LLM-Grounded
                        </span>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => handleRegenerateSection(secKey)}
                      disabled={isSectionRegen}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 hover:text-slate-900 p-1.5 rounded hover:bg-slate-200 transition-colors disabled:opacity-50"
                      title="Regenerate this section only"
                    >
                      <RefreshCw className={`w-3 h-3 ${isSectionRegen ? 'animate-spin' : ''}`} />
                      <span>{isSectionRegen ? 'Regenerating...' : 'Regenerate'}</span>
                    </button>
                  </div>

                  {/* Fallback Mode Banner */}
                  {isFallback && (
                    <div className="p-3 bg-amber-50/70 border-b border-amber-200 text-xs text-amber-900 flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                      <span>
                        AI summary unavailable for this section; showing record-based view.
                      </span>
                    </div>
                  )}

                  {/* Section Statements & Claims */}
                  <div className="p-4 sm:p-5 space-y-4">
                    {/* Natural narrative text */}
                    {sec.text && (
                      <div className="text-xs text-slate-700 leading-relaxed font-sans bg-slate-50/40 p-3 rounded-lg border border-slate-100">
                        {sec.text}
                      </div>
                    )}

                    {/* Statements / Claims list */}
                    {(() => {
                      const statementsList: any[] = sec.statements || sec.claims || [];
                      if (statementsList.length === 0) return null;

                      return (
                        <div className="space-y-3 pt-2">
                          {statementsList.map((claim: any, cIdx: number) => {
                            const stId = claim.statement_id || claim.claim_id || `stmt-${cIdx}`;
                            const stText = claim.text || claim.display_text || '';
                            const citations: Citation[] = claim.citations || [];

                            return (
                              <div
                                key={stId}
                                className="p-3.5 rounded-xl border border-slate-200 hover:border-[#FBC4AB] bg-[#FFFEFD] shadow-2xs space-y-2 transition-all"
                              >
                                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                                  {/* Left statement text */}
                                  <div className="text-xs text-slate-900 font-medium flex-1">
                                    {stText}
                                  </div>

                                  {/* Assurance badge & feedback button */}
                                  <div className="flex items-center gap-2 self-start sm:self-center flex-shrink-0">
                                    {getAssuranceBadge(claim)}

                                    <button
                                      type="button"
                                      onClick={() =>
                                        setFeedbackStatement({
                                          ref: stId,
                                          text: stText,
                                        })
                                      }
                                      className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-[#A83232] hover:bg-[#FFF0ED] px-2 py-0.5 rounded transition-colors cursor-pointer"
                                      title="Report incorrect fact or discrepancy"
                                    >
                                      <MessageSquare className="w-3 h-3" />
                                      <span>Feedback</span>
                                    </button>
                                  </div>
                                </div>

                                {/* Citation Chips */}
                                {citations.length > 0 && (
                                  <div className="pt-2 border-t border-slate-100 flex items-center gap-1.5 flex-wrap">
                                    <span className="text-[10px] text-slate-600 uppercase font-semibold">
                                      Sources:
                                    </span>
                                    {citations.map((c, citIdx) => {
                                      const isExt = c.trust === 'external_unverified';
                                      return (
                                        <button
                                          key={citIdx}
                                          type="button"
                                          onClick={() =>
                                            setSelectedCitation({
                                              ...c,
                                              field_path: claim.field_path,
                                              matching_text: stText,
                                            })
                                          }
                                          className={`font-mono text-[11px] px-2.5 py-1 rounded-md border shadow-2xs transition-all flex items-center gap-1.5 cursor-pointer ${
                                            isExt
                                              ? 'bg-amber-50/90 hover:bg-amber-100 text-amber-900 border-amber-300 hover:border-amber-400'
                                              : 'bg-white hover:bg-[#FFF5F2] text-slate-800 hover:text-[#A83232] border-slate-300 hover:border-[#F8AD9D]'
                                          }`}
                                        >
                                          <FileCheck className={`w-3 h-3 ${isExt ? 'text-amber-600' : 'text-[#F08080]'}`} />
                                          <span>[{formatCitationChip(c)}]</span>
                                        </button>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      );
                    })()}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 4. Prominent "Not Documented" Panel */}
        <MissingDataPanel
          missingItems={notDocumentedList}
        />
      </div>

      {/* Right Column: Split-Pane Source Viewer */}
      {selectedCitation && (
        <div className="w-full lg:w-96 xl:w-[480px] flex-shrink-0 sticky top-20">
          <SourceViewer
            citation={selectedCitation}
            onClose={() => setSelectedCitation(null)}
          />
        </div>
      )}

      {/* Feedback Modal Dialog */}
      {feedbackStatement && summary && (
        <StatementFeedbackModal
          summaryId={summaryId}
          statementRef={feedbackStatement.ref}
          statementText={feedbackStatement.text}
          onClose={() => setFeedbackStatement(null)}
        />
      )}
    </div>
  );
};
