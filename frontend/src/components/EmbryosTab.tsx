import React, { useState, useEffect } from 'react';
import { patientsApi, ApiClientError } from '../services/api';
import type { EmbryosResponse, EmbryoItem, Citation } from '../types/api';
import { SourceViewer } from './SourceViewer';
import {
  Baby,
  Snowflake,
  ArrowRightCircle,
  Trash2,
  Layers,
  AlertTriangle,
  Loader2,
  FileCheck,
  Search,
} from 'lucide-react';

interface EmbryosTabProps {
  patientId: string;
}

export const EmbryosTab: React.FC<EmbryosTabProps> = ({ patientId }) => {
  const [data, setData] = useState<EmbryosResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [fateFilter, setFateFilter] = useState<'all' | 'frozen' | 'transferred' | 'discarded'>('all');
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  const loadEmbryos = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await patientsApi.getEmbryos(patientId);
      setData(res);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Unable to load embryo inventory.');
      } else {
        setError('Network error while retrieving embryo ledger.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadEmbryos();
  }, [patientId]);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
        <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
        <h3 className="text-sm font-bold text-slate-800">Loading Embryology Ledger...</h3>
        <p className="text-xs text-slate-500 mt-1">Retrieving vitrification tanks, grades, and cryostorage status.</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-rose-200 p-8 shadow-xs max-w-xl mx-auto text-center space-y-3">
        <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto" />
        <h3 className="text-sm font-bold text-slate-900">Error Loading Embryos</h3>
        <p className="text-xs text-rose-700">{error || 'Data unavailable.'}</p>
        <button
          onClick={loadEmbryos}
          className="px-4 py-1.5 bg-[#FFF0ED] text-[#A83232] font-semibold text-xs rounded-lg border border-[#F8AD9D] hover:bg-[#FEEBE3]"
        >
          Retry
        </button>
      </div>
    );
  }

  const embryosList = data.embryos || [];
  const filteredEmbryos = embryosList.filter((emb) => {
    const matchesSearch =
      (emb.embryo_label && emb.embryo_label.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (emb.id && emb.id.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (emb.cycle_id && emb.cycle_id.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (emb.grade && emb.grade.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesFate = fateFilter === 'all' || emb.fate.toLowerCase() === fateFilter;
    return matchesSearch && matchesFate;
  });

  const getFateBadge = (fate: string) => {
    const f = fate.toLowerCase();
    switch (f) {
      case 'frozen':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#EBF5FB] text-[#2471A3] border border-[#AED6F1]">
            <Snowflake className="w-3 h-3 text-[#2980B9]" />
            Frozen
          </span>
        );
      case 'transferred':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <ArrowRightCircle className="w-3 h-3 text-emerald-600" />
            Transferred
          </span>
        );
      case 'discarded':
      case 'arrested':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
            <Trash2 className="w-3 h-3 text-slate-500" />
            Discarded
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-100 text-slate-700">
            {fate}
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      <div className="flex-1 min-w-0 space-y-6 w-full">
        {/* Remaining Frozen Count & Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Prominent Remaining Frozen Count Card */}
          <div className="p-4 rounded-xl border bg-[#FFF8F5] border-[#F8AD9D] shadow-2xs">
            <div className="flex items-center justify-between text-xs font-semibold text-[#A83232]">
              <span>Remaining Frozen</span>
              <Snowflake className="w-4 h-4 text-[#F08080]" />
            </div>
            <div className="text-3xl font-bold font-mono text-[#A83232] mt-1">
              {data.remaining_frozen ?? 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Vitrified in cryostorage</div>
          </div>

          <div className="p-4 rounded-xl border bg-white border-slate-200 shadow-2xs">
            <div className="flex items-center justify-between text-xs font-semibold text-emerald-800">
              <span>Transferred</span>
              <ArrowRightCircle className="w-4 h-4 text-emerald-600" />
            </div>
            <div className="text-3xl font-bold font-mono text-emerald-900 mt-1">
              {data.transferred_count ?? 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Fresh or FET procedures</div>
          </div>

          <div className="p-4 rounded-xl border bg-white border-slate-200 shadow-2xs">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-600">
              <span>Discarded / Arrested</span>
              <Trash2 className="w-4 h-4 text-slate-400" />
            </div>
            <div className="text-3xl font-bold font-mono text-slate-800 mt-1">
              {data.discarded_count ?? 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Developmental arrest</div>
          </div>

          <div className="p-4 rounded-xl border bg-white border-slate-200 shadow-2xs">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
              <span>Total Cultured</span>
              <Layers className="w-4 h-4 text-slate-500" />
            </div>
            <div className="text-3xl font-bold font-mono text-slate-900 mt-1">
              {data.total_count ?? embryosList.length}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Across all treatment cycles</div>
          </div>
        </div>

        {/* Filter and Search Bar */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-2xs flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search embryo ID, grade..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-[#F08080] w-48 sm:w-60"
              />
            </div>

            <div className="flex items-center gap-1 text-xs">
              {(['all', 'frozen', 'transferred', 'discarded'] as const).map((fate) => (
                <button
                  key={fate}
                  onClick={() => setFateFilter(fate)}
                  className={`px-2.5 py-1 rounded-md capitalize font-semibold transition-all cursor-pointer ${
                    fateFilter === fate
                      ? 'bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D]'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  {fate}
                </button>
              ))}
            </div>
          </div>

          <div className="text-xs text-slate-500 font-mono">
            Showing {filteredEmbryos.length} of {embryosList.length} embryos
          </div>
        </div>

        {/* Embryo Ledger Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="p-4 sm:px-5 bg-slate-50/80 border-b border-slate-200 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Baby className="w-4 h-4 text-[#F08080]" />
              <span>Embryo Vitrification & Culturing Ledger</span>
            </h3>
            <span className="text-xs text-slate-500 font-mono">
              Gardner Morphology & Tank Locations
            </span>
          </div>

          {filteredEmbryos.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-xs italic">
              No embryos match the current search / filter criteria.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50/60 border-b border-slate-200 text-slate-700">
                    <th className="p-3.5 font-bold">Embryo ID</th>
                    <th className="p-3.5 font-bold">Cycle</th>
                    <th className="p-3.5 font-bold">Day</th>
                    <th className="p-3.5 font-bold">Morphology Grade</th>
                    <th className="p-3.5 font-bold">PGT Status</th>
                    <th className="p-3.5 font-bold">Fate</th>
                    <th className="p-3.5 font-bold">Cryostorage Location</th>
                    <th className="p-3.5 font-bold text-right">Source</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {filteredEmbryos.map((emb: EmbryoItem) => {
                    const srcId = emb.source_refs?.[0];

                    return (
                      <tr key={emb.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="p-3.5 font-mono font-bold text-slate-900">
                          <div className="flex items-center gap-1.5">
                            <span className="w-5 h-5 rounded-full bg-[#FFF0ED] text-[#A83232] flex items-center justify-center text-[10px] font-bold">
                              {emb.embryo_label || emb.embryo_number || 'E'}
                            </span>
                            <span>{emb.id}</span>
                          </div>
                        </td>

                        <td className="p-3.5 font-mono text-slate-600">
                          {emb.cycle_id}
                        </td>

                        <td className="p-3.5 font-mono font-medium text-slate-800">
                          Day {emb.day}
                        </td>

                        <td className="p-3.5">
                          {emb.grade ? (
                            <span className="font-mono font-bold text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200">
                              {emb.grade}
                            </span>
                          ) : (
                            <span className="text-slate-400 italic">Not graded</span>
                          )}
                        </td>

                        <td className="p-3.5 font-mono text-[11px] text-slate-600">
                          {emb.pgt_status || emb.pgt_result || 'Untested'}
                        </td>

                        <td className="p-3.5">
                          {getFateBadge(emb.fate)}
                        </td>

                        <td className="p-3.5 text-slate-700">
                          {emb.storage_location ? (
                            <span className="font-mono text-[11px] text-slate-600 bg-slate-50 px-2 py-0.5 rounded border border-slate-100">
                              {emb.storage_location}
                            </span>
                          ) : (
                            <span className="text-slate-400 italic">—</span>
                          )}
                        </td>

                        <td className="p-3.5 text-right">
                          {srcId && (
                            <button
                              type="button"
                              onClick={() => setSelectedCitation({ source_id: srcId, type: 'embryology_report' })}
                              className="font-mono text-[11px] px-2 py-0.5 rounded bg-white hover:bg-[#FFF5F2] text-slate-700 hover:text-[#A83232] border border-slate-200 hover:border-[#F8AD9D] transition-colors cursor-pointer"
                              title="Click to view source report"
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
