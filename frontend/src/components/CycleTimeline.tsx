import React from 'react';
import type { TimelineCycleItem, TreatmentEvent } from '../types/api';
import { CycleBadge } from './CycleBadge';
import {
  Calendar,
  Building2,
  Syringe,
  Microscope,
  Baby,
  FileCheck,
  ChevronRight,
} from 'lucide-react';

interface CycleTimelineProps {
  cycles: TimelineCycleItem[];
  selectedCycleId: string | null;
  onSelectCycle: (cycleId: string) => void;
}

export const CycleTimeline: React.FC<CycleTimelineProps> = ({
  cycles,
  selectedCycleId,
  onSelectCycle,
}) => {
  if (!cycles || cycles.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500">
        No treatment cycles recorded for this patient.
      </div>
    );
  }

  const isExternalCycle = (cycle: TimelineCycleItem): boolean => {
    return (
      cycle.trust_status === 'external_unverified' ||
      cycle.origin_org.toLowerCase().includes('hospital x') ||
      cycle.origin_org !== 'ORG-Y'
    );
  };

  const isInProgressCycle = (cycle: TimelineCycleItem): boolean => {
    return !cycle.end_date || !cycle.outcome || cycle.outcome_badge.toLowerCase().includes('in progress');
  };

  // Extract key milestone event markers for a cycle
  const getCycleMilestoneMarkers = (events: TreatmentEvent[] = [], cycleType: string) => {
    const markers: Array<{
      key: string;
      label: string;
      date?: string | null;
      icon: React.ElementType;
      color: string;
    }> = [];

    events.forEach((ev) => {
      const k = (ev.kind || '').toLowerCase();
      const d = (ev.notes || '').toLowerCase();

      if (k.includes('trigger') || d.includes('trigger') || d.includes('hcg trigger') || d.includes('lupride')) {
        if (!markers.some((m) => m.key === 'trigger')) {
          markers.push({
            key: 'trigger',
            label: 'Trigger',
            date: ev.date,
            icon: Syringe,
            color: 'text-amber-600 bg-amber-50 border-amber-200',
          });
        }
      } else if (k === 'opu' || k.includes('retrieval') || d.includes('oocyte') || d.includes('opu')) {
        if (!markers.some((m) => m.key === 'opu')) {
          markers.push({
            key: 'opu',
            label: 'OPU',
            date: ev.date,
            icon: Microscope,
            color: 'text-purple-600 bg-purple-50 border-purple-200',
          });
        }
      } else if (k === 'transfer' || d.includes('transfer') || d.includes('et') || d.includes('insemination')) {
        if (!markers.some((m) => m.key === 'transfer')) {
          markers.push({
            key: 'transfer',
            label: cycleType.toUpperCase() === 'IUI' ? 'Insemination' : 'Transfer',
            date: ev.date,
            icon: Baby,
            color: 'text-indigo-600 bg-indigo-50 border-indigo-200',
          });
        }
      } else if (k.includes('outcome') || k.includes('beta') || d.includes('beta') || d.includes('hcg')) {
        if (!markers.some((m) => m.key === 'beta')) {
          markers.push({
            key: 'beta',
            label: 'Beta-hCG',
            date: ev.date,
            icon: FileCheck,
            color: 'text-rose-600 bg-rose-50 border-rose-200',
          });
        }
      }
    });

    return markers;
  };

  return (
    <div className="bg-white/95 backdrop-blur-md rounded-3xl border border-[#FBC4AB]/50 p-5 sm:p-6 shadow-peach-xs space-y-4">
      {/* Timeline Section Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#FBC4AB]/25">
        <div>
          <h2 className="text-base font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
            <span>Treatment Cycles Timeline</span>
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-[#FFF9F7] text-[#822828] border border-[#F8AD9D]/60 shadow-peach-xs">
              {cycles.length} Cycles
            </span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5 font-medium">
            Click any cycle block to open detailed protocol, medications, scan charts, and outcomes.
          </p>
        </div>
        <div className="text-[11px] text-slate-400 font-mono hidden sm:block">
          Chronological Order (Left → Right)
        </div>
      </div>

      {/* Horizontal Interactive Cycle Blocks */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {cycles.map((cycle) => {
          const isSelected = selectedCycleId === cycle.cycle_id;
          const isExternal = isExternalCycle(cycle);
          const inProgress = isInProgressCycle(cycle);
          const markers = getCycleMilestoneMarkers(cycle.events, cycle.type);

          return (
            <div
              key={cycle.cycle_id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectCycle(cycle.cycle_id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectCycle(cycle.cycle_id);
                }
              }}
              className={`rounded-2xl border p-4.5 transition-all card-interactive cursor-pointer relative text-left flex flex-col justify-between ${
                isSelected
                  ? 'border-[#F08080] bg-[#FFF8F6] ring-2 ring-[#F8AD9D] shadow-peach-xs'
                  : 'border-slate-200/90 bg-white hover:border-[#F8AD9D] hover:bg-[#FFF9F7] shadow-2xs'
              }`}
            >
              {/* Top Row: Cycle No, Type & Origin */}
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-900 text-sm">
                      Cycle {cycle.cycle_no}
                    </span>
                    <CycleBadge type={cycle.type} size="sm" />
                  </div>

                  {/* External Cycle Origin Badge */}
                  {isExternal ? (
                    <span
                      title="Cycle was performed at an outside facility (External Unverified)"
                      className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-300"
                    >
                      <Building2 className="w-3 h-3" />
                      <span>{cycle.origin_org} (External)</span>
                    </span>
                  ) : (
                    <span className="text-[11px] font-mono text-slate-400">
                      {cycle.origin_org}
                    </span>
                  )}
                </div>

                {/* Dates & Status */}
                <div className="text-xs text-slate-600 mb-3 flex items-center gap-1.5 font-medium">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>
                    {cycle.start_date || 'Start date unknown'} &rarr;{' '}
                    {inProgress ? (
                      <strong className="text-[#A83232] font-semibold">Active</strong>
                    ) : (
                      cycle.end_date || 'Ended'
                    )}
                  </span>
                </div>

                {/* Milestone Event Markers */}
                <div className="mb-3">
                  <div className="text-[11px] uppercase tracking-wider font-semibold text-slate-400 mb-1.5">
                    Milestones
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {markers.length > 0 ? (
                      markers.map((m) => {
                        const Icon = m.icon;
                        return (
                          <span
                            key={m.key}
                            title={`${m.label}: ${m.date || 'Recorded'}`}
                            className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md border font-medium ${m.color}`}
                          >
                            <Icon className="w-3 h-3" />
                            <span>{m.label}</span>
                          </span>
                        );
                      })
                    ) : (
                      <span className="text-xs text-slate-400 italic">
                        {inProgress ? 'Stimulation tracking active' : 'Summary milestones on file'}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Bottom Outcome & Drilldown CTA */}
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2 mt-2">
                {/* Outcome Badge */}
                {inProgress ? (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D]">
                    <span className="w-2 h-2 rounded-full bg-[#F08080] animate-pulse"></span>
                    <span>In Progress</span>
                  </span>
                ) : (
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${
                      cycle.outcome_badge.toLowerCase().includes('pregnant') ||
                      cycle.outcome_badge.toLowerCase().includes('pregnancy') ||
                      cycle.outcome_badge.toLowerCase().includes('live birth')
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                        : cycle.outcome_badge.toLowerCase().includes('loss') ||
                          cycle.outcome_badge.toLowerCase().includes('miscarriage') ||
                          cycle.outcome_badge.toLowerCase().includes('negative')
                        ? 'bg-rose-50 text-rose-800 border-rose-300'
                        : 'bg-slate-100 text-slate-800 border-slate-300'
                    }`}
                  >
                    <span>{cycle.outcome_badge}</span>
                  </span>
                )}

                <div className="inline-flex items-center gap-1 text-xs font-semibold text-[#A83232] group-hover:underline">
                  <span>Drill down</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
