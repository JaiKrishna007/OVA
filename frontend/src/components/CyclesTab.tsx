import React, { useState } from 'react';
import type { TimelineResponse, TimelineEvent, Citation } from '../types/api';
import {
  RotateCcw,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileText,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react';

interface CyclesTabProps {
  timeline: TimelineResponse;
  onSelectCitation: (citation: Citation) => void;
  onSelectCycle: (cycleId: string) => void;
}

const ALL_STAGES = ['Stimulation', 'Monitoring', 'OPU', 'Embryology', 'Transfer', 'Outcome'];

const STAGE_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  Stimulation: { bg: 'bg-[#FFF0ED]', text: 'text-[#A83232]', border: 'border-[#F8AD9D]' },
  Monitoring: { bg: 'bg-sky-50', text: 'text-sky-800', border: 'border-sky-200' },
  OPU: { bg: 'bg-amber-50', text: 'text-amber-800', border: 'border-amber-200' },
  Embryology: { bg: 'bg-purple-50', text: 'text-purple-800', border: 'border-purple-200' },
  Transfer: { bg: 'bg-emerald-50', text: 'text-emerald-800', border: 'border-emerald-200' },
  Outcome: { bg: 'bg-rose-50', text: 'text-rose-800', border: 'border-rose-200' },
};

export const CyclesTab: React.FC<CyclesTabProps> = ({
  timeline,
  onSelectCitation,
  onSelectCycle,
}) => {
  // Default all cycles to expanded
  const [expandedCycles, setExpandedCycles] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    (timeline.cycles || []).forEach((c) => {
      init[c.cycle_id] = true;
    });
    return init;
  });

  const toggleCycle = (cycleId: string) => {
    setExpandedCycles((prev) => ({
      ...prev,
      [cycleId]: !prev[cycleId],
    }));
  };

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

  const cycles = timeline.cycles || [];

  if (cycles.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500 space-y-2">
        <RotateCcw className="w-8 h-8 text-slate-400 mx-auto" />
        <p className="font-semibold text-slate-700">No treatment cycles recorded yet.</p>
        <p className="text-xs text-slate-500">Upload cycle summaries or stimulation records to materialize cycles.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Cycles Header Card */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white/95 backdrop-blur-md p-5 rounded-3xl border border-[#FBC4AB]/50 shadow-peach-xs">
        <div>
          <h3 className="text-base font-extrabold text-slate-900 flex items-center gap-2 tracking-tight">
            <RotateCcw className="w-4 h-4 text-[#F08080]" />
            <span>Treatment Cycles Accordion Ledger</span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5 font-medium">
            Sequential progression across documented stages (Stimulation → Monitoring → OPU → Embryology → Transfer → Outcome).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-bold px-3 py-1 rounded-full bg-[#FFF9F7] text-[#822828] border border-[#F8AD9D] shadow-peach-xs">
            {cycles.length} {cycles.length === 1 ? 'Cycle' : 'Cycles'} Tracked
          </span>
        </div>
      </div>

      {/* Accordions per cycle */}
      <div className="space-y-4">
        {cycles.map((cycle) => {
          const isExpanded = !!expandedCycles[cycle.cycle_id];
          const cycleEvents = cycle.events || [];

          // Compute documented stages
          const documentedStages = new Set<string>();
          if (cycle.stages && Array.isArray(cycle.stages)) {
            cycle.stages.forEach((s) => documentedStages.add(s));
          }
          cycleEvents.forEach((ev) => {
            if (ev.stage) documentedStages.add(ev.stage);
          });

          return (
            <div
              key={cycle.cycle_id}
              className="bg-white rounded-2xl border border-[#FBC4AB]/40 overflow-hidden shadow-peach-xs transition-all"
            >
              {/* Accordion Header */}
              <div
                onClick={() => toggleCycle(cycle.cycle_id)}
                className="p-4 sm:p-5 cursor-pointer hover:bg-[#FFF9F7]/60 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4 select-none border-b border-[#FBC4AB]/25"
              >
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded-lg bg-slate-900 text-white shadow-2xs">
                      Cycle {cycle.cycle_no}
                    </span>
                    <span className="text-sm font-bold text-slate-900">
                      {cycle.type} Protocol
                    </span>

                    {/* Outcome Badge */}
                    <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-[#FFF0ED] text-[#822828] border border-[#F8AD9D] shadow-peach-xs">
                      {cycle.outcome_badge}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                    <span className="flex items-center gap-1 font-mono">
                      <Calendar className="w-3.5 h-3.5 text-[#F08080]" />
                      <span>{cycle.start_date || 'Start undated'}</span>
                      <ArrowRight className="w-3 h-3 text-slate-400" />
                      <span>{cycle.end_date || 'In progress'}</span>
                    </span>

                    <span className="flex items-center gap-1">
                      <Building2 className="w-3.5 h-3.5 text-[#F08080]" />
                      <span className="font-semibold text-slate-700 truncate max-w-[240px]">
                        {cycle.hospital || cycle.origin_org}
                      </span>
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3 self-end md:self-center">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectCycle(cycle.cycle_id);
                    }}
                    className="px-3 py-1.5 text-xs font-bold text-[#822828] bg-gradient-to-r from-[#FFF9F7] to-[#FFEBE5] border border-[#F8AD9D] hover:bg-[#FEEBE3] rounded-xl transition-all shadow-peach-xs btn-interactive"
                  >
                    View Cycle Detail
                  </button>

                  <div className="w-7 h-7 rounded-full bg-[#FFF9F7] border border-[#FBC4AB]/50 flex items-center justify-center text-[#822828] shadow-peach-xs">
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </div>
                </div>
              </div>

              {/* Stage Progression Pills Bar */}
              <div className="px-4 py-3 bg-slate-50/60 border-b border-slate-100 flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mr-1">
                  Stages:
                </span>
                {ALL_STAGES.map((stg) => {
                  const isPresent = documentedStages.has(stg);
                  const style = STAGE_STYLES[stg] || { bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-200' };

                  return (
                    <span
                      key={stg}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${
                        isPresent
                          ? `${style.bg} ${style.text} border ${style.border} shadow-2xs`
                          : 'bg-white text-slate-400 border border-dashed border-slate-200'
                      }`}
                    >
                      {isPresent ? (
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                      ) : (
                        <span className="w-3.5 text-center text-[10px] leading-none">-</span>
                      )}
                      <span>{stg}</span>
                    </span>
                  );
                })}
              </div>

              {/* Accordion Body */}
              {isExpanded && (
                <div className="p-4 sm:p-5 space-y-3 bg-white">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <span className="text-xs font-bold text-slate-700">
                      Documented Events in Cycle {cycle.cycle_no}
                    </span>
                    <span className="text-xs text-slate-500 font-mono">
                      {cycleEvents.length} events
                    </span>
                  </div>

                  {cycleEvents.length === 0 ? (
                    <div className="py-4 text-center text-xs text-slate-400">
                      No discrete stage events logged for this cycle yet.
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {cycleEvents.map((ev) => {
                        const isVerified = ev.validation_status === 'VERIFIED';
                        const stageStyle = STAGE_STYLES[ev.stage] || {
                          bg: 'bg-slate-100',
                          text: 'text-slate-700',
                          border: 'border-slate-200',
                        };

                        return (
                          <div
                            key={ev.id}
                            className="p-3.5 bg-slate-50/50 hover:bg-[#FFFDFB] rounded-lg border border-slate-200 hover:border-[#F8AD9D] transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                          >
                            <div className="space-y-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-mono text-slate-500 font-semibold">
                                  {ev.date || 'Undated'}
                                </span>
                                <span className="font-bold text-slate-900">
                                  {ev.canonical_event_name || ev.kind}
                                </span>
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${stageStyle.bg} ${stageStyle.text} ${stageStyle.border}`}
                                >
                                  {ev.stage}
                                </span>
                              </div>
                              {ev.detail && (
                                <p className="text-slate-600 line-clamp-2">{ev.detail}</p>
                              )}
                            </div>

                            <div className="flex items-center gap-2 flex-shrink-0 self-start sm:self-center">
                              {/* Hospital Badge */}
                              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200 max-w-[140px] truncate">
                                <Building2 className="w-3 h-3 text-slate-400 shrink-0" />
                                <span className="truncate">{ev.hospital || cycle.hospital}</span>
                              </span>

                              {/* Source Chip */}
                              {ev.source_record_id && (
                                <button
                                  type="button"
                                  onClick={() => handleCitationClick(ev)}
                                  className="inline-flex items-center gap-1 font-mono text-[11px] px-2 py-0.5 rounded bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D] font-semibold hover:bg-[#FEEBE3] transition-colors"
                                  title="View evidence in document drawer"
                                >
                                  <FileText className="w-3 h-3 text-[#F08080]" />
                                  <span>[{ev.source_record_id}]</span>
                                </button>
                              )}

                              {/* Validation Status */}
                              <span
                                className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded font-semibold border ${
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
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
