import React, { useState, useEffect, useCallback } from 'react';
import { auditApi, ApiClientError } from '../services/api';
import type { AuditLogItem } from '../types/api';
import {
  ShieldAlert,
  Loader2,
  AlertCircle,
  RefreshCw,
  Download,
  Filter,
  ChevronDown,
  ChevronUp,
  LogIn,
  Eye,
  FileText,
  GitMerge,
  ClipboardCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowRightLeft,
  ShieldCheck,
  Search,
  SlidersHorizontal,
} from 'lucide-react';

// ─── Event type metadata ────────────────────────────────────────────────────

const EVENT_ICONS: Record<string, React.ElementType> = {
  LOGIN:                    LogIn,
  LOGOUT:                   LogIn,
  PATIENT_VIEWED:           Eye,
  RECORD_VIEWED:            FileText,
  RECORD_UPLOADED:          FileText,
  EXTRACTION_RUN:           GitMerge,
  CLAIM_VERIFIED:           CheckCircle2,
  CLAIM_ACCEPTED:           CheckCircle2,
  CLAIM_REJECTED:           XCircle,
  CONFLICT_DETECTED:        AlertTriangle,
  CONFLICT_ACKNOWLEDGED:    ClipboardCheck,
  GAP_DETECTED:             AlertTriangle,
  SUMMARY_GENERATED:        FileText,
  ASK_ALLOWED:              Eye,
  S1_BLOCK:                 ShieldAlert,
  CONSENT_GRANTED:          ShieldCheck,
  CONSENT_REVOKED:          XCircle,
  TRANSFER_REQUESTED:       ArrowRightLeft,
  TRANSFER_ACCEPTED:        CheckCircle2,
  TRANSFER_REJECTED:        XCircle,
  TRANSFER_CANCELLED:       XCircle,
};

const EVENT_COLORS: Record<string, string> = {
  LOGIN:                    'bg-slate-100 text-slate-600',
  PATIENT_VIEWED:           'bg-blue-50 text-blue-700',
  RECORD_VIEWED:            'bg-blue-50 text-blue-700',
  RECORD_UPLOADED:          'bg-indigo-50 text-indigo-700',
  EXTRACTION_RUN:           'bg-purple-50 text-purple-700',
  CLAIM_ACCEPTED:           'bg-emerald-50 text-emerald-700',
  CLAIM_REJECTED:           'bg-rose-50 text-rose-700',
  CONFLICT_DETECTED:        'bg-amber-50 text-amber-700',
  CONFLICT_ACKNOWLEDGED:    'bg-teal-50 text-teal-700',
  GAP_DETECTED:             'bg-amber-50 text-amber-700',
  SUMMARY_GENERATED:        'bg-pink-50 text-pink-700',
  CONSENT_GRANTED:          'bg-emerald-50 text-emerald-700',
  CONSENT_REVOKED:          'bg-rose-50 text-rose-700',
  TRANSFER_REQUESTED:       'bg-violet-50 text-violet-700',
  TRANSFER_ACCEPTED:        'bg-emerald-50 text-emerald-700',
  TRANSFER_REJECTED:        'bg-rose-50 text-rose-700',
  TRANSFER_CANCELLED:       'bg-slate-50 text-slate-600',
  S1_BLOCK:                 'bg-red-50 text-red-700',
  DEFAULT:                  'bg-slate-50 text-slate-600',
};

const OUTCOME_BADGE: Record<string, string> = {
  success: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  failure: 'bg-rose-100 text-rose-700 border-rose-200',
  blocked: 'bg-amber-100 text-amber-700 border-amber-200',
  denied:  'bg-red-100 text-red-700 border-red-200',
};

const EVENT_TYPE_OPTIONS = [
  'LOGIN', 'LOGOUT', 'PATIENT_VIEWED', 'RECORD_VIEWED', 'RECORD_UPLOADED',
  'CLAIM_ACCEPTED', 'CLAIM_REJECTED', 'CONFLICT_DETECTED', 'CONFLICT_ACKNOWLEDGED',
  'GAP_DETECTED', 'CONSENT_GRANTED', 'CONSENT_REVOKED',
  'TRANSFER_REQUESTED', 'TRANSFER_ACCEPTED', 'TRANSFER_REJECTED', 'TRANSFER_CANCELLED',
  'SUMMARY_GENERATED', 'S1_BLOCK', 'EXTRACTION_RUN',
];

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatEventType(et: string): string {
  return et.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDateTime(isoStr: string): string {
  return new Date(isoStr).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function exportCSV(rows: AuditLogItem[], filename: string) {
  const headers = ['ID', 'Timestamp', 'Event Type', 'User ID', 'Patient ID', 'Org', 'Hospital', 'Outcome', 'Details'];
  const csvRows = rows.map((r) => [
    r.id,
    r.at,
    r.event_type || r.action,
    r.user_id,
    r.patient_id || '',
    r.org_id,
    r.hospital_id || '',
    r.outcome || '',
    r.details ? JSON.stringify(r.details) : '',
  ].map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','));

  const csv = [headers.join(','), ...csvRows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Row component ───────────────────────────────────────────────────────────

function AuditTableRow({ log }: { log: AuditLogItem }) {
  const [expanded, setExpanded] = useState(false);
  const eventType = log.event_type || log.action;
  const Icon = EVENT_ICONS[eventType] || ShieldAlert;
  const colorClass = EVENT_COLORS[eventType] || EVENT_COLORS.DEFAULT;
  const outcomeClass = OUTCOME_BADGE[log.outcome || 'success'] || 'bg-slate-100 text-slate-600';
  const hasDetails = log.details && Object.keys(log.details).length > 0;

  return (
    <>
      <tr className="hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0">
        {/* Timestamp */}
        <td className="py-2.5 px-3 text-[11px] font-mono text-slate-500 whitespace-nowrap" title={log.at}>
          {formatDateTime(log.at)}
        </td>

        {/* Event type */}
        <td className="py-2.5 px-3">
          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold ${colorClass}`}>
            <Icon className="w-3 h-3 flex-shrink-0" />
            {formatEventType(eventType)}
          </span>
        </td>

        {/* User */}
        <td className="py-2.5 px-3 text-[11px] font-mono text-slate-700">
          {log.user_id}
        </td>

        {/* Patient */}
        <td className="py-2.5 px-3 text-[11px] font-mono text-slate-500">
          {log.patient_id || <span className="text-slate-300">—</span>}
        </td>

        {/* Org / Hospital */}
        <td className="py-2.5 px-3 text-[11px] font-mono text-slate-500">
          {log.hospital_id || log.org_id}
        </td>

        {/* Outcome */}
        <td className="py-2.5 px-3">
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border uppercase ${outcomeClass}`}>
            {log.outcome || 'success'}
          </span>
        </td>

        {/* Expand */}
        <td className="py-2.5 px-3 text-center">
          {hasDetails ? (
            <button
              onClick={() => setExpanded(!expanded)}
              className="w-5 h-5 rounded flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors mx-auto"
            >
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          ) : <span className="text-slate-200">—</span>}
        </td>
      </tr>

      {expanded && hasDetails && (
        <tr className="bg-slate-50 border-b border-slate-100">
          <td colSpan={7} className="px-4 py-3">
            <div className="flex items-start gap-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mt-1 shrink-0">Details</span>
              <pre className="text-[10px] font-mono text-slate-600 bg-white border border-slate-200 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all flex-1">
                {JSON.stringify(log.details, null, 2)}
              </pre>
            </div>
            <div className="mt-1 flex items-center gap-4 text-[10px] font-mono text-slate-400">
              <span>id: {log.id}</span>
              <span>org: {log.org_id}</span>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export const AuditPage: React.FC = () => {
  // Filters
  const [patientId,  setPatientId]  = useState('');
  const [userId,     setUserId]     = useState('');
  const [eventType,  setEventType]  = useState('');
  const [outcome,    setOutcome]    = useState('');
  const [dateFrom,   setDateFrom]   = useState('');
  const [dateTo,     setDateTo]     = useState('');
  const [limit,      setLimit]      = useState(100);
  const [showFilters, setShowFilters] = useState(false);

  // Data
  const [logs,      setLogs]      = useState<AuditLogItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error,     setError]     = useState<string | null>(null);
  const [fetched,   setFetched]   = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await auditApi.list({
        limit,
        patient_id: patientId || undefined,
        user_id:    userId    || undefined,
        event_type: eventType || undefined,
        outcome:    outcome   || undefined,
        date_from:  dateFrom  || undefined,
        date_to:    dateTo    || undefined,
      });
      setLogs(data);
      setFetched(true);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError('Unable to load audit logs.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [patientId, userId, eventType, outcome, dateFrom, dateTo, limit]);

  // Auto-load on mount
  useEffect(() => { load(); }, []);  // eslint-disable-line

  const handleExportCSV = () => {
    const ts = new Date().toISOString().replace(/[:T.]/g, '-').slice(0, 19);
    exportCSV(logs, `audit-export-${ts}.csv`);
  };

  // Summary counts
  const successCount = logs.filter((l) => (l.outcome || 'success') === 'success').length;
  const failureCount = logs.filter((l) => l.outcome === 'failure').length;
  const blockedCount = logs.filter((l) => l.outcome === 'blocked' || l.outcome === 'denied').length;

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-[#F08080]" />
            Platform Audit Log
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Immutable security &amp; access governance log. Append-only. Never modified.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            id="audit-filter-toggle"
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border transition-colors ${
              showFilters
                ? 'bg-[#FFF0ED] text-[#A83232] border-[#F8AD9D]'
                : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
            }`}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            Filters
          </button>
          <button
            id="audit-refresh-btn"
            onClick={load}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-slate-600 bg-white border border-slate-200 hover:border-slate-300 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          {logs.length > 0 && (
            <button
              id="audit-export-csv-btn"
              onClick={handleExportCSV}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-white bg-[#F08080] hover:bg-[#E07070] rounded-lg transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Export CSV
            </button>
          )}
        </div>
      </div>

      {/* Summary stats */}
      {fetched && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Total Events', value: logs.length, color: 'text-slate-900', bg: 'bg-slate-50' },
            { label: 'Success',      value: successCount, color: 'text-emerald-700', bg: 'bg-emerald-50' },
            { label: 'Failure',      value: failureCount, color: 'text-rose-700',    bg: 'bg-rose-50' },
            { label: 'Blocked/Denied', value: blockedCount, color: 'text-amber-700', bg: 'bg-amber-50' },
          ].map((stat) => (
            <div key={stat.label} className={`${stat.bg} rounded-xl border border-slate-200 px-4 py-3 flex items-center justify-between`}>
              <span className="text-xs text-slate-500 font-medium">{stat.label}</span>
              <span className={`text-lg font-bold font-mono ${stat.color}`}>{stat.value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Filter panel */}
      {showFilters && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-2xs">
          <div className="flex items-center gap-2 mb-4">
            <Filter className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-bold text-slate-700">Filter Events</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Patient ID */}
            <div>
              <label htmlFor="audit-filter-patient" className="block text-xs font-semibold text-slate-600 mb-1">Patient ID</label>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                <input
                  id="audit-filter-patient"
                  type="text"
                  value={patientId}
                  onChange={(e) => setPatientId(e.target.value)}
                  placeholder="e.g. P-101"
                  className="w-full pl-8 pr-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#F08080]/30"
                />
              </div>
            </div>

            {/* User ID */}
            <div>
              <label htmlFor="audit-filter-user" className="block text-xs font-semibold text-slate-600 mb-1">User ID</label>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                <input
                  id="audit-filter-user"
                  type="text"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="User ID"
                  className="w-full pl-8 pr-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#F08080]/30"
                />
              </div>
            </div>

            {/* Event type */}
            <div>
              <label htmlFor="audit-filter-event" className="block text-xs font-semibold text-slate-600 mb-1">Event Type</label>
              <select
                id="audit-filter-event"
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#F08080]/30 bg-white"
              >
                <option value="">All Events</option>
                {EVENT_TYPE_OPTIONS.map((o) => (
                  <option key={o} value={o}>{formatEventType(o)}</option>
                ))}
              </select>
            </div>

            {/* Outcome */}
            <div>
              <label htmlFor="audit-filter-outcome" className="block text-xs font-semibold text-slate-600 mb-1">Outcome</label>
              <select
                id="audit-filter-outcome"
                value={outcome}
                onChange={(e) => setOutcome(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#F08080]/30 bg-white"
              >
                <option value="">All Outcomes</option>
                <option value="success">Success</option>
                <option value="failure">Failure</option>
                <option value="blocked">Blocked</option>
                <option value="denied">Denied</option>
              </select>
            </div>

            {/* Date from */}
            <div>
              <label htmlFor="audit-filter-from" className="block text-xs font-semibold text-slate-600 mb-1">From Date</label>
              <input
                id="audit-filter-from"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#F08080]/30"
              />
            </div>

            {/* Date to */}
            <div>
              <label htmlFor="audit-filter-to" className="block text-xs font-semibold text-slate-600 mb-1">To Date</label>
              <input
                id="audit-filter-to"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#F08080]/30"
              />
            </div>

            {/* Limit */}
            <div>
              <label htmlFor="audit-filter-limit" className="block text-xs font-semibold text-slate-600 mb-1">Max Results</label>
              <select
                id="audit-filter-limit"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#F08080]/30 bg-white"
              >
                <option value={50}>50 rows</option>
                <option value={100}>100 rows</option>
                <option value={200}>200 rows</option>
                <option value={500}>500 rows</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3 mt-4 pt-4 border-t border-slate-100">
            <button
              id="audit-apply-filters-btn"
              onClick={load}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-[#F08080] hover:bg-[#E07070] rounded-lg transition-colors disabled:opacity-50"
            >
              {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Filter className="w-3.5 h-3.5" />}
              Apply Filters
            </button>
            <button
              id="audit-clear-filters-btn"
              onClick={() => {
                setPatientId(''); setUserId(''); setEventType('');
                setOutcome(''); setDateFrom(''); setDateTo(''); setLimit(100);
              }}
              className="px-4 py-2 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Audit table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-5 h-5 animate-spin text-[#F08080]" />
            <span className="ml-2 text-sm text-slate-500">Loading audit logs…</span>
          </div>
        )}

        {!isLoading && error && (
          <div className="flex items-center gap-3 m-5 p-4 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!isLoading && !error && logs.length === 0 && fetched && (
          <div className="text-center py-16">
            <ShieldAlert className="w-12 h-12 text-slate-200 mx-auto mb-3" />
            <p className="text-sm font-medium text-slate-500">No audit events match your filters.</p>
            <p className="text-xs text-slate-400 mt-1">Try adjusting the date range or clearing filters.</p>
          </div>
        )}

        {!isLoading && !error && logs.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  {['Timestamp', 'Event', 'User', 'Patient', 'Facility', 'Outcome', ''].map((h) => (
                    <th key={h} className="py-2.5 px-3 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <AuditTableRow key={log.id} log={log} />
                ))}
              </tbody>
            </table>
            <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between bg-slate-50">
              <span className="text-[11px] text-slate-500 font-mono">
                Showing {logs.length} events{logs.length === limit ? ` (capped at ${limit})` : ''}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-400">Append-only. All entries are forensically immutable.</span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700 border border-emerald-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  LIVE
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
