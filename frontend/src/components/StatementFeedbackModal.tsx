import React, { useState } from 'react';
import { summariesApi } from '../services/api';
import { X, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

interface StatementFeedbackModalProps {
  summaryId: string;
  statementRef: string;
  statementText: string;
  onClose: () => void;
  onSuccess?: () => void;
}

export const StatementFeedbackModal: React.FC<StatementFeedbackModalProps> = ({
  summaryId,
  statementRef,
  statementText,
  onClose,
  onSuccess,
}) => {
  const [feedbackType, setFeedbackType] = useState('incorrect_fact');
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await summariesApi.submitFeedback(summaryId, statementRef, feedbackType, comment.trim());
      setIsSuccess(true);
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 1200);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit feedback.');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-2xs transition-opacity"
        onClick={onClose}
      />

      {/* Modal Dialog */}
      <div className="relative bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-lg w-full p-6 z-10 animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-start justify-between pb-3 border-b border-slate-100">
          <div>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-800">
              {statementRef}
            </span>
            <h3 className="text-base font-bold text-slate-900 mt-1">
              Report Clinical Discrepancy
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {isSuccess ? (
          <div className="py-8 text-center space-y-2">
            <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto animate-bounce" />
            <h4 className="text-base font-bold text-slate-900">Feedback Recorded</h4>
            <p className="text-xs text-slate-500">
              Thank you for verifying this statement against source records.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            {error && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Quoted Statement */}
            <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 text-xs text-slate-700 italic">
              "{statementText}"
            </div>

            {/* Feedback Category */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
                Feedback Type
              </label>
              <select
                value={feedbackType}
                onChange={(e) => setFeedbackType(e.target.value)}
                className="w-full text-xs border border-slate-300 rounded-lg p-2.5 bg-white text-slate-900 focus:ring-2 focus:ring-[#F08080]"
              >
                <option value="incorrect_fact">Incorrect fact or numerical value</option>
                <option value="conflicting_record">Contradicts another source document</option>
                <option value="wrong_citation">Cites wrong source record</option>
                <option value="missing_context">Missing critical clinical context</option>
              </select>
            </div>

            {/* Clinical Note / Comments */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
                Clinician Comment (Optional)
              </label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Describe the discrepancy or the correct source record..."
                rows={3}
                className="w-full text-xs border border-slate-300 rounded-lg p-2.5 text-slate-900 placeholder-slate-400 focus:ring-2 focus:ring-[#F08080]"
              />
            </div>

            {/* Buttons */}
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-[#F08080] hover:bg-[#D96969] rounded-lg transition-colors disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Submitting...</span>
                  </>
                ) : (
                  <span>Submit Report</span>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
