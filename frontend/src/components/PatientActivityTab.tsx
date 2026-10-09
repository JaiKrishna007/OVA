import React, { useState, useEffect, useCallback } from 'react';
import { auditApi, ApiClientError } from '../services/api';
import type { AuditLogItem } from '../types/api';
import {
  ShieldAlert,
  Loader2,
  AlertCircle,
  RefreshCw,
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
  ChevronDown,
  ChevronUp,
  Filter,
} from 'lucide-react';

interface PatientActivityTabProps {
  patientId: string;
}

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
  'All',
  'PATIENT_VIEWED',
  'RECORD_VIEWED',
  'RECORD_UPLOADED',
  'CLAIM_ACCEPTED',
  'CLAIM_REJECTED',
  'CONFLICT_DETECTED',
  'CONFLICT_ACKNOWLEDGED',
  'GAP_DETECTED',
  'CONSENT_GRANTED',
  'CONSENT_REVOKED',
  'TRANSFER_REQUESTED',
  'TRANSFER_ACCEPTED',
  'TRANSFER_REJECTED',
  'TRANSFER_CANCELLED',
  'SUMMARY_GENERATED',
  'S1_BLOCK',
];

function formatRelativeTime(isoStr: string): string {
  const date = new Date(isoStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1)  return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24)   return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7)     return `${days}d ago`;
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatEventType(et: string): string {
  return et
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function AuditRow({ log }: { log: AuditLogItem }) {
  const [expanded, setExpanded] = useState(false);
  const eventType = log.event_type || log.action;
  const Icon = EVENT_ICONS[eventType] || ShieldAlert;
  const colorClass = EVENT_COLORS[eventType] || EVENT_COLORS.DEFAULT;
  const outcomeClass = OUTCOME_BADGE[log.outcome || 'success'] || 'bg-slate-100 text-slate-600';
  const hasDetails = log.details && Object.keys(log.details).length > 0;

  return (
    <div className="group relative pl-8 pb-4">
      {/* Connector line */}
      <div className="absolute left-3.5 top-7 bottom-0 w-px bg-slate-100 group-last:hidden" />

      {/* Icon dot */}
      <div className={`absolute left-0 top-1 w-7 h-7 rounded-full flex items-center justify-center text-xs ${colorClass} shadow-2xs border border-white`}>
        <Icon className="w-3.5 h-3.5" />
      </div>

      <div className="bg-white border border-slate-100 rounded-lg p-3 shadow-2xs hover:border-slate-200 transition-colors">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${colorClass} border-current/20`}>
                {formatEventType(eventType)}
              </span>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${outcomeClass}`}>
                {(log.outcome || 'success').toUpperCase()}
              </span>
            </div>
            <div className="mt-1 flex items-center gap-3 text-[11px] text-slate-500 flex-wrap">
              <span className="font-mono">by <strong className="text-slate-700">{log.user_id}</strong></span>
              {log.hospital_id && (
                <span className="font-mono text-slate-400">{log.hospital_id}</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-[11px] text-slate-400 whitespace-nowrap" title={new Date(log.at).toISOString()}>
              {formatRelativeTime(log.at)}
            </span>
            {hasDetails && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="w-5 h-5 rounded flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                title={expanded ? 'Hide details' : 'Show details'}
              >
                {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>
        </div>

        {expanded && hasDetails && (
          <div className="mt-2 pt-2 border-t border-slate-100">
            <pre className="text-[10px] font-mono text-slate-600 bg-slate-50 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
              {JSON.stringify(log.details, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

export const PatientActivityTab: React.FC<PatientActivityTabProps> = ({ patientId }) => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [eventTypeFilter, setEventTypeFilter] = useState('All');

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await auditApi.listForPatient(patientId, {
        limit: 200,
        event_type: eventTypeFilter === 'All' ? undefined : eventTypeFilter,
      });
      setLogs(data);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError('Unable to load activity feed.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [patientId, eventTypeFilter]);

  useEffect(() => { load(); }, [load]);

  // Group by date
  const grouped: { label: string; items: AuditLogItem[] }[] = [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const dateMap = new Map<string, AuditLogItem[]>();
  for (const log of logs) {
    const d = new Date(log.at);
    d.setHours(0, 0, 0, 0);
    let label: string;
    if (d.getTime() === today.getTime()) {
      label = 'Today';
    } else if (d.getTime() === yesterday.getTime()) {
      label = 'Yesterday';
    } else {
      label = d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }
    if (!dateMap.has(label)) dateMap.set(label, []);
    dateMap.get(label)!.push(log);
  }
  dateMap.forEach((items, label) => grouped.push({ label, items }));

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-2xs">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-[#F08080]" />
          <h3 className="text-sm font-bold text-slate-900">Patient Activity Feed</h3>
          {!isLoading && (
            <span className="px-2 py-0.5 rounded-full bg-slate-100 text-[11px] font-mono text-slate-600">
              {logs.length} events
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Event type filter */}
          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              id="activity-event-type-filter"
              value={eventTypeFilter}
              onChange={(e) => setEventTypeFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#F08080]/30"
            >
              {EVENT_TYPE_OPTIONS.map((o) => (
                <option key={o} value={o}>{o === 'All' ? 'All Events' : formatEventType(o)}</option>
              ))}
            </select>
          </div>
          <button
            id="activity-refresh-btn"
            onClick={load}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            title="Refresh activity"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="p-5">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-5 h-5 animate-spin text-[#F08080]" />
            <span className="ml-2 text-sm text-slate-500">Loading activity…</span>
          </div>
        ) : error ? (
          <div className="flex items-center gap-3 p-4 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-12">
            <ShieldAlert className="w-10 h-10 text-slate-200 mx-auto mb-3" />
            <p className="text-sm text-slate-500">No activity recorded for this patient yet.</p>
            {eventTypeFilter !== 'All' && (
              <p className="text-xs text-slate-400 mt-1">Try changing the event type filter.</p>
            )}
          </div>
        ) : (
          <div className="space-y-5">
            {grouped.map(({ label, items }) => (
              <div key={label}>
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</span>
                  <div className="flex-1 h-px bg-slate-100" />
                  <span className="text-[10px] font-mono text-slate-400">{items.length} events</span>
                </div>
                <div>
                  {items.map((log) => (
                    <AuditRow key={log.id} log={log} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
