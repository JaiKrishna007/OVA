import React, { useState, useEffect } from 'react';
import { patientsApi, ApiClientError } from '../services/api';
import type { StimulationResponse, TimelineResponse, StimulationDayItem, Citation } from '../types/api';
import { SourceViewer } from './SourceViewer';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import {
  Activity,
  Calendar,
  Loader2,
  FileCheck,
  ChevronDown,
  Sparkles,
  Info,
} from 'lucide-react';

interface StimulationTabProps {
  patientId: string;
}

export const StimulationTab: React.FC<StimulationTabProps> = ({ patientId }) => {
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [selectedCycleId, setSelectedCycleId] = useState<string>('');
  const [stimData, setStimData] = useState<StimulationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  // 1. Initial load: fetch patient cycles
  useEffect(() => {
    const loadCycles = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const tl = await patientsApi.getTimeline(patientId);
        setTimeline(tl);
        if (tl.cycles && tl.cycles.length > 0) {
          // Select cycle with stim days if available, or latest cycle
          // For P-102, default to CY-P102-3 (the OHSS IVF cycle)
          const targetCycle =
            tl.cycles.find((c) => c.cycle_id.includes('P102-3')) ||
            tl.cycles.find((c) => c.type === 'IVF' || c.type === 'ICSI') ||
            tl.cycles[tl.cycles.length - 1];

          setSelectedCycleId(targetCycle.cycle_id);
        }
      } catch (err: unknown) {
        if (err instanceof ApiClientError) {
          setError(err.message || 'Unable to retrieve treatment cycles.');
        } else {
          setError('Network error while retrieving cycles.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadCycles();
  }, [patientId]);

  // 2. Load stimulation data whenever selectedCycleId changes
  useEffect(() => {
    if (!selectedCycleId) return;

    const loadStimulation = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await patientsApi.getStimulation(patientId, selectedCycleId);
        setStimData(res);
      } catch (err: unknown) {
        if (err instanceof ApiClientError) {
          setError(err.message || `No stimulation records found for cycle ${selectedCycleId}`);
        } else {
          setError('Network error loading stimulation chart.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadStimulation();
  }, [patientId, selectedCycleId]);

  if (isLoading && !stimData) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
        <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
        <h3 className="text-sm font-bold text-slate-800">Loading Follicular Monitoring Chart...</h3>
        <p className="text-xs text-slate-500 mt-1">Fetching hormone assays and follicle cohort progression.</p>
      </div>
    );
  }

  if (error && !stimData) {
    return (
      <div className="bg-white rounded-xl border border-rose-200 p-8 text-center shadow-2xs space-y-3">
        <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 mx-auto flex items-center justify-center">
          <Activity className="w-6 h-6" />
        </div>
        <h3 className="text-base font-bold text-slate-900">Stimulation Chart Unavailable</h3>
        <p className="text-xs text-rose-600 max-w-md mx-auto">{error}</p>
      </div>
    );
  }

  const days: StimulationDayItem[] = stimData?.days || [];
  const summary = stimData?.summary as any;
  const trigger = stimData?.trigger as any;

  // Transform data for Recharts
  const chartData = days.map((d) => {
    const dayLabel = `Day ${d.day_no ?? d.day_number ?? '?'}`;
    const e2Val = d.e2 ?? d.estradiol_pg_ml ?? null;
    const endoVal = d.endometrium_mm ?? d.endometrium_thickness_mm ?? null;

    let rightSizes: number[] = [];
    let leftSizes: number[] = [];

    if (d.follicles && typeof d.follicles === 'object') {
      if (Array.isArray(d.follicles.right)) rightSizes = d.follicles.right;
      if (Array.isArray(d.follicles.left)) leftSizes = d.follicles.left;
    }

    const allSizes = [...rightSizes, ...leftSizes];
    const totalCount = allSizes.length;
    const countGe14 = allSizes.filter((s) => s >= 14).length;
    const maxSize = allSizes.length > 0 ? Math.max(...allSizes) : null;

    return {
      name: dayLabel,
      date: d.date,
      day_no: d.day_no ?? d.day_number,
      e2: e2Val,
      endometrium: endoVal,
      totalFollicles: totalCount,
      folliclesGe14: countGe14,
      leadFollicleSize: maxSize,
    };
  });

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      <div className="flex-1 min-w-0 space-y-6 w-full">
        {/* Cycle Selector Header Bar */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#F08080]" />
              <span>Follicular Monitoring & Stimulation Chart</span>
            </h3>
            <p className="text-xs text-slate-500">
              Interactive follicular development, serum estradiol (E2), and endometrial thickness trajectories.
            </p>
          </div>

          {/* Cycle Selector Dropdown */}
          <div className="flex items-center gap-2">
            <label htmlFor="cycle-select" className="text-xs font-semibold text-slate-600">
              Cycle:
            </label>
            <div className="relative">
              <select
                id="cycle-select"
                value={selectedCycleId}
                onChange={(e) => setSelectedCycleId(e.target.value)}
                className="appearance-none bg-slate-50 border border-slate-200 text-slate-900 text-xs font-bold font-mono rounded-lg pl-3 pr-8 py-2 focus:outline-none focus:border-[#F08080] cursor-pointer"
              >
                {timeline?.cycles.map((c) => (
                  <option key={c.cycle_id} value={c.cycle_id}>
                    Cycle {c.cycle_no}: {c.type} ({c.cycle_id})
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Top Summary Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-4 rounded-xl border bg-white border-slate-200 shadow-2xs">
            <div className="text-xs font-semibold text-slate-600">Days of Stimulation</div>
            <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
              {days.length > 0 ? days[days.length - 1].day_no ?? days[days.length - 1].day_number : 0} days
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">{days.length} ultrasound scans</div>
          </div>

          <div className="p-4 rounded-xl border bg-[#FFF8F5] border-[#F8AD9D] shadow-2xs">
            <div className="text-xs font-semibold text-[#A83232]">Peak Estradiol (E2)</div>
            <div className="text-2xl font-bold font-mono text-[#A83232] mt-1">
              {summary?.peak_e2 ? `${summary.peak_e2.toLocaleString()} pg/mL` : '—'}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">
              {summary?.peak_e2 > 3500 ? 'High OHSS risk threshold' : 'Assay at peak'}
            </div>
          </div>

          <div className="p-4 rounded-xl border bg-white border-slate-200 shadow-2xs">
            <div className="text-xs font-semibold text-slate-600">Max Follicles Count</div>
            <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
              {summary?.max_follicles_count ?? 0}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">Bilateral cohort total</div>
          </div>

          <div className="p-4 rounded-xl border bg-white border-slate-200 shadow-2xs">
            <div className="text-xs font-semibold text-slate-600">Trigger Administration</div>
            <div className="text-sm font-bold text-slate-900 mt-1.5 flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${trigger ? 'bg-emerald-500' : 'bg-slate-300'}`} />
              <span>{trigger ? 'Administered' : 'Pending / None'}</span>
            </div>
            <div className="text-[11px] text-slate-500 truncate mt-0.5" title={trigger?.detail}>
              {trigger?.detail || 'No trigger on file'}
            </div>
          </div>
        </div>

        {/* Recharts Chart: Follicles, E2 & Endometrial Thickness */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#F08080]" />
                <span>Longitudinal Progression Curve (Recharts)</span>
              </h4>
              <p className="text-xs text-slate-500">
                Left Y-axis: Serum E2 (pg/mL) & Follicle Count | Right Y-axis: Endometrial Thickness (mm)
              </p>
            </div>

            <div className="flex items-center gap-3 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-[#F08080]">
                <span className="w-2.5 h-2.5 rounded-full bg-[#F08080]" />
                <span>E2 (pg/mL)</span>
              </span>
              <span className="flex items-center gap-1.5 text-emerald-700">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-600" />
                <span>Endometrium (mm)</span>
              </span>
              <span className="flex items-center gap-1.5 text-amber-700">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span>Total Follicles</span>
              </span>
            </div>
          </div>

          {chartData.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-slate-400 text-xs italic">
              <Info className="w-6 h-6 mb-2 text-slate-300" />
              <span>No daily stimulation tracking scans logged for cycle {selectedCycleId}.</span>
            </div>
          ) : (
            <div className="h-80 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 10, right: 25, left: 10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: '#64748B' }}
                    axisLine={{ stroke: '#CBD5E1' }}
                  />
                  <YAxis
                    yAxisId="left"
                    orientation="left"
                    tick={{ fontSize: 11, fill: '#64748B' }}
                    axisLine={{ stroke: '#CBD5E1' }}
                    label={{ value: 'E2 / Follicles', angle: -90, position: 'insideLeft', style: { fill: '#94A3B8', fontSize: 10 } }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    domain={[0, 16]}
                    tick={{ fontSize: 11, fill: '#16A34A' }}
                    axisLine={{ stroke: '#CBD5E1' }}
                    label={{ value: 'Endo (mm)', angle: 90, position: 'insideRight', style: { fill: '#16A34A', fontSize: 10 } }}
                  />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (!active || !payload || !payload.length) return null;
                      const d = payload[0]?.payload;
                      return (
                        <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-lg text-xs space-y-1.5 font-sans">
                          <div className="font-bold text-slate-900 border-b border-slate-100 pb-1">
                            {label} ({d.date})
                          </div>
                          <div className="text-[#A83232] font-semibold flex items-center justify-between gap-4 font-mono">
                            <span>Serum Estradiol:</span>
                            <span>{d.e2 ? `${d.e2.toLocaleString()} pg/mL` : '—'}</span>
                          </div>
                          <div className="text-emerald-700 font-semibold flex items-center justify-between gap-4 font-mono">
                            <span>Endometrium:</span>
                            <span>{d.endometrium ? `${d.endometrium} mm` : '—'}</span>
                          </div>
                          <div className="text-amber-800 font-semibold flex items-center justify-between gap-4 font-mono">
                            <span>Total Follicles:</span>
                            <span>{d.totalFollicles}</span>
                          </div>
                          <div className="text-slate-600 flex items-center justify-between gap-4 font-mono text-[11px]">
                            <span>Follicles ≥ 14 mm:</span>
                            <span>{d.folliclesGe14}</span>
                          </div>
                        </div>
                      );
                    }}
                  />
                  {/* Follicle Count Bars */}
                  <Bar
                    yAxisId="left"
                    dataKey="totalFollicles"
                    name="Follicles"
                    fill="#FBC4AB"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={32}
                  />
                  {/* Estradiol Line in Peach Sorbet primary */}
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="e2"
                    name="Estradiol (E2)"
                    stroke="#F08080"
                    strokeWidth={3}
                    dot={{ fill: '#F08080', r: 4 }}
                    activeDot={{ r: 6, fill: '#A83232' }}
                  />
                  {/* Endometrial Thickness Line in Emerald */}
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="endometrium"
                    name="Endometrium"
                    stroke="#16A34A"
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    dot={{ fill: '#16A34A', r: 3 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Day-Wise Stimulation Log Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="p-4 sm:px-5 bg-slate-50/80 border-b border-slate-200 flex items-center justify-between">
            <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[#F08080]" />
              <span>Day-Wise Follicular Monitoring Scans</span>
            </h4>
            <span className="text-xs text-slate-500 font-mono">
              Cohort breakdown & hormone assays
            </span>
          </div>

          {days.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-xs italic">
              No daily follicular tracking table records found for this cycle.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50/60 border-b border-slate-200 text-slate-700">
                    <th className="p-3.5 font-bold">Stim Day</th>
                    <th className="p-3.5 font-bold">Date</th>
                    <th className="p-3.5 font-bold">Right Ovary Follicles (mm)</th>
                    <th className="p-3.5 font-bold">Left Ovary Follicles (mm)</th>
                    <th className="p-3.5 font-bold">E2 (pg/mL)</th>
                    <th className="p-3.5 font-bold">LH (mIU/mL)</th>
                    <th className="p-3.5 font-bold">Endo (mm)</th>
                    <th className="p-3.5 font-bold">Dose / Protocol Note</th>
                    <th className="p-3.5 font-bold text-right">Source</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {days.map((d: StimulationDayItem, idx: number) => {
                    let rightArr: number[] = [];
                    let leftArr: number[] = [];

                    if (d.follicles && typeof d.follicles === 'object') {
                      if (Array.isArray(d.follicles.right)) rightArr = d.follicles.right;
                      if (Array.isArray(d.follicles.left)) leftArr = d.follicles.left;
                    }

                    const srcId = d.source_refs?.[0];

                    return (
                      <tr key={d.id || idx} className="hover:bg-slate-50/70 transition-colors">
                        <td className="p-3.5 font-mono font-bold text-slate-900">
                          <span className="px-2 py-0.5 rounded bg-[#FFF0ED] text-[#A83232]">
                            Day {d.day_no ?? d.day_number ?? idx + 1}
                          </span>
                        </td>

                        <td className="p-3.5 font-mono text-slate-600">
                          {d.date}
                        </td>

                        <td className="p-3.5 font-mono text-xs">
                          {rightArr.length > 0 ? (
                            <span className="text-slate-800 font-medium">
                              {rightArr.join(', ')}
                            </span>
                          ) : (
                            <span className="text-slate-400 italic">—</span>
                          )}
                        </td>

                        <td className="p-3.5 font-mono text-xs">
                          {leftArr.length > 0 ? (
                            <span className="text-slate-800 font-medium">
                              {leftArr.join(', ')}
                            </span>
                          ) : (
                            <span className="text-slate-400 italic">—</span>
                          )}
                        </td>

                        <td className="p-3.5 font-mono font-bold text-[#A83232]">
                          {d.e2 ? d.e2.toLocaleString() : '—'}
                        </td>

                        <td className="p-3.5 font-mono text-slate-700">
                          {d.lh ?? '—'}
                        </td>

                        <td className="p-3.5 font-mono font-semibold text-emerald-800">
                          {d.endometrium_mm ? `${d.endometrium_mm} mm` : '—'}
                        </td>

                        <td className="p-3.5 text-slate-700 max-w-xs">
                          {d.dose_note || d.notes ? (
                            <span className="text-[11px] leading-tight block">
                              {d.dose_note || d.notes}
                            </span>
                          ) : (
                            <span className="text-slate-400 italic">—</span>
                          )}
                        </td>

                        <td className="p-3.5 text-right">
                          {srcId && (
                            <button
                              type="button"
                              onClick={() => setSelectedCitation({ source_id: srcId, type: 'stimulation_chart' })}
                              className="font-mono text-[11px] px-2 py-0.5 rounded bg-white hover:bg-[#FFF5F2] text-slate-700 hover:text-[#A83232] border border-slate-200 hover:border-[#F8AD9D] transition-colors cursor-pointer"
                              title="Click to view source record"
                            >
                              <FileCheck className="w-3 h-3 text-[#F08080] inline mr-1" />
                              <span>[{srcId}]</span>
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
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
    </div>
  );
};
