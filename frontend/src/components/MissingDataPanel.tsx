import React from 'react';
import { FileQuestion } from 'lucide-react';

interface MissingItem {
  item: string;
  reason: string;
  rule_id: string;
  source_refs?: string[];
}

interface MissingDataPanelProps {
  missingItems: MissingItem[];
}

export const MissingDataPanel: React.FC<MissingDataPanelProps> = ({ missingItems }) => {
  if (!missingItems || missingItems.length === 0) return null;

  return (
    <div className="bg-gradient-to-br from-amber-50/80 to-[#FFF9F7] rounded-3xl border border-amber-300/80 p-5 sm:p-6 shadow-peach-xs space-y-4">
      {/* Panel Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-10 h-10 rounded-2xl bg-amber-500 text-white flex items-center justify-center flex-shrink-0 shadow-xs">
            <FileQuestion className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
              <span>Not Documented in Records</span>
              <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-white text-amber-900 border border-amber-300 shadow-2xs">
                {missingItems.length} Gaps Identified
              </span>
            </h3>
            <p className="text-xs text-slate-600 mt-0.5 font-medium">
              Safety Rule S3: Missing data is explicitly displayed as "Not documented in records". The system never guesses or fills gaps.
            </p>
          </div>
        </div>
      </div>

      {/* Missing Items List */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {missingItems.map((item, idx) => (
          <div
            key={idx}
            className="bg-white rounded-2xl border border-amber-200/80 p-4.5 shadow-2xs hover:shadow-peach-xs card-interactive flex flex-col justify-between space-y-2"
          >
            <div>
              <div className="flex items-center justify-between gap-2 mb-1">
                <strong className="text-sm font-bold text-slate-900">
                  {item.item}
                </strong>
                <span className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-amber-50 text-amber-800 border border-amber-200">
                  {item.rule_id}
                </span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                {item.reason}
              </p>
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-amber-800 font-medium">
              <span className="italic">Status: Not documented in records</span>
              <span className="text-slate-400 font-mono text-[10px]">Rule-validated</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
