import React, { useState, useEffect, useRef } from 'react';
import { recordsApi, ApiClientError } from '../services/api';
import type { SourceRecordDetailResponse, Citation } from '../types/api';
import {
  X,
  ShieldCheck,
  ShieldAlert,
  Loader2,
  AlertTriangle,
  Highlighter,
} from 'lucide-react';

interface SourceViewerProps {
  citation: Citation | null;
  onClose: () => void;
}

export const SourceViewer: React.FC<SourceViewerProps> = ({ citation, onClose }) => {
  const [record, setRecord] = useState<SourceRecordDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const highlightRef = useRef<HTMLSpanElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!citation?.source_id) {
      setRecord(null);
      return;
    }

    const loadRecord = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await recordsApi.getById(citation.source_id);
        setRecord(data);
      } catch (err: unknown) {
        if (err instanceof ApiClientError) {
          setError(err.message || `Unable to load source record ${citation.source_id}`);
        } else {
          setError('Network error while retrieving source record.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadRecord();
  }, [citation?.source_id]);

  // Automatically scroll highlighted text into view
  useEffect(() => {
    if (highlightRef.current && containerRef.current) {
      const timer = setTimeout(() => {
        highlightRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [record, citation]);

  if (!citation) return null;

  // Render record text with character span highlighted
  const renderHighlightedContent = () => {
    if (!record?.content_text) return null;

    const text = record.content_text;
    const span = citation.span;

    if (span && typeof span.start === 'number' && typeof span.end === 'number' && span.end > span.start) {
      const start = Math.max(0, Math.min(span.start, text.length));
      const end = Math.max(0, Math.min(span.end, text.length));

      const before = text.slice(0, start);
      const highlighted = text.slice(start, end);
      const after = text.slice(end);

      return (
        <pre className="font-mono text-xs text-slate-800 whitespace-pre-wrap leading-relaxed select-text">
          {before}
          <mark
            ref={highlightRef}
            className="bg-[#FFE5B4] text-[#782C2C] px-1 py-0.5 rounded font-bold border border-[#F8AD9D] ring-2 ring-[#F08080]/40 shadow-xs"
          >
            {highlighted}
          </mark>
          {after}
        </pre>
      );
    }

    // Structured-field claims highlight the matching field line
    const searchTerms: string[] = [];
    if (citation.field_path) {
      const col = citation.field_path.split('.').pop();
      if (col) {
        searchTerms.push(col.replace(/_/g, ' ').toLowerCase());
        searchTerms.push(col.toLowerCase());
      }
    }
    if (citation.matching_text) {
      const clean = citation.matching_text.trim().toLowerCase();
      if (clean) searchTerms.push(clean);
    }

    if (searchTerms.length > 0) {
      const lines = text.split('\n');
      let matchIdx = -1;
      for (let i = 0; i < lines.length; i++) {
        const lineLower = lines[i].toLowerCase();
        if (searchTerms.some((term) => term.length > 1 && lineLower.includes(term))) {
          matchIdx = i;
          break;
        }
      }

      if (matchIdx !== -1) {
        return (
          <div className="font-mono text-xs text-slate-800 whitespace-pre-wrap leading-relaxed select-text">
            {lines.map((line, idx) =>
              idx === matchIdx ? (
                <mark
                  key={idx}
                  ref={highlightRef}
                  className="block bg-[#FFE5B4] text-[#782C2C] px-1.5 py-0.5 rounded font-bold border border-[#F8AD9D] ring-2 ring-[#F08080]/40 shadow-xs my-0.5"
                >
                  {line}
                </mark>
              ) : (
                <div key={idx}>{line}</div>
              )
            )}
          </div>
        );
      }
    }

    // Default plain text rendering
    return (
      <pre className="font-mono text-xs text-slate-800 whitespace-pre-wrap leading-relaxed select-text">
        {text}
      </pre>
    );
  };

  const isExternal =
    record?.trust_status === 'external_unverified' ||
    record?.origin_org?.toLowerCase().includes('hospital x') ||
    citation.trust === 'external_unverified';

  return (
    <aside aria-label="Source Document Viewer" className="h-full flex flex-col bg-white/95 backdrop-blur-md border border-[#FBC4AB]/50 rounded-3xl shadow-peach-xl w-full max-w-lg lg:max-w-xl transition-all overflow-hidden">
      {/* Top Header */}
      <div className="p-4 sm:p-5 bg-gradient-to-r from-[#FFF9F7] to-[#FFF5F2] border-b border-[#FBC4AB]/30 flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-lg bg-[#FFF0ED] text-[#822828] border border-[#F8AD9D]/60 shadow-peach-xs">
              {citation.source_id}
            </span>
            <span className="text-xs font-semibold uppercase px-2 py-0.5 rounded-md bg-white text-slate-700 border border-slate-200">
              {record?.type || citation.type || 'Clinical Document'}
            </span>
            <span
              className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full ${
                isExternal
                  ? 'bg-amber-100 text-amber-900 border border-amber-300'
                  : 'bg-emerald-50 text-emerald-800 border border-emerald-300'
              }`}
            >
              {isExternal ? (
                <>
                  <ShieldAlert className="w-3 h-3 text-amber-600" />
                  <span>External Unverified</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-3 h-3 text-emerald-600" />
                  <span>Internal Verified</span>
                </>
              )}
            </span>
          </div>

          <h3 className="text-sm font-extrabold text-slate-900 tracking-tight">
            Source Document Viewer
          </h3>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-xl text-slate-400 hover:text-[#822828] hover:bg-[#FFF0ED] btn-interactive transition-colors"
          title="Close source viewer"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Metadata Strip */}
      {record && (
        <div className="bg-[#FFFDFB] px-4 py-2.5 border-b border-slate-100 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
          <div>
            <span className="text-slate-500 block font-medium">Document Date</span>
            <span className="font-mono font-semibold text-slate-800">{record.date}</span>
          </div>
          <div>
            <span className="text-slate-500 block font-medium">Author</span>
            <span className="font-semibold text-slate-800 truncate block">
              {record.author || 'Clinical Staff'}
            </span>
          </div>
          <div>
            <span className="text-slate-500 block font-medium">Facility</span>
            <span className="font-semibold text-slate-800 truncate block" title={record.origin_org}>
              {record.origin_org}
            </span>
          </div>
          <div>
            <span className="text-slate-500 block font-medium">Version</span>
            <span className="font-mono font-semibold text-slate-800">v{record.version}</span>
          </div>
        </div>
      )}

      {/* Citation Span Info Banner */}
      <div className="bg-[#FFF9F7] px-4 py-2 border-b border-[#FBC4AB]/40 flex items-center justify-between text-xs text-[#822828]">
        <div className="flex items-center gap-2">
          <Highlighter className="w-3.5 h-3.5 text-[#F08080]" />
          <span>
            Highlighted span: <strong>{citation.span ? `Chars ${citation.span.start} - ${citation.span.end}` : 'Structured Reference'}</strong>
          </span>
        </div>
        <span className="text-[10px] text-slate-500 font-mono">Immutable EMR Record</span>
      </div>

      {/* Document Content Viewport */}
      <div ref={containerRef} className="flex-1 overflow-y-auto p-4 sm:p-5 bg-white">
        {isLoading && (
          <div className="py-20 text-center">
            <Loader2 className="w-6 h-6 text-[#F08080] animate-spin mx-auto mb-2" />
            <p className="text-xs font-semibold text-slate-600">
              Retrieving immutable source document...
            </p>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-rose-500 flex-shrink-0 mt-0.5" />
            <div>
              <strong className="block font-semibold">Unable to Load Record</strong>
              <span>{error}</span>
            </div>
          </div>
        )}

        {!isLoading && !error && record && (
          <div className="bg-slate-50/60 p-4 rounded-xl border border-slate-200">
            {renderHighlightedContent()}
          </div>
        )}
      </div>
    </aside>
  );
};
