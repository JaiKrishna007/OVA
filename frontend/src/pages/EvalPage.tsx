import React, { useState, useEffect } from 'react';
import { evalApi, ApiClientError } from '../services/api';
import type { EvaluationResponse } from '../types/api';
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  BarChart3,
  Clock,
  FileCheck,
  Zap,
  Target,
  Bug,
  ChevronRight,
  Database,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const EvalPage: React.FC = () => {
  const [data, setData] = useState<EvaluationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunningEval, setIsRunningEval] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLatestEval = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await evalApi.getLatest();
      setData(res);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Failed to load evaluation benchmark.');
      } else {
        setError('Network error while fetching evaluation benchmark.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunEval = async (adversarial: boolean) => {
    setIsRunningEval(true);
    setError(null);
    try {
      const res = await evalApi.runEval(adversarial);
      setData(res);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Evaluation run failed.');
      } else {
        setError('Failed to trigger evaluation benchmark run.');
      }
    } finally {
      setIsRunningEval(false);
    }
  };

  useEffect(() => {
    fetchLatestEval();
  }, []);

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto py-16 px-4 text-center">
        <RotateCw className="w-10 h-10 text-[#F08080] animate-spin mx-auto mb-4" />
        <h2 className="text-lg font-bold text-slate-800">Loading Clinical Benchmark Evaluation...</h2>
        <p className="text-xs text-slate-500 mt-1">
          Evaluating patient summaries against gold standards, calculating citation accuracy and degradation ratios.
        </p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="max-w-3xl mx-auto py-12 px-4">
        <div className="bg-white rounded-xl border border-rose-200 p-8 text-center space-y-4 shadow-xs">
          <AlertTriangle className="w-10 h-10 text-rose-500 mx-auto" />
          <h3 className="text-base font-bold text-slate-900">Benchmark Evaluation Unavailable</h3>
          <p className="text-sm text-slate-600">{error}</p>
          <button
            onClick={fetchLatestEval}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-800"
          >
            <RotateCw className="w-3.5 h-3.5" />
            <span>Retry</span>
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const m = data.summary_metrics;
  const isAdv = data.is_adversarial;
  const totalBlocked = m.total_claims_blocked || 0;
  const blockedReasons = data.blocked_reasons || {};

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 space-y-8">
      {/* Page Header */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-1.5">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <BarChart3 className="w-6 h-6 text-[#F08080]" />
              <span>AI Evaluation & Safety Benchmark</span>
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D]">
              Provider: {data.provider}
            </span>
            {isAdv ? (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-300 flex items-center gap-1">
                <Bug className="w-3.5 h-3.5 text-amber-600" />
                <span>Adversarial Mode (60% corrupted)</span>
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span>Standard Benchmark</span>
              </span>
            )}
          </div>
          <div className="text-xs text-slate-500 flex items-center gap-2">
            <Clock className="w-3.5 h-3.5" />
            <span>Last evaluated: {new Date(data.run_at).toLocaleString()}</span>
            <span>&bull;</span>
            <span className="font-mono text-slate-400">Run ID: {data.run_id}</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 self-start md:self-center">
          <button
            type="button"
            onClick={() => handleRunEval(false)}
            disabled={isRunningEval}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-xl text-xs font-semibold hover:bg-slate-800 transition-colors disabled:opacity-50 shadow-2xs"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isRunningEval ? 'animate-spin' : ''}`} />
            <span>Re-run Evaluation</span>
          </button>
          <button
            type="button"
            onClick={() => handleRunEval(true)}
            disabled={isRunningEval}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#FFF0ED] text-[#A83232] border border-[#F8AD9D] hover:bg-[#FEEBE3] rounded-xl text-xs font-semibold transition-colors disabled:opacity-50"
            title="Injects 60% bad/corrupted claims to test zero-LLM claim validator blocking"
          >
            <Bug className="w-3.5 h-3.5" />
            <span>Run Adversarial Test</span>
          </button>
        </div>
      </div>

      {/* KPI Benchmark Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Fact Recall */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
              <Target className="w-4 h-4 text-[#F08080]" />
              <span>Fact Recall</span>
            </span>
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700">
              Target &gt;80%
            </span>
          </div>
          <div className="space-y-1">
            <div className="text-2xl font-black text-slate-900">
              {(m.fact_recall * 100).toFixed(1)}%
            </div>
            <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, m.fact_recall * 100)}%` }}
              />
            </div>
          </div>
          <p className="text-[11px] text-slate-500">Gold clinical facts captured in verified claims.</p>
        </div>

        {/* Citation Accuracy */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
              <FileCheck className="w-4 h-4 text-[#F08080]" />
              <span>Citation Accuracy</span>
            </span>
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700">
              Target ~100%
            </span>
          </div>
          <div className="space-y-1">
            <div className="text-2xl font-black text-slate-900">
              {(m.citation_accuracy * 100).toFixed(1)}%
            </div>
            <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, m.citation_accuracy * 100)}%` }}
              />
            </div>
          </div>
          <p className="text-[11px] text-slate-500">Independent check verifying source support.</p>
        </div>

        {/* Unsupported-Claim Rate */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-[#F08080]" />
              <span>Unsupported Claims</span>
            </span>
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700">
              Target 0.0%
            </span>
          </div>
          <div className="space-y-1">
            <div className={`text-2xl font-black ${m.unsupported_claim_rate === 0 ? 'text-emerald-700' : 'text-rose-600'}`}>
              {(m.unsupported_claim_rate * 100).toFixed(1)}%
            </div>
            <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div
                className={`${m.unsupported_claim_rate === 0 ? 'bg-emerald-500' : 'bg-rose-500'} h-full rounded-full transition-all duration-500`}
                style={{ width: `${Math.max(5, m.unsupported_claim_rate * 100)}%` }}
              />
            </div>
          </div>
          <p className="text-[11px] text-slate-500">Claims displayed without verifiable grounding.</p>
        </div>

        {/* Conflict Recall */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-[#F08080]" />
              <span>Conflict Recall</span>
            </span>
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700">
              Target 100%
            </span>
          </div>
          <div className="space-y-1">
            <div className="text-2xl font-black text-slate-900">
              {(m.conflict_recall * 100).toFixed(1)}%
            </div>
            <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, m.conflict_recall * 100)}%` }}
              />
            </div>
          </div>
          <p className="text-[11px] text-slate-500">False-positive rate: {(m.conflict_false_positive_rate * 100).toFixed(1)}%</p>
        </div>
      </div>

      {/* Secondary Benchmark Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Absence Recall */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-2xs flex items-center gap-4">
          <div className="p-3 rounded-xl bg-purple-50 text-purple-700">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500">Absence Detection Recall</div>
            <div className="text-xl font-bold text-slate-900">{(m.absence_recall * 100).toFixed(1)}%</div>
            <div className="text-[11px] text-slate-400">100% gold absences flagged (semen, HSG)</div>
          </div>
        </div>

        {/* Prompt Injection Defense */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-2xs flex items-center gap-4">
          <div className="p-3 rounded-xl bg-emerald-50 text-emerald-700">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500">Prompt Injection Defense</div>
            <div className="text-xl font-bold text-slate-900">{(m.injection_pass_rate * 100).toFixed(1)}%</div>
            <div className="text-[11px] text-slate-400">P-106 override intercepted & neutralized</div>
          </div>
        </div>

        {/* Avg Latency & Blocked Rate */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-2xs flex items-center gap-4">
          <div className="p-3 rounded-xl bg-amber-50 text-amber-700">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500">Avg Generation Latency</div>
            <div className="text-xl font-bold text-slate-900">{m.avg_latency_seconds.toFixed(2)}s</div>
            <div className="text-[11px] text-slate-400">Blocked claims: {(m.blocked_claim_rate * 100).toFixed(1)}% ({totalBlocked})</div>
          </div>
        </div>
      </div>

      {/* Blocked Claims Reasons Breakdown */}
      {Object.keys(blockedReasons).length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[#F08080]" />
              <span>Zero-LLM Claim Validator: Intercepted Failure Codes</span>
            </h3>
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
              Total Blocked: {totalBlocked} claims
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(blockedReasons)
              .sort((a, b) => b[1] - a[1])
              .map(([reasonCode, count]) => {
                const pct = totalBlocked > 0 ? (count / totalBlocked) * 100 : 0;
                return (
                  <div key={reasonCode} className="p-3 rounded-xl border border-slate-200 bg-slate-50 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-bold text-slate-800">{reasonCode}</span>
                      <span className="font-bold text-[#A83232]">{count} ({pct.toFixed(0)}%)</span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-1 overflow-hidden">
                      <div className="bg-[#F08080] h-full rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Per-Patient Benchmark Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden space-y-0">
        <div className="p-5 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Per-Patient Clinical Summary Performance</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Verified statements, gold recall, citation provenance, and latency across all 6 seed patients.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold">
                <th className="py-3 px-4">Patient</th>
                <th className="py-3 px-4">Verified Claims</th>
                <th className="py-3 px-4">Blocked Claims</th>
                <th className="py-3 px-4">Fact Recall</th>
                <th className="py-3 px-4">Citation Accuracy</th>
                <th className="py-3 px-4">Conflicts</th>
                <th className="py-3 px-4">Absences</th>
                <th className="py-3 px-4">Latency</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.per_patient.map((p) => {
                const recallPct = (p.fact_recall * 100).toFixed(0);
                const citPct = (p.citation_accuracy * 100).toFixed(0);
                return (
                  <tr key={p.patient_id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900">{p.patient_name}</div>
                      <div className="text-[11px] text-slate-400 font-mono">{p.patient_id}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                        {p.verified_claims}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {p.blocked_claims > 0 ? (
                        <span className="font-semibold text-rose-800 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                          {p.blocked_claims}
                        </span>
                      ) : (
                        <span className="text-slate-400">0</span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-800">
                      {recallPct}% ({p.gold_facts_matched}/{p.gold_facts_total})
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-800">
                      {citPct}% ({p.accurate_citations}/{p.total_citations})
                    </td>
                    <td className="py-3 px-4">
                      {p.detected_conflicts_total > 0 ? (
                        <span className="font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                          {p.detected_conflicts_total}
                        </span>
                      ) : (
                        <span className="text-slate-400">0</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {p.gold_absences_matched > 0 ? (
                        <span className="font-bold text-purple-800 bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
                          {p.gold_absences_matched}
                        </span>
                      ) : (
                        <span className="text-slate-400">0</span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-600">
                      {p.latency_seconds.toFixed(2)}s
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/patients/${p.patient_id}`}
                        className="inline-flex items-center gap-1 text-[#A83232] hover:text-[#8C3A3A] font-semibold"
                      >
                        <span>View Chart</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
