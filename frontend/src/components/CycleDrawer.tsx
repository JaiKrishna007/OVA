import React, { useState, useEffect } from 'react';
import { patientsApi, ApiClientError } from '../services/api';
import type { CycleDetailResponse, StimulationResponse } from '../types/api';
import { CycleBadge } from './CycleBadge';
import {
  X,
  Calendar,
  Building2,
  Syringe,
  Microscope,
  Baby,
  Activity,
  AlertTriangle,
  Clock,
  Layers,
  Loader2,
} from 'lucide-react';

interface CycleDrawerProps {
  patientId: string;
  cycleId: string | null;
  onClose: () => void;
}

interface OpuInfo {
  oocytes_retrieved?: number;
  mii?: number;
  mi?: number;
  gv?: number;
}

interface EmbryoInfo {
  embryo_label?: string;
  day?: number;
  grade?: string;
  pgt_status?: string;
  fate?: string;
  storage_location?: string;
}

interface AdverseEventInfo {
  kind?: string;
  severity?: string;
  management_note?: string;
}

export const CycleDrawer: React.FC<CycleDrawerProps> = ({
  patientId,
  cycleId,
  onClose,
}) => {
  const [cycle, setCycle] = useState<CycleDetailResponse | null>(null);
  const [stimulation, setStimulation] = useState<StimulationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!cycleId || !patientId) {
      setCycle(null);
      setStimulation(null);
      return;
    }

    const loadCycleDetails = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await patientsApi.getCycleDetail(patientId, cycleId);
        setCycle(data);

        // Also fetch stimulation charts if applicable
        try {
          const stimData = await patientsApi.getStimulation(patientId, cycleId);
          setStimulation(stimData);
        } catch {
          // Non-stimulation cycle or optional
          setStimulation(null);
        }
      } catch (err: unknown) {
        if (err instanceof ApiClientError) {
          setError(err.message || `Failed to fetch cycle details for ${cycleId}`);
        } else {
          setError('Network error while retrieving cycle details.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadCycleDetails();
  }, [patientId, cycleId]);

  if (!cycleId) return null;

  const isExternal =
    cycle?.trust_status === 'external_unverified' ||
    cycle?.origin_org?.toLowerCase().includes('hospital x') ||
    (cycle && cycle.origin_org !== 'ORG-Y');

  const opu = cycle?.opu as OpuInfo | null | undefined;
  const embryos = (cycle?.embryos || []) as EmbryoInfo[];
  const adverseEvents = (cycle?.adverse_events || []) as AdverseEventInfo[];

  const stimDaysCount = String(
    stimulation?.summary?.total_days ??
    cycle?.stimulation_summary?.total_days ??
    'N/A'
  );

  const peakE2Val =
    stimulation?.summary?.peak_e2 ??
    cycle?.stimulation_summary?.peak_e2;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-2xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <aside aria-label="Cycle Details Drawer" className="w-screen max-w-2xl bg-white shadow-2xl flex flex-col border-l border-slate-200">
          {/* Drawer Header */}
          <div className="p-5 sm:p-6 bg-slate-50 border-b border-slate-200 flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-800">
                  {cycleId}
                </span>
                {cycle && <CycleBadge type={cycle.type} size="md" />}
                {cycle && isExternal && (
                  <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-300">
                    <Building2 className="w-3 h-3" />
                    <span>{cycle.origin_org} (External)</span>
                  </span>
                )}
                {cycle && !cycle.end_date && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D]">
                    <span className="w-2 h-2 rounded-full bg-[#F08080] animate-pulse"></span>
                    <span>In Progress</span>
                  </span>
                )}
              </div>

              <h2 className="text-lg font-bold text-slate-900 mt-2">
                {cycle ? `Cycle #${cycle.cycle_no} Details (${cycle.type})` : `Loading ${cycleId}...`}
              </h2>

              {cycle && (
                <div className="text-xs text-slate-500 mt-1 flex items-center gap-2">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>
                    {cycle.start_date || 'Start date unrecorded'} &rarr;{' '}
                    {cycle.end_date || 'Ongoing'}
                  </span>
                  <span>&bull;</span>
                  <span>Outcome: <strong>{cycle.outcome_badge}</strong></span>
                </div>
              )}
            </div>

            <button
              onClick={onClose}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
              title="Close drawer (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
            {isLoading && (
              <div className="py-20 text-center">
                <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
                <p className="text-sm font-medium text-slate-600">
                  Loading clinical data for {cycleId}...
                </p>
              </div>
            )}

            {error && (
              <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-rose-500 flex-shrink-0 mt-0.5" />
                <div>
                  <strong className="block font-semibold">Error Loading Cycle</strong>
                  <span>{error}</span>
                </div>
              </div>
            )}

            {!isLoading && !error && cycle && (
              <>
                {/* 1. Protocol & Summary */}
                <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <Layers className="w-4 h-4 text-[#F08080]" />
                      <span>Protocol & Stimulation Overview</span>
                    </h3>
                    <span className="text-xs text-slate-500 font-mono">
                      Trust: {cycle.trust_status}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                    <div className="bg-white p-3 rounded-lg border border-slate-200">
                      <span className="text-slate-600 block">Cycle Type</span>
                      <strong className="text-slate-800 font-bold text-sm">{cycle.type}</strong>
                    </div>

                    <div className="bg-white p-3 rounded-lg border border-slate-200">
                      <span className="text-slate-600 block">Facility Origin</span>
                      <strong className="text-slate-800 font-bold text-sm truncate block" title={cycle.origin_org}>
                        {cycle.origin_org}
                      </strong>
                    </div>

                    <div className="bg-white p-3 rounded-lg border border-slate-200">
                      <span className="text-slate-600 block">Stimulation Days</span>
                      <strong className="text-slate-800 font-bold text-sm">
                        {stimDaysCount}
                      </strong>
                    </div>

                    <div className="bg-white p-3 rounded-lg border border-slate-200">
                      <span className="text-slate-600 block">Peak Estradiol (E2)</span>
                      <strong className="text-slate-800 font-bold text-sm">
                        {peakE2Val ? `${String(peakE2Val)} pg/mL` : 'Not recorded'}
                      </strong>
                    </div>

                    <div className="bg-white p-3 rounded-lg border border-slate-200">
                      <span className="text-slate-600 block">Total Oocytes</span>
                      <strong className="text-slate-800 font-bold text-sm">
                        {opu?.oocytes_retrieved != null
                          ? String(opu.oocytes_retrieved)
                          : cycle.type === 'IUI'
                          ? 'N/A (IUI)'
                          : 'Pending'}
                      </strong>
                    </div>

                    <div className="bg-white p-3 rounded-lg border border-slate-200">
                      <span className="text-slate-600 block">Embryos Cultured</span>
                      <strong className="text-slate-800 font-bold text-sm">
                        {embryos.length}
                      </strong>
                    </div>
                  </div>
                </div>

                {/* 2. Stimulation Days & Scans */}
                {stimulation && stimulation.days && stimulation.days.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <Activity className="w-4 h-4 text-[#F08080]" />
                      <span>Follicular Scans & Monitoring</span>
                    </h3>
                    <div className="overflow-x-auto border border-slate-200 rounded-xl">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
                          <tr>
                            <th className="p-2.5">Day</th>
                            <th className="p-2.5">Date</th>
                            <th className="p-2.5">Endo (mm)</th>
                            <th className="p-2.5">E2 (pg/mL)</th>
                            <th className="p-2.5">LH (mIU/mL)</th>
                            <th className="p-2.5">Follicles (R / L)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {stimulation.days.map((d) => (
                            <tr key={d.day_number} className="hover:bg-slate-50">
                              <td className="p-2.5 font-bold font-mono">D{d.day_number}</td>
                              <td className="p-2.5 text-slate-600">{d.date}</td>
                              <td className="p-2.5 font-semibold">{d.endometrium_thickness_mm ?? '-'}</td>
                              <td className="p-2.5 text-slate-700">{d.estradiol_pg_ml ?? '-'}</td>
                              <td className="p-2.5 text-slate-700">{d.lh_miu_ml ?? '-'}</td>
                              <td className="p-2.5 text-slate-600 font-mono text-[11px]">
                                {Array.isArray(d.follicles_right) ? d.follicles_right.join(', ') : '-'} /{' '}
                                {Array.isArray(d.follicles_left) ? d.follicles_left.join(', ') : '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* 3. Medications */}
                {stimulation && stimulation.medications && stimulation.medications.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <Syringe className="w-4 h-4 text-[#F08080]" />
                      <span>Medications Administered</span>
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      {stimulation.medications.map((m, i) => (
                        <div key={i} className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                          <strong className="text-slate-800 font-semibold block">
                            {String(m.name || m.drug || 'Medication')}
                          </strong>
                          <span className="text-slate-600 text-[11px]">
                            {m.dose ? `Dose: ${String(m.dose)}` : ''}{' '}
                            {m.start_date ? `(${String(m.start_date)} → ${String(m.end_date || 'ongoing')})` : ''}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 4. OPU (Oocyte Retrieval) */}
                {opu && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <Microscope className="w-4 h-4 text-[#F08080]" />
                      <span>Oocyte Retrieval (OPU)</span>
                    </h3>
                    <div className="bg-[#FFFDFB] rounded-xl border border-[#F8AD9D] p-4">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                        <div className="p-2 bg-white rounded-lg border border-[#FBC4AB]">
                          <span className="text-slate-600 text-[11px] block">Retrieved</span>
                          <strong className="text-lg text-[#A83232] font-bold">
                            {String(opu.oocytes_retrieved ?? 0)}
                          </strong>
                        </div>
                        <div className="p-2 bg-white rounded-lg border border-[#FBC4AB]">
                          <span className="text-slate-600 text-[11px] block">Mature (MII)</span>
                          <strong className="text-lg text-emerald-700 font-bold">
                            {String(opu.mii ?? 0)}
                          </strong>
                        </div>
                        <div className="p-2 bg-white rounded-lg border border-[#FBC4AB]">
                          <span className="text-slate-600 text-[11px] block">Intermediate (MI)</span>
                          <strong className="text-lg text-amber-700 font-bold">
                            {String(opu.mi ?? 0)}
                          </strong>
                        </div>
                        <div className="p-2 bg-white rounded-lg border border-[#FBC4AB]">
                          <span className="text-slate-600 text-[11px] block">Germinal Vesicle</span>
                          <strong className="text-lg text-slate-700 font-bold">
                            {String(opu.gv ?? 0)}
                          </strong>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 5. Embryos Cultured */}
                {embryos.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <Baby className="w-4 h-4 text-[#F08080]" />
                      <span>Embryos Cultured ({embryos.length})</span>
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      {embryos.map((emb, idx) => (
                        <div key={idx} className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                          <div className="flex items-center justify-between mb-1">
                            <strong className="font-mono text-slate-800">
                              {emb.embryo_label || `Embryo #${idx + 1}`}
                            </strong>
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                emb.fate === 'frozen'
                                  ? 'bg-sky-50 text-sky-800 border border-sky-300'
                                  : emb.fate === 'transferred'
                                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-300'
                                  : 'bg-slate-100 text-slate-600'
                              }`}
                            >
                              {emb.fate || 'Cultured'}
                            </span>
                          </div>
                          <div className="text-slate-600 text-[11px]">
                            <span>Day: {String(emb.day ?? '-')}</span> &bull;{' '}
                            <span>Grade: {emb.grade || 'N/A'}</span>
                            {emb.pgt_status && <span> &bull; PGT: {emb.pgt_status}</span>}
                          </div>
                          {emb.storage_location && (
                            <div className="text-[10px] font-mono text-slate-600 mt-1">
                              Loc: {emb.storage_location}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 6. Adverse Events */}
                {adverseEvents.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-rose-700 flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-rose-500" />
                      <span>Adverse Events ({adverseEvents.length})</span>
                    </h3>
                    {adverseEvents.map((adv, idx) => (
                      <div key={idx} className="p-3.5 bg-rose-50 rounded-xl border border-rose-200 text-xs text-rose-900 space-y-1">
                        <div className="flex items-center justify-between font-bold">
                          <span>{adv.kind || 'Adverse Event'}</span>
                          <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-rose-200/60">
                            {adv.severity || 'Reported'}
                          </span>
                        </div>
                        <p className="text-slate-700">{adv.management_note || 'No management note recorded'}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* 7. Clinical Events Chronology */}
                {cycle.events && cycle.events.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <Clock className="w-4 h-4 text-[#F08080]" />
                      <span>Cycle Events Log</span>
                    </h3>
                    <div className="space-y-2">
                      {cycle.events.map((ev) => (
                        <div
                          key={ev.id}
                          className="p-3 bg-white rounded-lg border border-slate-200 text-xs flex items-start justify-between gap-3"
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-slate-400 text-[11px]">{ev.date}</span>
                              <span className="font-semibold text-slate-800 capitalize">{ev.kind}</span>
                            </div>
                            <p className="text-slate-600 mt-0.5">{ev.notes || 'No notes documented'}</p>
                          </div>
                          {ev.source_refs && ev.source_refs.length > 0 && (
                            <span className="font-mono text-[10px] text-slate-600 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200 flex-shrink-0">
                              {ev.source_refs[0]}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 8. Source Provenance */}
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 block mb-2">
                    Verified Source Provenance
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {cycle.source_refs.map((ref) => (
                      <span
                        key={ref}
                        className="font-mono text-xs px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-300"
                      >
                        {ref}
                      </span>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
};
