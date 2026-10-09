import React from 'react';

export type CycleCategory = 'OI' | 'IUI' | 'IVF' | 'ICSI' | 'FET' | 'pregnancy' | string;

interface CycleBadgeProps {
  type: CycleCategory;
  className?: string;
  size?: 'sm' | 'md';
}

export const CycleBadge: React.FC<CycleBadgeProps> = ({ type, className = '', size = 'md' }) => {
  const normType = (type || '').toUpperCase().trim();

  let colorClasses = 'bg-slate-100 text-slate-700 border-slate-200';

  if (normType === 'OI' || normType.includes('OVULATION')) {
    colorClasses = 'bg-emerald-50 text-emerald-800 border-emerald-300';
  } else if (normType === 'IUI') {
    colorClasses = 'bg-sky-50 text-sky-800 border-sky-300';
  } else if (normType === 'IVF' || normType === 'ICSI' || normType.includes('IVF') || normType.includes('ICSI')) {
    colorClasses = 'bg-indigo-50 text-indigo-800 border-indigo-300';
  } else if (normType === 'FET' || normType.includes('FROZEN')) {
    colorClasses = 'bg-amber-50 text-amber-900 border-amber-300';
  } else if (
    normType === 'PREGNANCY' ||
    normType.includes('PREGNAN') ||
    normType.includes('MISCARRIAGE')
  ) {
    // Peach Sorbet primary palette theme
    colorClasses = 'bg-[#FFF0ED] text-[#822828] border-[#F8AD9D] font-bold shadow-peach-xs';
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs font-semibold' : 'px-3 py-1 text-xs font-bold';

  return (
    <span
      className={`inline-flex items-center rounded-full border transition-colors ${sizeClasses} ${colorClasses} ${className}`}
    >
      {type}
    </span>
  );
};
