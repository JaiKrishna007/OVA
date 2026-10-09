import React from 'react';
import type { TimelineResponse, TimelineEvent, Citation } from '../types/api';
import {
  Calendar,
  Building2,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Clock,
} from 'lucide-react';

interface LongitudinalTimelineProps {
  timeline: TimelineResponse;
  onSelectCitation: (citation: Citation) => void;
  onSelectCycle: (cycleId: string) => void;
}

const STAGE_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  Stimulation: { bg: 'bg-[#FFF0ED]', text: 'text-[#A83232]', border: 'border-[#F8AD9D]' },
  Monitoring: { bg: 'bg-sky-50', text: 'text-sky-800', border: 'border-sky-200' },
  OPU: { bg: 'bg-amber-50', text: 'text-amber-800', border: 'border-amber-200' },
  Trigger: { bg: 'bg-orange-50', text: 'text-orange-800', border: 'border-orange-200' },
  Embryology: { bg: 'bg-purple-50', text: 'text-purple-800', border: 'border-purple-200' },
  Transfer: { bg: 'bg-emerald-50', text: 'text-emerald-800', border: 'border-emerald-200' },
  Outcome: { bg: 'bg-rose-50', text: 'text-rose-800', border: 'border-rose-200' },
};

export const LongitudinalTimeline: React.FC<LongitudinalTimelineProps> = ({
  timeline,
  onSelectCitation,
  onSelectCycle,
}) => {
  // Normalize events grouped by year
  const yearsData = React.useMemo(() => {
    if (timeline.years && timeline.years.length > 0) {
      return timeline.years;
    }

    // Fallback if years payload is empty: aggregate from cycles
    const grouped: Record<number, TimelineEvent[]> = {};
    (timeline.cycles || []).forEach((c) => {
      (c.events || []).forEach((ev) => {
        const yr = ev.date ? parseInt(ev.date.substring(0, 4), 10) : 2024;
        if (!grouped[yr]) grouped[yr] = [];
        grouped[yr].push(ev);
      });
    });

    return Object.keys(grouped)
      .map(Number)
      .sort((a, b) => a - b)
      .map((yr) => ({
        year: yr,
        events_count: grouped[yr].length,
        cycles: timeline.cycles || [],
        events: grouped[yr].sort((a, b) => a.date.localeCompare(b.date)),
      }));
  }, [timeline]);

  const handleCitationClick = (ev: TimelineEvent) => {
    const srcId = ev.source_record_id || (ev.source_refs && ev.source_refs[0]) || '';
    if (srcId) {
      onSelectCitation({
        source_id: srcId,
        type: ev.kind || 'clinical_event',
        date: ev.date || null,
        origin: ev.hospital || ev.origin_org || 'Origin Hospital',
        trust: 'internal_verified',
      });
    }
  };

  return (
    <div className="space-y-8">
      {/* 1. Ambiguous / Unlinked Events Requiring Doctor Review */}
      {timeline.unlinked_events && timeline.unlinked_events.length > 0 && (
        <div className="bg-amber-50/70 border border-amber-300 rounded-xl p-5 shadow-2xs space-y-3">
          <div className="flex items-center gap-2 text-amber-900 font-bold text-sm">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Unassigned Clinical Events (Marked cycle_assignment=NEEDS_REVIEW)</span>
            <span className="text-xs bg-amber-200/80 text-amber-900 font-mono px-2 py-0.5 rounded-full ml-auto">
              {timeline.unlinked_events.length} unassigned
            </span>
          </div>
          <p className="text-xs text-amber-800 leading-relaxed">
            Per clinical safety rule, events with ambiguous cycle attribution, differing hospital origins,
            or out-of-order sequence are flagged for explicit clinician review rather than guessed silently.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
            {timeline.unlinked_events.map((ev) => (
              <div
                key={ev.id}
                className="bg-white p-3.5 rounded-lg border border-amber-200 shadow-2xs space-y-2 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-slate-500 font-semibold">{ev.date || 'Undated'}</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                    NEEDS_REVIEW
                  </span>
                </div>
                <div className="font-bold text-slate-900">{ev.canonical_event_name || ev.kind}</div>
                {ev.detail && <div className="text-slate-600 line-clamp-2">{ev.detail}</div>}
                <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-[11px]">
                  <span className="text-slate-500 flex items-center gap-1 truncate max-w-[160px]">
                    <Building2 className="w-3 h-3 text-slate-400 shrink-0" />
                    <span className="truncate">{ev.hospital || 'Hospital'}</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => handleCitationClick(ev)}
                    className="font-mono text-[#A83232] hover:underline flex items-center gap-1 font-semibold"
                  >
                    <FileText className="w-3 h-3 text-[#F08080]" />
                    <span>[{ev.source_record_id || 'REC'}]</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 2. Longitudinal Vertical Timeline by Year */}
      <div className="space-y-10">
        {yearsData.map((yearGroup) => (
          <div key={yearGroup.year} className="space-y-4">
            {/* Year Header Marker */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-gradient-to-r from-[#FFF9F7] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] font-extrabold text-sm shadow-peach-xs">
                <Calendar className="w-4 h-4 text-[#F08080]" />
                <span>{yearGroup.year}</span>
              </div>
              <div className="h-px bg-[#FBC4AB]/40 flex-1" />
              <span className="text-xs text-slate-500 font-mono">
                {yearGroup.events.length} documented events
              </span>
            </div>

            {/* Vertical Timeline Track */}
            <div className="relative border-l-2 border-[#F8AD9D]/60 ml-4 md:ml-6 pl-6 space-y-4 py-1">
              {yearGroup.events.map((ev) => {
                const stageStyle = STAGE_STYLES[ev.stage] || {
                  bg: 'bg-slate-100',
                  text: 'text-slate-700',
                  border: 'border-slate-200',
                };
                const isVerified = ev.validation_status === 'VERIFIED';

                return (
                  <div key={ev.id} className="relative group">
                    {/* Timeline Node Dot */}
                    <div className="absolute -left-[31px] top-3.5 w-3.5 h-3.5 rounded-full bg-white border-[3px] border-[#F08080] group-hover:scale-125 transition-transform shadow-peach-xs" />

                    {/* Event Card */}
                    <div className="bg-white rounded-2xl border border-slate-200/90 hover:border-[#F8AD9D] p-4.5 shadow-2xs hover:shadow-peach-xs card-interactive transition-all space-y-2.5">
                      {/* Top Header Row */}
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <span className="font-mono text-xs font-bold text-[#822828] bg-[#FFF9F7] border border-[#FBC4AB]/50 px-2 py-0.5 rounded-md">
                            {ev.date || 'Undated'}
                          </span>
                          <h4 className="text-sm font-bold text-slate-900">
                            {ev.canonical_event_name || ev.kind}
                          </h4>
                        </div>

                        <div className="flex items-center gap-2">
                          {/* Stage Chip */}
                          <span
                            className={`px-2 py-0.5 rounded-md text-[11px] font-semibold border ${stageStyle.bg} ${stageStyle.text} ${stageStyle.border}`}
                          >
                            {ev.stage}
                          </span>

                          {/* Validation Status Chip */}
                          <span
                            className={`px-2 py-0.5 rounded-md text-[11px] font-semibold flex items-center gap-1 border ${
                              isVerified
                                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                : 'bg-amber-50 text-amber-800 border-amber-200'
                            }`}
                          >
                            {isVerified ? (
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            ) : (
                              <AlertTriangle className="w-3 h-3 text-amber-600" />
                            )}
                            <span>{ev.validation_status}</span>
                          </span>
                        </div>
                      </div>

                      {/* Detail Body */}
                      {ev.detail && (
                        <p className="text-xs text-slate-700 leading-relaxed font-sans">
                          {ev.detail}
                        </p>
                      )}

                      {/* Bottom Provenance Footer */}
                      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100 text-xs">
                        <div className="flex items-center gap-2">
                          {/* Hospital Badge */}
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 text-[11px]">
                            <Building2 className="w-3 h-3 text-slate-400 shrink-0" />
                            <span className="font-medium truncate max-w-[220px]">
                              {ev.hospital || ev.origin_org || 'Kernel Prime Fertility Hospital'}
                            </span>
                          </span>

                          {/* Cycle Pill */}
                          {ev.cycle_no ? (
                            <button
                              type="button"
                              onClick={() => ev.cycle_id && onSelectCycle(ev.cycle_id)}
                              className="px-2 py-0.5 rounded bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D] text-[11px] font-semibold hover:bg-[#FEEBE3] transition-colors"
                            >
                              Cycle {ev.cycle_no}
                            </button>
                          ) : null}
                        </div>

                        {/* Source Record & Citation Drawer Trigger */}
                        <div className="flex items-center gap-2">
                          {ev.source_record_id && (
                            <button
                              type="button"
                              onClick={() => handleCitationClick(ev)}
                              className="inline-flex items-center gap-1 font-mono text-[11px] text-[#A83232] bg-[#FFF0ED] hover:bg-[#FEEBE3] px-2 py-0.5 rounded border border-[#F8AD9D] font-semibold transition-colors"
                              title="Click to view raw evidence document"
                            >
                              <FileText className="w-3 h-3 text-[#F08080]" />
                              <span>[{ev.source_record_id}]</span>
                            </button>
                          )}
                          <span className="text-[11px] text-slate-400 font-mono hidden sm:inline">
                            {ev.citation}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {yearsData.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500 space-y-2">
            <Clock className="w-8 h-8 text-slate-400 mx-auto" />
            <p className="font-semibold text-slate-700">No longitudinal timeline events recorded yet.</p>
            <p className="text-xs text-slate-500">Upload a clinical record to materialize timeline events.</p>
          </div>
        )}
      </div>
    </div>
  );
};
