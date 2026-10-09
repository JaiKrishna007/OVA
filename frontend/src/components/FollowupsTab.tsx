import React, { useState, useEffect } from 'react';
import { patientsApi, ApiClientError } from '../services/api';
import type { FollowupsResponse, FollowupItem, Citation } from '../types/api';
import { SourceViewer } from './SourceViewer';
import {
  Clock,
  CheckCircle2,
  AlertTriangle,
  Calendar,
  Loader2,
  FileCheck,
  Check,
  Filter,
} from 'lucide-react';

interface FollowupsTabProps {
  patientId: string;
  onSelectCitation?: (cit: Citation) => void;
}

export const FollowupsTab: React.FC<FollowupsTabProps> = ({ patientId }) => {
  const [data, setData] = useState<FollowupsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<'all' | 'overdue' | 'scheduled' | 'pending' | 'done'>('all');
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  const loadFollowups = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await patientsApi.getFollowups(patientId);
      setData(res);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Unable to retrieve clinical follow-ups.');
      } else {
        setError('Network error while retrieving follow-ups.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadFollowups();
  }, [patientId]);

  const handleMarkDone = async (item: FollowupItem) => {
    setUpdatingId(item.id);
    try {
      await patientsApi.updateFollowup(item.id, { status: 'done' });
      // Reload fresh data from backend
      const refreshed = await patientsApi.getFollowups(patientId);
      setData(refreshed);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to update follow-up status.');
    } finally {
      setUpdatingId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
        <Loader2 className="w-8 h-8 text-[#F08080] animate-spin mx-auto mb-3" />
        <h3 className="text-sm font-bold text-slate-800">Loading Clinical Follow-ups...</h3>
        <p className="text-xs text-slate-500 mt-1">Retrieving scheduled investigations and overdue actions.</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-rose-200 p-8 shadow-xs max-w-xl mx-auto text-center space-y-3">
        <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto" />
        <h3 className="text-sm font-bold text-slate-900">Error Loading Follow-ups</h3>
        <p className="text-xs text-rose-700">{error || 'Data unavailable.'}</p>
        <button
          onClick={loadFollowups}
          className="px-4 py-1.5 bg-[#FFF0ED] text-[#A83232] font-semibold text-xs rounded-lg border border-[#F8AD9D] hover:bg-[#FEEBE3]"
        >
          Retry
        </button>
      </div>
    );
  }

  const allItems: FollowupItem[] = [
    ...(data.overdue || []).map((i) => ({ ...i, status: 'overdue' as const })),
    ...(data.scheduled || []).map((i) => ({ ...i, status: 'scheduled' as const })),
    ...(data.pending || []).map((i) => ({ ...i, status: 'pending' as const })),
    ...(data.done || []).map((i) => ({ ...i, status: 'done' as const })),
  ];

  const filteredItems = allItems.filter((it) => {
    if (filterCategory === 'all') return true;
    return it.status === filterCategory;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'overdue':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-50 text-rose-800 border border-rose-200">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
            Overdue
          </span>
        );
      case 'scheduled':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
            <Calendar className="w-3 h-3 text-amber-600" />
            Scheduled
          </span>
        );
      case 'pending':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-sky-50 text-sky-800 border border-sky-200">
            <Clock className="w-3 h-3 text-sky-600" />
            Pending Action
          </span>
        );
      case 'done':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Completed
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      <div className="flex-1 min-w-0 space-y-6 w-full">
        {/* Status Metrics Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div
            onClick={() => setFilterCategory('overdue')}
            className={`p-4 rounded-xl border transition-all cursor-pointer ${
              filterCategory === 'overdue'
                ? 'bg-[#FFF0ED] border-[#F8AD9D] ring-2 ring-[#F08080]/30'
                : 'bg-white border-slate-200 hover:border-[#FBC4AB]'
            }`}
          >
            <div className="flex items-center justify-between text-xs font-semibold text-rose-800">
              <span>Overdue</span>
              <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
            </div>
            <div className="text-2xl font-bold font-mono text-rose-900 mt-1">
              {data.counts?.overdue || 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Requires immediate review</div>
          </div>

          <div
            onClick={() => setFilterCategory('scheduled')}
            className={`p-4 rounded-xl border transition-all cursor-pointer ${
              filterCategory === 'scheduled'
                ? 'bg-[#FFF8F2] border-[#FBC4AB] ring-2 ring-[#F08080]/30'
                : 'bg-white border-slate-200 hover:border-[#FBC4AB]'
            }`}
          >
            <div className="flex items-center justify-between text-xs font-semibold text-amber-800">
              <span>Scheduled</span>
              <Calendar className="w-3.5 h-3.5 text-amber-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-amber-900 mt-1">
              {data.counts?.scheduled || 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Upcoming appointments</div>
          </div>

          <div
            onClick={() => setFilterCategory('pending')}
            className={`p-4 rounded-xl border transition-all cursor-pointer ${
              filterCategory === 'pending'
                ? 'bg-sky-50/50 border-sky-300 ring-2 ring-sky-400/30'
                : 'bg-white border-slate-200 hover:border-[#FBC4AB]'
            }`}
          >
            <div className="flex items-center justify-between text-xs font-semibold text-sky-800">
              <span>Pending</span>
              <Clock className="w-3.5 h-3.5 text-sky-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-sky-900 mt-1">
              {data.counts?.pending || 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Orders awaiting booking</div>
          </div>

          <div
            onClick={() => setFilterCategory('done')}
            className={`p-4 rounded-xl border transition-all cursor-pointer ${
              filterCategory === 'done'
                ? 'bg-emerald-50/50 border-emerald-300 ring-2 ring-emerald-400/30'
                : 'bg-white border-slate-200 hover:border-[#FBC4AB]'
            }`}
          >
            <div className="flex items-center justify-between text-xs font-semibold text-emerald-800">
              <span>Completed</span>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-emerald-900 mt-1">
              {data.counts?.done || 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Verified & closed</div>
          </div>
        </div>

        {/* Filters and Search Bar */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-2xs flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-400 mr-1" />
            <span className="text-slate-500 font-medium">Filter:</span>
            {(['all', 'overdue', 'scheduled', 'pending', 'done'] as const).map((cat) => (
              <button
                key={cat}
                onClick={() => setFilterCategory(cat)}
                className={`px-2.5 py-1 rounded-md capitalize font-semibold transition-all cursor-pointer ${
                  filterCategory === cat
                    ? 'bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D]'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="text-xs text-slate-500 font-mono">
            As-of reference date: <strong className="text-slate-700">{data.as_of_date}</strong>
          </div>
        </div>

        {/* Followups List */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="p-4 sm:px-5 bg-slate-50/80 border-b border-slate-200 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Clock className="w-4 h-4 text-[#F08080]" />
              <span>Follow-up & Investigation Schedule</span>
            </h3>
            <span className="text-xs text-slate-500 font-mono">
              Showing {filteredItems.length} of {allItems.length}
            </span>
          </div>

          {filteredItems.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-xs italic">
              No follow-up items found for filter "{filterCategory}".
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filteredItems.map((item) => {
                const isOverdue = item.status === 'overdue';
                const isUpdating = updatingId === item.id;
                const srcId = item.source_refs?.[0] || item.source_id;

                return (
                  <div
                    key={item.id}
                    className={`p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-colors ${
                      isOverdue ? 'bg-rose-50/20 hover:bg-rose-50/40' : 'hover:bg-slate-50/60'
                    }`}
                  >
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className="text-xs font-bold text-slate-900">
                          {item.name}
                        </span>
                        {getStatusBadge(item.status)}
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                          {item.kind ? item.kind.replace(/_/g, ' ') : 'investigation'}
                        </span>
                      </div>

                      <div className="text-xs text-slate-600 flex items-center gap-3 flex-wrap">
                        <span className="flex items-center gap-1 font-mono text-[11px]">
                          <Calendar className="w-3 h-3 text-slate-400" />
                          <span>Due: {item.due_date || 'Not specified'}</span>
                        </span>
                        {item.cycle_id && (
                          <span className="font-mono text-[11px] text-slate-500">
                            Cycle: {item.cycle_id}
                          </span>
                        )}
                        {srcId && (
                          <button
                            type="button"
                            onClick={() =>
                              setSelectedCitation({
                                source_id: srcId,
                                type: 'clinical_record',
                              })
                            }
                            className="font-mono text-[11px] px-2 py-0.5 rounded bg-white hover:bg-[#FFF5F2] text-slate-700 hover:text-[#A83232] border border-slate-200 hover:border-[#F8AD9D] transition-colors flex items-center gap-1 cursor-pointer"
                            title="Click to view source record"
                          >
                            <FileCheck className="w-3 h-3 text-[#F08080]" />
                            <span>[{srcId}]</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Action: Mark Done via PATCH */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {item.status !== 'done' ? (
                        <button
                          type="button"
                          onClick={() => handleMarkDone(item)}
                          disabled={isUpdating}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-2xs transition-all disabled:opacity-50 cursor-pointer"
                        >
                          {isUpdating ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Check className="w-3.5 h-3.5" />
                          )}
                          <span>{isUpdating ? 'Updating...' : 'Mark Done'}</span>
                        </button>
                      ) : (
                        <span className="text-xs font-bold text-emerald-700 flex items-center gap-1">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          <span>Done</span>
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
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
