import React, { useState, useEffect } from 'react';
import { patientsApi, ApiClientError } from '../services/api';
import type { PaginatedRecordsResponse, RecordSummaryItem, Citation } from '../types/api';
import { SourceViewer } from './SourceViewer';
import { AddRecordModal } from './AddRecordModal';
import {
  FileText,
  Search,
  Filter,
  ShieldCheck,
  ShieldAlert,
  Calendar,
  User,
  Loader2,
  AlertTriangle,
  ChevronRight,
  Upload,
} from 'lucide-react';

interface SourcesTabProps {
  patientId: string;
}

export const SourcesTab: React.FC<SourcesTabProps> = ({ patientId }) => {
  const [data, setData] = useState<PaginatedRecordsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedCycle, setSelectedCycle] = useState<string>('all');
  const [selectedOrigin, setSelectedOrigin] = useState<string>('all');

  const loadRecords = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await patientsApi.getRecords(patientId, 1, 50);
      setData(res);
      // Auto-select first record if none selected
      if (res.records && res.records.length > 0 && !selectedCitation) {
        setSelectedCitation({
          source_id: res.records[0].id,
          type: res.records[0].type,
        });
      }
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Unable to retrieve source records.');
      } else {
        setError('Network error while retrieving records.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRecords();
  }, [patientId]);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
        <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
        <h3 className="text-sm font-bold text-slate-800">Loading Immutable Source Records...</h3>
        <p className="text-xs text-slate-500 mt-1">Retrieving original clinic notes, lab reports, and external summaries.</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-rose-200 p-8 shadow-xs max-w-xl mx-auto text-center space-y-3">
        <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto" />
        <h3 className="text-sm font-bold text-slate-900">Error Loading Source Records</h3>
        <p className="text-xs text-rose-700">{error || 'Data unavailable.'}</p>
        <button
          onClick={loadRecords}
          className="px-4 py-1.5 bg-[#FFF0ED] text-[#A83232] font-semibold text-xs rounded-lg border border-[#F8AD9D] hover:bg-[#FEEBE3]"
        >
          Retry
        </button>
      </div>
    );
  }

  const rawRecords = data.records || [];

  // Unique options for dropdown filters
  const uniqueTypes = Array.from(new Set(rawRecords.map((r) => r.type))).filter(Boolean);
  const uniqueCycles = Array.from(new Set(rawRecords.map((r) => r.cycle_id))).filter(Boolean) as string[];
  const uniqueOrigins = Array.from(new Set(rawRecords.map((r) => r.origin_org))).filter(Boolean);

  const filteredRecords = rawRecords.filter((rec) => {
    const matchesSearch =
      searchTerm === '' ||
      rec.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (rec.content_text && rec.content_text.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (rec.author && rec.author.toLowerCase().includes(searchTerm.toLowerCase())) ||
      rec.type.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesType = selectedType === 'all' || rec.type === selectedType;
    const matchesCycle = selectedCycle === 'all' || rec.cycle_id === selectedCycle;
    const matchesOrigin = selectedOrigin === 'all' || rec.origin_org === selectedOrigin;

    return matchesSearch && matchesType && matchesCycle && matchesOrigin;
  });

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      {/* Left Column: Records Browser */}
      <div className="flex-1 min-w-0 space-y-5 w-full">
        {/* Controls & Search Filter Bar */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-2xs space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search records by ID, content text, clinician..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-[#F08080]"
              />
            </div>

            <div className="flex items-center gap-3">
              <div className="text-xs text-slate-500 font-mono flex items-center gap-1.5 flex-shrink-0">
                <FileText className="w-3.5 h-3.5 text-slate-400" />
                <span>
                  {filteredRecords.length} of {rawRecords.length} records
                </span>
              </div>

              <button
                type="button"
                id="add-record-button"
                onClick={() => setIsUploadModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-white bg-[#A83232] hover:bg-[#912B2B] rounded-lg shadow-xs transition-colors shrink-0"
              >
                <Upload className="w-3.5 h-3.5" />
                <span>Add Record</span>
              </button>
            </div>
          </div>

          {/* Filter Dropdowns: Type, Cycle, Origin */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100 text-xs">
            <span className="text-slate-500 font-semibold flex items-center gap-1 mr-1">
              <Filter className="w-3 h-3 text-slate-400" />
              <span>Filters:</span>
            </span>

            {/* Type Filter */}
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1 focus:outline-none focus:border-[#F08080] cursor-pointer"
            >
              <option value="all">All Document Types</option>
              {uniqueTypes.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, ' ')}
                </option>
              ))}
            </select>

            {/* Cycle Filter */}
            <select
              value={selectedCycle}
              onChange={(e) => setSelectedCycle(e.target.value)}
              className="bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1 focus:outline-none focus:border-[#F08080] cursor-pointer"
            >
              <option value="all">All Cycles</option>
              {uniqueCycles.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            {/* Origin Filter */}
            <select
              value={selectedOrigin}
              onChange={(e) => setSelectedOrigin(e.target.value)}
              className="bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-md px-2 py-1 focus:outline-none focus:border-[#F08080] max-w-[220px] truncate cursor-pointer"
            >
              <option value="all">All Origin Facilities</option>
              {uniqueOrigins.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>

            {(selectedType !== 'all' || selectedCycle !== 'all' || selectedOrigin !== 'all' || searchTerm !== '') && (
              <button
                type="button"
                onClick={() => {
                  setSelectedType('all');
                  setSelectedCycle('all');
                  setSelectedOrigin('all');
                  setSearchTerm('');
                }}
                className="text-[11px] text-[#A83232] font-semibold hover:underline ml-1 cursor-pointer"
              >
                Reset
              </button>
            )}
          </div>
        </div>

        {/* Records Cards List */}
        <div className="space-y-3">
          {filteredRecords.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500 text-xs italic">
              No clinical records match the selected filters.
            </div>
          ) : (
            filteredRecords.map((rec: RecordSummaryItem) => {
              const isSelected = selectedCitation?.source_id === rec.id;
              const isExternal =
                rec.trust_status === 'external_unverified' ||
                rec.origin_org?.toLowerCase().includes('hospital x');

              return (
                <div
                  key={rec.id}
                  onClick={() =>
                    setSelectedCitation({
                      source_id: rec.id,
                      type: rec.type,
                    })
                  }
                  className={`p-4 sm:p-5 rounded-xl border transition-all cursor-pointer bg-white shadow-2xs space-y-3 ${
                    isSelected
                      ? 'border-[#F8AD9D] ring-2 ring-[#F08080]/30 bg-[#FFFDFB]'
                      : 'border-slate-200 hover:border-[#FBC4AB] hover:shadow-xs'
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200">
                        {rec.id}
                      </span>
                      <span className="text-xs font-bold text-slate-900 uppercase">
                        {rec.type ? rec.type.replace(/_/g, ' ') : 'Clinical Document'}
                      </span>
                      {rec.cycle_id && (
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                          {rec.cycle_id}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded ${
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

                      <span className="font-mono text-[11px] text-slate-400">
                        v{rec.version}
                      </span>
                    </div>
                  </div>

                  {/* Excerpt preview */}
                  <div className="text-xs text-slate-600 leading-relaxed font-mono bg-slate-50/70 p-2.5 rounded-lg border border-slate-100 line-clamp-2">
                    {rec.content_excerpt || rec.content_text?.slice(0, 150) || 'No content preview available.'}
                  </div>

                  {/* Metadata Row */}
                  <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
                    <div className="flex items-center gap-4 flex-wrap">
                      <span className="flex items-center gap-1 font-mono text-[11px]">
                        <Calendar className="w-3 h-3 text-slate-400" />
                        <span>{rec.date}</span>
                      </span>
                      {rec.author && (
                        <span className="flex items-center gap-1 text-[11px]">
                          <User className="w-3 h-3 text-slate-400" />
                          <span>{rec.author}</span>
                        </span>
                      )}
                      <span className="text-[11px] text-slate-400 truncate max-w-xs" title={rec.origin_org}>
                        {rec.origin_org}
                      </span>
                    </div>

                    <div className="flex items-center gap-1 text-[11px] font-semibold text-[#A83232]">
                      <span>Open in Viewer</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </div>
                  </div>
                </div>
              );
            })
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

      {/* Add Record Modal */}
      <AddRecordModal
        patientId={patientId}
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onSuccess={(newRec) => {
          loadRecords();
          setSelectedCitation({
            source_id: newRec.id,
            type: newRec.type,
          });
        }}
      />
    </div>
  );
};
