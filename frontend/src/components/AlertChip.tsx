import React from 'react';
import { AlertTriangle, AlertCircle, Clock, CheckCircle2 } from 'lucide-react';

export type AlertType = 'conflict' | 'missing' | 'overdue' | 'neutral' | 'verified';

interface AlertChipProps {
  type: AlertType;
  label: string;
  count?: number;
  className?: string;
}

export const AlertChip: React.FC<AlertChipProps> = ({ type, label, count, className = '' }) => {
  let style = 'bg-slate-100 text-slate-700 border-slate-300';
  let Icon = AlertCircle;

  switch (type) {
    case 'conflict':
      // Peach Sorbet deep coral / red alert
      style = 'bg-[#FFF0ED] text-[#822828] border-[#F8AD9D] font-bold shadow-peach-xs';
      Icon = AlertTriangle;
      break;
    case 'missing':
      style = 'bg-amber-50 text-amber-900 border-amber-300 font-semibold';
      Icon = AlertCircle;
      break;
    case 'overdue':
      style = 'bg-rose-50 text-rose-800 border-rose-300 font-bold';
      Icon = Clock;
      break;
    case 'verified':
      style = 'bg-emerald-50 text-emerald-800 border-emerald-300 font-semibold';
      Icon = CheckCircle2;
      break;
    default:
      style = 'bg-slate-100 text-slate-700 border-slate-200 font-medium';
      Icon = AlertCircle;
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs border ${style} ${className}`}
    >
      <Icon className="w-3.5 h-3.5 flex-shrink-0" />
      <span>{label}</span>
      {typeof count === 'number' && (
        <span className="ml-0.5 px-1.5 py-0.2 rounded-full bg-white/70 text-xs font-bold">
          {count}
        </span>
      )}
    </span>
  );
};
