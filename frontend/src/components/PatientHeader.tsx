import React, { useState } from 'react';
import type { PatientDetailResponse } from '../types/api';
import {
  Heart,
  Droplet,
  Scale,
  AlertTriangle,
  AlertCircle,
  Clock,
  Info,
  Building2,
} from 'lucide-react';

interface AlertItem {
  id: string;
  type: 'conflict' | 'missing' | 'overdue' | 'warning' | 'info';
  title: string;
  text: string;
  sourceRefs: string[];
}

interface PatientHeaderProps {
  patient: PatientDetailResponse;
  alerts?: AlertItem[];
}

export const PatientHeader: React.FC<PatientHeaderProps> = ({ patient, alerts = [] }) => {
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null);

  // Compute age from dob relative to 2025-03-14 (AS_OF_DATE)
  const computeAge = (dobString: string): number => {
    if (!dobString) return 0;
    const dob = new Date(dobString);
    const asOf = new Date('2025-03-14');
    let age = asOf.getFullYear() - dob.getFullYear();
    const m = asOf.getMonth() - dob.getMonth();
    if (m < 0 || (m === 0 && asOf.getDate() < dob.getDate())) {
      age--;
    }
    return Math.max(0, age);
  };

  const getDiagnosisText = (diag: PatientDetailResponse['diagnosis']): { primary: string; secondary?: string } => {
    if (!diag) return { primary: 'Fertility Evaluation' };
    if (typeof diag === 'string') return { primary: diag };
    if (typeof diag === 'object' && 'primary' in diag) {
      const d = diag as { primary?: string; secondary?: string };
      return {
        primary: d.primary || 'Fertility Evaluation',
        secondary: d.secondary,
      };
    }
    return { primary: 'Fertility Evaluation' };
  };

  const diag = getDiagnosisText(patient.diagnosis);
  const age = computeAge(patient.dob);

  return (
    <div className="bg-white/95 backdrop-blur-md rounded-3xl border border-[#FBC4AB]/50 shadow-peach-xs overflow-hidden">
      {/* Top Main Patient Bar */}
      <div className="p-5 sm:p-7 pb-4 border-b border-[#FBC4AB]/25">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Identity & Current Stage */}
          <div className="space-y-2.5">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
                {patient.name}
              </h1>
              <span className="font-mono text-xs font-bold px-2.5 py-1 rounded-lg bg-[#FFF9F7] text-[#822828] border border-[#FBC4AB]/60 shadow-peach-xs">
                {patient.id}
              </span>
              <span className="text-sm font-bold text-slate-700 bg-slate-100/80 px-3 py-0.5 rounded-full border border-slate-200/80">
                {age} yrs &bull; {patient.sex.charAt(0).toUpperCase() + patient.sex.slice(1)}
              </span>
              <span className="text-xs text-slate-500 font-medium font-mono">
                DOB: {patient.dob}
              </span>
            </div>

            {/* Current Stage Highlight */}
            <div className="flex items-center gap-2 flex-wrap">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-[#FFF9F7] to-[#FFEBE5] text-[#822828] border border-[#F8AD9D] text-xs font-bold shadow-peach-xs">
                <span className="w-2 h-2 rounded-full bg-[#F08080] animate-pulse"></span>
                <span>Current Treatment Stage:</span>
                <span className="text-[#822828] font-extrabold">{patient.current_stage}</span>
              </div>
              <span className="text-xs text-slate-400 font-mono">
                As of 2025-03-14
              </span>
            </div>
          </div>

          {/* Org & Clinical Assignment Info */}
          <div className="flex items-center gap-3 self-start lg:self-center">
            <div className="text-right hidden sm:block">
              <div className="text-xs text-slate-500 font-medium">EMR Facility</div>
              <div className="text-xs font-mono font-bold text-slate-800">
                {patient.org_id}
              </div>
            </div>
            <div className="w-11 h-11 rounded-2xl bg-[#FFF9F7] flex items-center justify-center text-[#822828] border border-[#F8AD9D]/50 shadow-peach-xs">
              <Building2 className="w-5 h-5 text-[#F08080]" />
            </div>
          </div>
        </div>
      </div>

      {/* Clinical Baseline Grid */}
      <div className="bg-gradient-to-r from-[#FFF9F7]/60 to-[#FFF5F2]/40 px-5 sm:p-6 py-3.5 border-b border-[#FBC4AB]/25 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-4 text-xs">
        {/* Diagnosis */}
        <div className="col-span-2 sm:col-span-2">
          <span className="text-slate-600 uppercase tracking-wider text-[11px] font-semibold block">
            Clinical Diagnosis
          </span>
          <div className="font-semibold text-slate-800 mt-0.5 truncate" title={diag.primary}>
            {diag.primary}
          </div>
          {diag.secondary && (
            <div className="text-[11px] text-slate-500 truncate" title={diag.secondary}>
              {diag.secondary}
            </div>
          )}
        </div>

        {/* Partner Link */}
        <div>
          <span className="text-slate-600 uppercase tracking-wider text-[11px] font-semibold block">
            Partner
          </span>
          {patient.partner_id ? (
            <div className="inline-flex items-center gap-1 font-mono font-semibold text-[#A83232] hover:underline mt-0.5">
              <Heart className="w-3 h-3 text-[#F08080]" />
              <span>{patient.partner_id}</span>
            </div>
          ) : (
            <span className="text-slate-600 mt-0.5 block italic">None linked</span>
          )}
        </div>

        {/* Blood Group */}
        <div>
          <span className="text-slate-600 uppercase tracking-wider text-[11px] font-semibold block">
            Blood Group
          </span>
          <div className="inline-flex items-center gap-1 font-semibold text-slate-800 mt-0.5">
            <Droplet className="w-3 h-3 text-rose-500" />
            <span>{patient.blood_group || 'Not recorded'}</span>
          </div>
        </div>

        {/* BMI */}
        <div>
          <span className="text-slate-600 uppercase tracking-wider text-[11px] font-semibold block">
            BMI
          </span>
          <div className="inline-flex items-center gap-1 font-semibold text-slate-800 mt-0.5">
            <Scale className="w-3 h-3 text-slate-500" />
            <span>{patient.bmi ? `${patient.bmi} kg/m²` : 'Not recorded'}</span>
          </div>
        </div>
      </div>

      {/* Alert Chips with "Record shows..." wording and source tooltips */}
      {alerts.length > 0 && (
        <div className="p-4 sm:px-6 bg-[#FFFCFA] border-t border-[#FEEBE3]">
          <div className="flex items-center gap-2 mb-2">
            <Info className="w-3.5 h-3.5 text-[#F08080]" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Clinical Findings & Attention Flags ({alerts.length})
            </span>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            {alerts.map((alert) => {
              const isTooltipOpen = activeTooltip === alert.id;
              let chipStyle = 'bg-slate-100 text-slate-800 border-slate-300';
              let Icon = AlertCircle;

              if (alert.type === 'conflict') {
                chipStyle = 'bg-[#FFF0ED] text-[#9E2A2B] border-[#F4978E] font-medium';
                Icon = AlertTriangle;
              } else if (alert.type === 'missing') {
                chipStyle = 'bg-amber-50 text-amber-900 border-amber-300 font-medium';
                Icon = AlertCircle;
              } else if (alert.type === 'overdue') {
                chipStyle = 'bg-rose-50 text-rose-900 border-rose-300 font-medium';
                Icon = Clock;
              }

              return (
                <div
                  key={alert.id}
                  className="relative inline-block"
                  onMouseEnter={() => setActiveTooltip(alert.id)}
                  onMouseLeave={() => setActiveTooltip(null)}
                >
                  <button
                    type="button"
                    onClick={() => setActiveTooltip(isTooltipOpen ? null : alert.id)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs border shadow-2xs hover:shadow-xs transition-all cursor-pointer ${chipStyle}`}
                  >
                    <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>{alert.text}</span>
                    {alert.sourceRefs.length > 0 && (
                      <span className="ml-1 px-1.5 py-0.2 rounded bg-white/80 text-[10px] font-mono font-bold text-slate-700 border border-slate-200">
                        {alert.sourceRefs.length} src
                      </span>
                    )}
                  </button>

                  {/* Hover/Focus Source Tooltip */}
                  {isTooltipOpen && (
                    <div
                      role="tooltip"
                      className="absolute z-50 bottom-full left-0 mb-2 w-72 p-3 bg-slate-900 text-white text-xs rounded-xl shadow-xl pointer-events-none animate-in fade-in duration-150"
                    >
                      <div className="font-bold text-[#FFDAB9] mb-1 flex items-center justify-between">
                        <span>{alert.title}</span>
                        <span className="text-[10px] text-slate-400 font-normal">Source Verification</span>
                      </div>
                      <p className="text-slate-300 text-[11px] leading-relaxed mb-2">
                        {alert.text}
                      </p>
                      {alert.sourceRefs.length > 0 ? (
                        <div className="pt-2 border-t border-slate-800">
                          <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
                            Supporting Records:
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {alert.sourceRefs.map((ref) => (
                              <span
                                key={ref}
                                className="px-1.5 py-0.5 rounded bg-slate-800 font-mono text-[10px] text-emerald-400 border border-slate-700"
                              >
                                {ref}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="text-[10px] text-amber-400 italic">
                          Absence detected via rule checklist: Not documented in records.
                        </div>
                      )}
                      {/* Tooltip beak */}
                      <div className="absolute top-full left-6 -mt-1 border-4 border-transparent border-t-slate-900" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
