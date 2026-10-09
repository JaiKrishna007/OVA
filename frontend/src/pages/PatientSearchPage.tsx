import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { patientsApi, ApiClientError } from '../services/api';
import type { PatientListItem } from '../types/api';
import { AlertChip } from '../components/AlertChip';
import { CycleBadge } from '../components/CycleBadge';
import {
  Search,
  Phone,
  ArrowRight,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Activity,
} from 'lucide-react';

export const PatientSearchPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [patients, setPatients] = useState<PatientListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusCode, setStatusCode] = useState<number | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Debounce search input by 300ms
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => clearTimeout(handler);
  }, [query]);

  // Global keyboard shortcut '/' to focus search input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement !== searchInputRef.current) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const fetchPatients = async (searchTerm: string) => {
    setIsLoading(true);
    setError(null);
    setStatusCode(null);
    try {
      const data = await patientsApi.search(searchTerm);
      setPatients(data);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setStatusCode(err.status);
        if (err.status === 403) {
          setError(
            'Access Restricted (403): You do not have permission to view this patient directory. Check your clinical assignment.'
          );
        } else {
          setError(err.message || 'Error retrieving patient directory.');
        }
      } else {
        setError('Network error: Unable to reach the clinical EMR backend.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPatients(debouncedQuery);
  }, [debouncedQuery]);

  const computeAge = (dobString: string): number => {
    if (!dobString) return 0;
    const dob = new Date(dobString);
    const asOf = new Date('2025-03-14'); // Clinical Reference AS_OF_DATE
    let age = asOf.getFullYear() - dob.getFullYear();
    const m = asOf.getMonth() - dob.getMonth();
    if (m < 0 || (m === 0 && asOf.getDate() < dob.getDate())) {
      age--;
    }
    return Math.max(0, age);
  };

  const getDiagnosisText = (diag: PatientListItem['diagnosis']): string => {
    if (!diag) return 'Fertility Evaluation';
    if (typeof diag === 'string') return diag;
    if (typeof diag === 'object' && 'primary' in diag) {
      return (diag as { primary?: string; secondary?: string }).primary || 'Fertility Evaluation';
    }
    return 'Fertility Evaluation';
  };

  const extractCycleType = (stageText: string): string => {
    const s = (stageText || '').toUpperCase();
    if (s.includes('PREGNAN') || s.includes('BETA-HCG')) return 'pregnancy';
    if (s.includes('FET') || s.includes('FROZEN')) return 'FET';
    if (s.includes('IVF') || s.includes('ICSI') || s.includes('STIMULATION')) return 'IVF/ICSI';
    if (s.includes('IUI')) return 'IUI';
    if (s.includes('OI') || s.includes('OVULATION')) return 'OI';
    return 'IVF';
  };

  // Known clinical cues for badge indicators
  const getPatientAlerts = (patientId: string) => {
    switch (patientId) {
      case 'P-101':
        return [
          { type: 'conflict' as const, label: 'OPU Oocyte Mismatch (8 vs 9)' },
          { type: 'missing' as const, label: 'Missing Semen Analysis' },
          { type: 'overdue' as const, label: 'Overdue TSH' },
        ];
      case 'P-102':
        return [
          { type: 'neutral' as const, label: 'OHSS History' },
          { type: 'verified' as const, label: 'Ongoing Clinical Pregnancy' },
        ];
      case 'P-103':
        return [
          { type: 'conflict' as const, label: 'Duplicate Lab Mismatch' },
          { type: 'overdue' as const, label: 'Pending Beta-hCG' },
        ];
      case 'P-104':
        return [
          { type: 'neutral' as const, label: 'Miscarriage Note' },
          { type: 'verified' as const, label: 'FET Planned' },
        ];
      case 'P-105':
        return [
          { type: 'missing' as const, label: 'Missing HSG Report' },
          { type: 'conflict' as const, label: 'Abnormal Semen Params' },
        ];
      default:
        return [];
    }
  };

  return (
    <div className="space-y-6">
      {/* Search Header */}
      <div className="bg-white/95 backdrop-blur-md rounded-3xl border border-[#FBC4AB]/50 p-6 sm:p-7 shadow-peach-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
              Clinical Patient Directory
            </h1>
            <p className="text-xs text-slate-500 mt-0.5 font-medium">
              Search by patient name, ID (e.g. P-101), or phone number
            </p>
          </div>
          <div className="text-xs font-bold text-[#822828] bg-[#FFF9F7] px-3.5 py-1.5 rounded-full border border-[#F8AD9D]/60 font-mono shadow-peach-xs self-start sm:self-auto">
            {patients.length} patient{patients.length === 1 ? '' : 's'} in assigned scope
          </div>
        </div>

        {/* Search Bar with Keyboard indicator */}
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
            <Search className="w-5 h-5 text-[#F08080]" />
          </div>
          <input
            ref={searchInputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search patients (e.g. 'Priya', 'P-101', 'Anitha'). Press '/' to focus..."
            className="block w-full pl-11 pr-20 py-3.5 text-sm border border-slate-200/90 rounded-2xl bg-white text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-[#F8AD9D]/50 focus:border-[#F08080] transition-all shadow-peach-xs"
          />
          <div className="absolute inset-y-0 right-0 pr-3.5 flex items-center gap-1.5 pointer-events-none text-xs text-slate-400">
            <kbd className="px-2 py-0.5 bg-[#FFF0ED] text-[#822828] rounded-md font-mono text-[11px] font-bold border border-[#F8AD9D]/40 shadow-peach-xs">
              /
            </kbd>
          </div>
        </div>
      </div>

      {/* Error Banner with 403 Handling */}
      {error && (
        <div
          role="alert"
          className="rounded-xl bg-rose-50 border border-rose-200 p-5 text-rose-900 flex items-start gap-4 shadow-2xs"
        >
          <AlertTriangle className="w-6 h-6 text-rose-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h2 className="text-sm font-bold mb-1">
              {statusCode === 403 ? 'Access Restricted (403 Forbidden)' : 'Clinical Query Error'}
            </h2>
            <p className="text-sm text-rose-700 leading-relaxed mb-3">{error}</p>
            <button
              onClick={() => fetchPatients(debouncedQuery)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-rose-300 text-rose-700 text-xs font-semibold rounded-lg hover:bg-rose-50 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Search</span>
            </button>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="space-y-4">
          <div className="flex items-center justify-center py-12 gap-3 text-slate-500">
            <Loader2 className="w-6 h-6 text-[#F08080] animate-spin" />
            <span className="text-sm font-medium">Filtering clinical records...</span>
          </div>
          {/* Skeleton Cards */}
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs animate-pulse space-y-3"
            >
              <div className="h-5 bg-slate-200 rounded w-1/4"></div>
              <div className="h-4 bg-slate-100 rounded w-1/2"></div>
              <div className="h-6 bg-slate-100 rounded w-1/3"></div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && patients.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-2xs">
          <div className="w-12 h-12 rounded-full bg-[#FFF0ED] text-[#F08080] mx-auto flex items-center justify-center mb-4">
            <Search className="w-6 h-6" />
          </div>
          <h2 className="text-base font-bold text-slate-900 mb-1">No Matching Patients Found</h2>
          <p className="text-sm text-slate-500 max-w-sm mx-auto mb-4">
            No patient records matched <strong className="text-slate-800">"{query}"</strong> within your assigned doctor scope.
          </p>
          {query && (
            <button
              onClick={() => setQuery('')}
              className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
            >
              Clear Search Query
            </button>
          )}
        </div>
      )}

      {/* Results Grid */}
      {!isLoading && !error && patients.length > 0 && (
        <div className="space-y-3">
          {patients.map((p) => {
            const age = computeAge(p.dob);
            const cycleType = extractCycleType(p.current_stage);
            const alerts = getPatientAlerts(p.id);

            return (
              <div
                key={p.id}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/patients/${p.id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate(`/patients/${p.id}`);
                  }
                }}
                className="group bg-white hover:bg-[#FFFDFB] rounded-2xl border border-slate-200/90 hover:border-[#F8AD9D] p-5 shadow-2xs hover:shadow-peach-sm transition-all card-interactive cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-[#F08080]"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  {/* Left: Patient Identity */}
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <h2 className="text-base font-bold text-slate-900 group-hover:text-[#F08080] transition-colors">
                        {p.name}
                      </h2>
                      <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded-md bg-[#FFF9F7] text-[#822828] border border-[#FBC4AB]/60">
                        {p.id}
                      </span>
                      <span className="text-xs text-slate-500 font-medium">
                        {age} yrs &bull; {p.sex.charAt(0).toUpperCase() + p.sex.slice(1)}
                      </span>
                      {p.blood_group && (
                        <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
                          {p.blood_group}
                        </span>
                      )}
                      <CycleBadge type={cycleType} size="sm" />
                    </div>

                    {/* Diagnosis & Stage */}
                    <div className="text-xs text-slate-600 flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-slate-700">
                        {getDiagnosisText(p.diagnosis)}
                      </span>
                      <span className="text-slate-300">&bull;</span>
                      <span className="inline-flex items-center gap-1 text-slate-600">
                        <Activity className="w-3.5 h-3.5 text-[#F08080]" />
                        <strong className="font-bold text-slate-800">Current Stage:</strong>{' '}
                        {p.current_stage}
                      </span>
                    </div>

                    {/* Alert Chips */}
                    {alerts.length > 0 && (
                      <div className="flex items-center gap-2 pt-1 flex-wrap">
                        {alerts.map((alert, idx) => (
                          <AlertChip
                            key={idx}
                            type={alert.type}
                            label={alert.label}
                          />
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Right: Phone, Provenance & Navigation CTA */}
                  <div className="flex md:flex-col items-center md:items-end justify-between md:justify-center gap-2.5 border-t md:border-t-0 pt-3 md:pt-0 border-slate-100">
                    <div className="text-xs text-slate-500 font-mono flex items-center gap-1.5 font-medium">
                      <Phone className="w-3.5 h-3.5 text-[#F08080]" />
                      <span>{p.phone_masked || 'Phone not on file'}</span>
                    </div>

                    <div className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#FFF9F7] group-hover:bg-gradient-to-r group-hover:from-[#F08080] group-hover:to-[#F4978E] border border-[#FBC4AB]/60 group-hover:border-transparent text-xs font-bold text-[#822828] group-hover:text-white transition-all shadow-peach-xs btn-interactive">
                      <span>View Chart</span>
                      <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
