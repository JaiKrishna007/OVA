import React from 'react';
import type { Citation } from '../types/api';
import { AlertTriangle, ArrowRightLeft } from 'lucide-react';

interface ConflictItem {
  conflict_type: string;
  field: string;
  items: Array<Record<string, unknown>>;
  source_refs: string[];
}

interface ConflictsPanelProps {
  conflicts: ConflictItem[];
  onSelectCitation?: (citation: Citation) => void;
}

export const ConflictsPanel: React.FC<ConflictsPanelProps> = ({
  conflicts,
  onSelectCitation,
}) => {
  if (!conflicts || conflicts.length === 0) return null;

  return (
    <div className="bg-gradient-to-br from-[#FFF9F7] to-[#FFF0ED] rounded-3xl border border-[#F8AD9D] p-5 sm:p-6 shadow-peach-xs space-y-4">
      {/* Panel Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-10 h-10 rounded-2xl bg-[#F08080] text-white flex items-center justify-center flex-shrink-0 shadow-peach-xs">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
              <span>Active Clinical Contradictions & Conflicts</span>
              <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-[#FFF0ED] text-[#822828] border border-[#F8AD9D] shadow-peach-xs">
                {conflicts.length} Detected
              </span>
            </h3>
            <p className="text-xs text-slate-600 mt-0.5 font-medium">
              Safety Rule S8: Contradictory facts across different records are shown side-by-side. The system never arbitrarily selects one value.
            </p>
          </div>
        </div>
      </div>

      {/* Side-by-Side Comparison Cards */}
      <div className="space-y-4">
        {conflicts.map((conflict: any, cIdx) => {
          const items = conflict.items || [];
          const itemA = items[0] || {};
          const itemB = items[1] || {};

          const valA = conflict.value_a ?? itemA.value ?? itemA.count ?? 'Unknown';
          const valB = conflict.value_b ?? itemB.value ?? itemB.count ?? 'Unknown';

          const srcA = String(conflict.source_id_a || itemA.source_id || conflict.source_refs?.[0] || '');
          const srcB = String(conflict.source_id_b || itemB.source_id || conflict.source_refs?.[1] || '');

          const typeA = String(conflict.source_type_a || itemA.document_type || itemA.source_kind || 'Source Record A').replace(/_/g, ' ');
          const typeB = String(conflict.source_type_b || itemB.document_type || itemB.source_kind || 'Source Record B').replace(/_/g, ' ');

          return (
            <div
              key={cIdx}
              className="bg-white rounded-2xl border border-[#FBC4AB]/60 p-4 sm:p-5 shadow-peach-xs card-interactive space-y-3"
            >
              <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
                <span className="font-bold text-slate-900 text-xs uppercase tracking-wider flex items-center gap-1.5">
                  <ArrowRightLeft className="w-3.5 h-3.5 text-[#F08080]" />
                  <span>{(conflict.field || conflict.description || '').replace(/_/g, ' ')}</span>
                </span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                  {conflict.conflict_type || conflict.conflict_id}
                </span>
              </div>

              {/* Side-by-side grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Side A */}
                <div className="bg-[#FFFDFB] rounded-lg border border-slate-200 p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-600">
                    <span className="font-semibold uppercase tracking-wider text-[11px] text-slate-700">{typeA}</span>
                    <span className="font-mono text-slate-400">{String(itemA.date || '')}</span>
                  </div>

                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-[#A83232] font-mono">
                      {String(valA)}
                    </span>
                    <span className="text-xs text-slate-600">
                      {itemA.unit ? String(itemA.unit) : 'oocytes reported'}
                    </span>
                  </div>

                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                    <span className="text-slate-500 font-mono text-[11px]">
                      Origin: {String(itemA.origin || itemA.origin_org || 'ORG-Y')}
                    </span>
                    {srcA && (
                      <button
                        type="button"
                        onClick={() =>
                          onSelectCitation?.({
                            source_id: srcA,
                            type: typeA,
                            origin: String(itemA.origin || 'ORG-Y'),
                            field_path: conflict.field_path || conflict.field,
                            matching_text: String(valA),
                          })
                        }
                        className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-white hover:bg-slate-50 text-[#A83232] border border-[#F8AD9D] transition-colors"
                      >
                        {srcA}
                      </button>
                    )}
                  </div>
                </div>

                {/* Side B */}
                <div className="bg-[#FFFDFB] rounded-lg border border-slate-200 p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-600">
                    <span className="font-semibold uppercase tracking-wider text-[11px] text-slate-700">{typeB}</span>
                    <span className="font-mono text-slate-400">{String(itemB.date || '')}</span>
                  </div>

                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-amber-800 font-mono">
                      {String(valB)}
                    </span>
                    <span className="text-xs text-slate-600">
                      {itemB.unit ? String(itemB.unit) : 'oocytes reported'}
                    </span>
                  </div>

                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                    <span className="text-slate-500 font-mono text-[11px]">
                      Origin: {String(itemB.origin || itemB.origin_org || 'ORG-Y')}
                    </span>
                    {srcB && (
                      <button
                        type="button"
                        onClick={() =>
                          onSelectCitation?.({
                            source_id: srcB,
                            type: typeB,
                            origin: String(itemB.origin || 'ORG-Y'),
                            field_path: conflict.field_path || conflict.field,
                            matching_text: String(valB),
                          })
                        }
                        className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-white hover:bg-slate-50 text-amber-800 border border-amber-300 transition-colors"
                      >
                        {srcB}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
