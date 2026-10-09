import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { FertilityBackground } from '../components/FertilityBackground';
import { Baby3D } from '../components/Baby3D';
import { HeartPulse, Lock, User, AlertCircle, ArrowRight, ShieldCheck, Stethoscope, Building2 } from 'lucide-react';
import { BASE_URL } from '../services/api';

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('dr.rao');
  const [password, setPassword] = useState('password123');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setFormError('Please enter both username and password.');
      return;
    }

    setFormError(null);
    setIsSubmitting(true);

    try {
      const loggedUser = await login(username.trim(), password);
      if (loggedUser.role === 'patient') {
        const patientTarget = loggedUser.patient_id ? `/patients/${loggedUser.patient_id}` : '/patients/P-101';
        navigate(patientTarget, { replace: true });
      } else if (loggedUser.role === 'ova_admin') {
        navigate('/audit', { replace: true });
      } else {
        navigate('/patients', { replace: true });
      }
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Invalid credentials. Please verify your login details.';
      setFormError(errorMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickSelect = (u: string, p: string = 'password123') => {
    setUsername(u);
    setPassword(p);
    setFormError(null);
  };

  return (
    <div className="min-h-screen relative flex flex-col justify-center py-12 sm:px-6 lg:px-8 overflow-hidden selection:bg-[#FBC4AB]">
      {/* 16:9 Dynamic Fertility Background */}
      <FertilityBackground />

      {/* Floating Interactive 3D Embryo Vista */}
      <Baby3D />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="flex justify-center">
          <div className="p-3 rounded-2xl bg-white/80 backdrop-blur-md border border-[#FBC4AB]/50 shadow-peach-sm">
            <img
              src="/logo.png"
              alt="OVA"
              className="h-20 w-auto object-contain"
            />
          </div>
        </div>
        <p className="mt-4 text-center text-sm font-medium text-slate-600">
          Fertility Treatment & Follow-Up Assistant
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-lg px-4 sm:px-0 relative z-10">
        <div className="bg-white/90 backdrop-blur-xl py-9 px-6 sm:px-10 shadow-peach-md border border-[#FBC4AB]/60 rounded-3xl">
          {formError && (
            <div
              role="alert"
              className="mb-6 rounded-xl bg-rose-50/90 border border-rose-200 p-4 text-sm text-rose-800 flex items-start gap-3 shadow-2xs"
            >
              <AlertCircle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
              <div>
                <strong className="font-semibold block">Authentication Failed</strong>
                <span>{formError}</span>
                <span className="block mt-1 text-[11px] text-rose-600/80 font-mono">Connecting to: {BASE_URL}</span>
              </div>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label
                htmlFor="username"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5"
              >
                Clinical Username
              </label>
              <div className="relative rounded-xl shadow-2xs">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <User className="h-4 w-4" />
                </div>
                <input
                  id="username"
                  name="username"
                  type="text"
                  required
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. dr.rao"
                  className="block w-full pl-10 pr-3.5 py-2.5 text-sm bg-white/80 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-[#F8AD9D]/50 focus:border-[#F08080] transition-all"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5"
              >
                Password
              </label>
              <div className="relative rounded-xl shadow-2xs">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="block w-full pl-10 pr-3.5 py-2.5 text-sm bg-white/80 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-[#F8AD9D]/50 focus:border-[#F08080] transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full flex justify-center items-center gap-2 py-3.5 px-4 border border-transparent rounded-2xl shadow-peach-sm hover:shadow-peach-md text-sm font-bold text-white bg-gradient-to-r from-[#F08080] via-[#F4978E] to-[#F08080] hover:brightness-105 active:scale-[0.98] btn-interactive focus:outline-hidden focus:ring-2 focus:ring-offset-2 focus:ring-[#F08080] transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {isSubmitting ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <span>Sign In to Clinical Workspace</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Quick Persona Selector for Demo & Eval */}
          <div className="mt-8 pt-6 border-t border-slate-100">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-3 text-center">
              Quick Personas (Seeded Credentials)
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              <button
                type="button"
                onClick={() => handleQuickSelect('patient.priya')}
                className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                  username === 'patient.priya'
                    ? 'border-[#F08080] bg-[#FFF0ED] text-[#822828] font-bold ring-2 ring-[#F8AD9D]/40 shadow-peach-xs'
                    : 'border-slate-200/80 bg-white hover:bg-[#FFF9F7] text-slate-700 hover:border-[#FBC4AB]'
                }`}
              >
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-[#822828]">
                  <HeartPulse className="w-3.5 h-3.5 text-[#F08080]" />
                  patient.priya
                </div>
                <div className="text-[10px] text-slate-600 mt-0.5 font-medium">Patient (P-101)</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickSelect('patient.p102')}
                className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                  username === 'patient.p102'
                    ? 'border-[#F08080] bg-[#FFF0ED] text-[#822828] font-bold ring-2 ring-[#F8AD9D]/40 shadow-peach-xs'
                    : 'border-slate-200/80 bg-white hover:bg-[#FFF9F7] text-slate-700 hover:border-[#FBC4AB]'
                }`}
              >
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-[#822828]">
                  <HeartPulse className="w-3.5 h-3.5 text-[#F08080]" />
                  patient.p102
                </div>
                <div className="text-[10px] text-slate-600 mt-0.5 font-medium">Patient (P-102)</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickSelect('patient.p105')}
                className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                  username === 'patient.p105'
                    ? 'border-[#F08080] bg-[#FFF0ED] text-[#822828] font-bold ring-2 ring-[#F8AD9D]/40 shadow-peach-xs'
                    : 'border-slate-200/80 bg-white hover:bg-[#FFF9F7] text-slate-700 hover:border-[#FBC4AB]'
                }`}
              >
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-[#822828]">
                  <HeartPulse className="w-3.5 h-3.5 text-[#F08080]" />
                  patient.p105
                </div>
                <div className="text-[10px] text-slate-600 mt-0.5 font-medium">Patient (P-105)</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickSelect('admin.a')}
                className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                  username === 'admin.a'
                    ? 'border-[#F08080] bg-[#FFF0ED] text-[#822828] font-bold ring-2 ring-[#F8AD9D]/40 shadow-peach-xs'
                    : 'border-slate-200/80 bg-white hover:bg-[#FFF9F7] text-slate-700 hover:border-[#FBC4AB]'
                }`}
              >
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-indigo-700">
                  <Building2 className="w-3.5 h-3.5 text-indigo-600" />
                  admin.a
                </div>
                <div className="text-[10px] text-slate-600 mt-0.5 font-medium">Hospital Admin</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickSelect('dr.rao')}
                className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                  username === 'dr.rao'
                    ? 'border-[#F08080] bg-[#FFF0ED] text-[#822828] font-bold ring-2 ring-[#F8AD9D]/40 shadow-peach-xs'
                    : 'border-slate-200/80 bg-white hover:bg-[#FFF9F7] text-slate-700 hover:border-[#FBC4AB]'
                }`}
              >
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-700">
                  <Stethoscope className="w-3.5 h-3.5 text-emerald-600" />
                  dr.rao
                </div>
                <div className="text-[10px] text-slate-600 mt-0.5 font-medium">Lead Doctor</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickSelect('nurse.devi')}
                className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                  username === 'nurse.devi'
                    ? 'border-[#F08080] bg-[#FFF0ED] text-[#822828] font-bold ring-2 ring-[#F8AD9D]/40 shadow-peach-xs'
                    : 'border-slate-200/80 bg-white hover:bg-[#FFF9F7] text-slate-700 hover:border-[#FBC4AB]'
                }`}
              >
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-sky-700">
                  <User className="w-3.5 h-3.5 text-sky-600" />
                  nurse.devi
                </div>
                <div className="text-[10px] text-slate-600 mt-0.5 font-medium">Clinical Staff</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickSelect('admin')}
                className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                  username === 'admin'
                    ? 'border-[#F08080] bg-[#FFF0ED] text-[#822828] font-bold ring-2 ring-[#F8AD9D]/40 shadow-peach-xs'
                    : 'border-slate-200/80 bg-white hover:bg-[#FFF9F7] text-slate-700 hover:border-[#FBC4AB]'
                }`}
              >
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-purple-700">
                  <ShieldCheck className="w-3.5 h-3.5 text-purple-600" />
                  admin
                </div>
                <div className="text-[10px] text-slate-600 mt-0.5 font-medium">Audit & Eval</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickSelect('dr.menon')}
                className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                  username === 'dr.menon'
                    ? 'border-[#F08080] bg-[#FFF0ED] text-[#822828] font-bold ring-2 ring-[#F8AD9D]/40 shadow-peach-xs'
                    : 'border-slate-200/80 bg-white hover:bg-[#FFF9F7] text-slate-700 hover:border-[#FBC4AB]'
                }`}
              >
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-teal-700">
                  <Stethoscope className="w-3.5 h-3.5 text-teal-600" />
                  dr.menon
                </div>
                <div className="text-[10px] text-slate-600 mt-0.5 font-medium">Hospital B Doctor</div>
              </button>
            </div>
          </div>
        </div>

        <div className="mt-6 text-center text-xs text-slate-600">
          Synthetic clinical test environment. No real protected health information (PHI).
        </div>
      </div>
    </div>
  );
};
