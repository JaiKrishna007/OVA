import React, { useState, useEffect } from 'react';
import { patientsApi, ApiClientError } from '../services/api';
import type { CycleComparisonResponse, Citation } from '../types/api';
import { SourceViewer } from './SourceViewer';
import {
  Columns,
  AlertTriangle,
  Loader2,
  ArrowRightLeft,
  Calendar,
  HelpCircle,
} from 'lucide-react';

interface CompareTabProps {
  patientId: string;
}

const COMPARISON_METRICS: Array<{
  key: string;
  label: string;
  unit?: string;
}> = [
  { key: 'type', label: 'Treatment Type' },
  { key: 'protocol', label: 'Stimulation Protocol' },
  { key: 'start_date', label: 'Cycle Start' },
  { key: 'end_date', label: 'Cycle End' },
  { key: 'days_of_stim', label: 'Days of Stimulation', unit: 'days' },
  { key: 'e2_at_trigger', label: 'Peak / Trigger E2', unit: 'pg/mL' },
  { key: 'follicles_ge_14mm_at_trigger', label: 'Follicles ≥ 14 mm', unit: 'follicles' },
  { key: 'oocytes', label: 'Oocytes Retrieved', unit: 'oocytes' },
  { key: 'mii', label: 'Mature Oocytes (MII)', unit: 'MII' },
  { key: 'fertilization', label: 'Fertilization (2PN)', unit: 'embryos' },
  { key: 'blastocysts', label: 'Blastocysts Cultured', unit: 'blastocysts' },
  { key: 'transfer', label: 'Embryo Transfer' },
  { key: 'outcome', label: 'Cycle Outcome' },
  { key: 'origin_org', label: 'Origin Facility' },
];

export const CompareTab: React.FC<CompareTabProps> = ({ patientId }) => {
  const [data, setData] = useState<CycleComparisonResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  const loadComparison = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await patientsApi.getCycleComparison(patientId);
      setData(res);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Unable to retrieve cycle comparison data.');
      } else {
        setError('Network error while retrieving cycle comparison.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadComparison();
  }, [patientId]);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
        <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
        <h3 className="text-sm font-bold text-slate-800">Building Cycle Comparison Matrix...</h3>
        <p className="text-xs text-slate-500 mt-1">Cross-referencing stimulation parameters and outcomes.</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-rose-200 p-8 shadow-xs max-w-xl mx-auto text-center space-y-3">
        <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto" />
        <h3 className="text-sm font-bold text-slate-900">Error Loading Cycle Comparison</h3>
        <p className="text-xs text-rose-700">{error || 'Data unavailable.'}</p>
        <button
          onClick={loadComparison}
          className="px-4 py-1.5 bg-[#FFF0ED] text-[#A83232] font-semibold text-xs rounded-lg border border-[#F8AD9D] hover:bg-[#FEEBE3]"
        >
          Retry
        </button>
      </div>
    );
  }

  const matrix = data.comparison_matrix || [];
  const conflicts = data.conflicts || [];

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      <div className="flex-1 min-w-0 space-y-6 w-full">
        {/* Top Header Controls */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Columns className="w-4 h-4 text-[#F08080]" />
              <span>Multi-Cycle Longitudinal Comparison Matrix</span>
            </h3>
            <p className="text-xs text-slate-500">
              Comparative analysis across {matrix.length} treatment {matrix.length === 1 ? 'cycle' : 'cycles'}.
              Empty parameters indicate undocumented records in patient chart.
            </p>
          </div>

          <div className="text-xs text-slate-500 font-mono flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span>Cycles: {matrix.length} tracked</span>
          </div>
        </div>

        {/* Prominent Conflicts Flag Banner (e.g. P-103 duplicate lab AMH) */}
        {conflicts.length > 0 && (
          <div className="rounded-xl bg-amber-50 border border-amber-300 p-4 sm:p-5 shadow-2xs space-y-3">
            <div className="flex items-center gap-2 text-amber-900">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <h4 className="text-xs font-bold uppercase tracking-wider">
                Clinical Discrepancy Flagged ({conflicts.length})
              </h4>
            </div>

            <div className="space-y-2">
              {conflicts.map((conf: any, idx: number) => {
                const srcA = conf.source_id_a || conf.source_refs?.[0];
                const srcB = conf.source_id_b || conf.source_refs?.[1];

                return (
                  <div
                    key={idx}
                    className="p-3 bg-white/90 rounded-lg border border-amber-200 text-xs text-amber-950 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="space-y-0.5">
                      <div className="font-bold flex items-center gap-2">
                        <ArrowRightLeft className="w-3.5 h-3.5 text-[#F08080]" />
                        <span>{conf.description || conf.field || 'Conflicting values detected across records.'}</span>
                      </div>
                      <div className="text-[11px] text-slate-600 font-mono">
                        Value A: <strong className="text-[#A83232]">{String(conf.value_a)}</strong> vs Value B: <strong className="text-amber-800">{String(conf.value_b)}</strong>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {srcA && (
                        <button
                          type="button"
                          onClick={() => setSelectedCitation({ source_id: srcA, type: conf.source_type_a || 'record' })}
                          className="font-mono text-[11px] px-2 py-0.5 rounded bg-white hover:bg-slate-100 text-[#A83232] border border-[#F8AD9D] font-bold"
                        >
                          [{srcA}]
                        </button>
                      )}
                      {srcB && (
                        <button
                          type="button"
                          onClick={() => setSelectedCitation({ source_id: srcB, type: conf.source_type_b || 'record' })}
                          className="font-mono text-[11px] px-2 py-0.5 rounded bg-white hover:bg-slate-100 text-amber-800 border border-amber-300 font-bold"
                        >
                          [{srcB}]
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Comparison Matrix Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="p-3.5 sm:px-4 font-bold text-slate-700 w-52 sticky left-0 bg-slate-50 z-10 border-r border-slate-200">
                    Clinical Parameter
                  </th>
                  {matrix.map((col: any, idx: number) => (
                    <th key={col.cycle_id || idx} className="p-3.5 sm:px-4 min-w-[200px] border-r border-slate-100">
                      <div className="space-y-1">
                        <div className="flex items-center justify-between gap-1">
                          <span className="font-bold text-slate-900">
                            Cycle {col.cycle_no || idx + 1}
                          </span>
                          <span className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-slate-200 text-slate-700">
                            {col.cycle_id}
                          </span>
                        </div>
                        <div className="text-[11px] font-semibold text-slate-500 uppercase">
                          {col.type || 'IVF'}
                        </div>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100">
                {COMPARISON_METRICS.map(({ key, label, unit }) => (
                  <tr key={key} className="hover:bg-slate-50/50 transition-colors">
                    <td className="p-3.5 sm:px-4 font-semibold text-slate-700 sticky left-0 bg-white z-10 border-r border-slate-200 flex items-center justify-between gap-2">
                      <span>{label}</span>
                      {unit && <span className="text-[10px] text-slate-400 font-mono">({unit})</span>}
                    </td>

                    {matrix.map((col: any, cIdx: number) => {
                      const rawVal = col[key];
                      const isAbsent = rawVal === null || rawVal === undefined || rawVal === '';
                      const srcRefs = col.source_refs || [];

                      return (
                        <td key={col.cycle_id || cIdx} className="p-3.5 sm:px-4 border-r border-slate-100 align-top">
                          {isAbsent ? (
                            <div className="flex items-center gap-1.5 text-slate-400 italic font-sans text-[11px]">
                              <HelpCircle className="w-3 h-3 text-slate-300" />
                              <span>Not documented</span>
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <div className="font-bold text-slate-900 font-mono">
                                {typeof rawVal === 'number' ? rawVal.toLocaleString() : String(rawVal)}
                                {unit && typeof rawVal === 'number' ? ` ${unit}` : ''}
                              </div>

                              {/* Citation tooltip chips for this cycle */}
                              {srcRefs.length > 0 && (
                                <div className="flex items-center gap-1 flex-wrap pt-0.5">
                                  {srcRefs.slice(0, 2).map((ref: string) => (
                                    <button
                                      key={ref}
                                      type="button"
                                      onClick={() => setSelectedCitation({ source_id: ref, type: 'clinical_record' })}
                                      className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-slate-100 hover:bg-[#FFF0ED] text-slate-600 hover:text-[#A83232] border border-slate-200 hover:border-[#F8AD9D] transition-colors cursor-pointer"
                                      title={`Source reference ${ref}`}
                                    >
                                      [{ref}]
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
