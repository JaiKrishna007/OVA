import React, { useState, useEffect, type ReactNode } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { systemApi } from '../services/api';
import { FertilityBackground } from './FertilityBackground';
import { Baby3D } from './Baby3D';
import {
  Users,
  LogOut,
  ShieldAlert,
  HeartPulse,
  BarChart3,
  UploadCloud,
  ArrowRightLeft,
} from 'lucide-react';

interface ClinicalLayoutProps {
  children: ReactNode;
}

export const ClinicalLayout: React.FC<ClinicalLayoutProps> = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [llmProvider, setLlmProvider] = useState<string>('mock');

  useEffect(() => {
    systemApi.getHealth().then((res) => {
      if (res.llm_provider) {
        setLlmProvider(res.llm_provider);
      }
    }).catch(() => {});
  }, []);

  const homePath = user?.role === 'patient'
    ? (user.patient_id ? `/patients/${user.patient_id}` : '/patients')
    : (user?.role === 'ova_admin' ? '/audit' : '/patients');

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true, state: {} });
  };

  const navItems = [
    ...(user?.role === 'patient'
      ? [
          {
            name: 'My Timeline & Records',
            path: user.patient_id ? `/patients/${user.patient_id}` : '/patients',
            icon: HeartPulse,
            description: 'My medical record & timeline',
          },
        ]
      : user?.role === 'ova_admin'
      ? [
          {
            name: 'Audit Logs',
            path: '/audit',
            icon: ShieldAlert,
            description: 'Security & access governance logs',
          },
          {
            name: 'AI Benchmark Eval',
            path: '/eval',
            icon: BarChart3,
            description: 'Model benchmark & safety metrics',
          },
        ]
      : [
          {
            name: 'Patient Search',
            path: '/patients',
            icon: Users,
            description: 'Search & clinical registry',
          },
          ...(user?.role === 'hospital_admin' || user?.role === 'admin' || user?.role === 'doctor' || user?.role === 'staff'
            ? [
                {
                  name: 'Transfers & Consents',
                  path: '/transfers',
                  icon: ArrowRightLeft,
                  description: 'Cross-hospital transfer requests & consents',
                },
              ]
            : []),
          ...(user?.role === 'hospital_admin' || user?.role === 'admin' || user?.role === 'staff'
            ? [
                {
                  name: 'Transfer Import',
                  path: '/import',
                  icon: UploadCloud,
                  description: 'External quarantine & transfer queue',
                },
              ]
            : []),
          ...(user?.role === 'hospital_admin' || user?.role === 'admin'
            ? [
                {
                  name: 'Audit Logs',
                  path: '/audit',
                  icon: ShieldAlert,
                  description: 'Security & access governance logs',
                },
              ]
            : []),
          ...(user?.role === 'doctor' || user?.role === 'admin'
            ? [
                {
                  name: 'AI Benchmark Eval',
                  path: '/eval',
                  icon: BarChart3,
                  description: 'Model benchmark & safety metrics',
                },
              ]
            : []),
        ]),
  ];

  return (
    <div className="min-h-screen relative flex flex-col text-slate-900 antialiased selection:bg-[#FBC4AB] selection:text-slate-900 overflow-x-hidden">
      {/* Dynamic 16:9 Full-Screen Fertility Background */}
      <FertilityBackground />

      {/* Floating Interactive 3D Embryo Vista */}
      <Baby3D />

      {/* 1. Persistent Top Bar */}
      <header className="sticky top-0 z-40 bg-white/85 backdrop-blur-md border-b border-[#FBC4AB]/40 shadow-peach-xs transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Brand */}
          <div
            onClick={() => navigate(homePath)}
            className="flex items-center gap-3 cursor-pointer select-none group"
            title="Go to Home"
          >
            <div className="p-1 rounded-xl bg-gradient-to-br from-[#FFF9F7] to-[#FFDAB9]/30 border border-[#FBC4AB]/40 shadow-peach-xs group-hover:scale-105 transition-transform">
              <img
                src="/logo.png"
                alt="OVA"
                className="h-9 w-auto object-contain"
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-[#FFF9F7] text-[#822828] border border-[#F8AD9D]/60 shadow-peach-xs">
                  Fertility AI
                </span>
                <span
                  id="active-llm-provider-badge"
                  title={`Active LLM Extraction & Synthesis Provider: ${llmProvider}`}
                  className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-50 text-slate-700 border border-slate-200 flex items-center gap-1 shadow-2xs"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  LLM: {llmProvider}
                </span>
              </div>
              <p className="text-xs text-slate-500 hidden sm:block font-normal mt-0.5">
                Clinical Decision Support Assistant
              </p>
            </div>
          </div>

          {/* User Profile & Actions */}
          <div className="flex items-center gap-3 sm:gap-4">
            {user ? (
              <div className="flex items-center gap-3">
                <div className="hidden sm:flex flex-col text-right">
                  <span className="text-sm font-semibold text-slate-900">
                    {user.username}
                  </span>
                  <div className="flex items-center gap-1.5 justify-end">
                    <span className="text-[11px] uppercase tracking-wider font-semibold text-[#822828] bg-[#FFF9F7] px-1.5 py-0.2 rounded border border-[#F8AD9D]/50">
                      {user.role}
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">
                      {user.org_id}
                    </span>
                  </div>
                </div>

                <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-[#F08080] via-[#F4978E] to-[#FFDAB9] text-white font-bold flex items-center justify-center text-xs shadow-peach-xs border-2 border-white ring-1 ring-[#F8AD9D]/40">
                  {user.username.slice(0, 2).toUpperCase()}
                </div>

                <button
                  onClick={handleLogout}
                  title="Sign out of system"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:text-[#822828] bg-slate-100 hover:bg-[#FFF9F7] border border-transparent hover:border-[#F8AD9D]/60 rounded-lg transition-all focus:outline-hidden focus:ring-2 focus:ring-[#F08080]"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Sign Out</span>
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </header>

      {/* 2. Persistent Clinical Safety Disclaimer Banner */}
      <aside aria-label="Clinical Disclaimer" className="relative z-30 bg-gradient-to-r from-[#FFF9F7]/95 via-white/90 to-[#FFF9F7]/95 border-b border-[#FBC4AB]/35 text-[#822828] px-4 py-2 sm:px-6 shadow-2xs backdrop-blur-xs">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-3 text-xs sm:text-sm">
          <div className="flex items-center gap-2 font-medium">
            <ShieldAlert className="w-4 h-4 text-[#F08080] flex-shrink-0" />
            <span>
              <strong className="font-semibold text-slate-900">
                AI-assisted. Clinician review required.
              </strong>{' '}
              <span className="text-slate-600 hidden md:inline">
                All clinical insights, timelines, and facts are grounded in verified source records. Never replaces clinician judgment.
              </span>
            </span>
          </div>
          <div className="hidden lg:flex items-center gap-2 text-xs text-slate-500 font-mono">
            <span>Reference Date: 2025-03-14</span>
          </div>
        </div>
      </aside>

      {/* 3. Main Body: Left Nav + Content (Elevated above background 3D baby) */}
      <div className="relative z-20 flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col md:flex-row gap-6">
        {/* Left Nav Column */}
        <aside className="w-full md:w-60 flex-shrink-0 relative z-20">
          <nav className="bg-white/95 backdrop-blur-md rounded-2xl border border-[#FBC4AB]/40 p-3 shadow-peach-xs space-y-1 relative z-20">
            <div className="px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-[#822828]/70">
              Navigation
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname.startsWith(item.path);
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all btn-interactive ${
                    isActive
                      ? 'bg-gradient-to-r from-[#FFF9F7] to-[#FFF0ED] text-[#822828] font-bold border border-[#F8AD9D] shadow-peach-xs'
                      : 'text-slate-600 hover:text-[#822828] hover:bg-[#FFF9F7]/80'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-[#F08080]' : 'text-slate-500'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="truncate">{item.name}</div>
                  </div>
                </NavLink>
              );
            })}

            <div className="pt-4 border-t border-slate-100 px-3 pb-1">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-2">
                Quick Scope Info
              </div>
              <div className="p-2.5 bg-slate-50 rounded-lg text-xs space-y-1 text-slate-600 border border-slate-100">
                <div className="flex items-center justify-between">
                  <span>Assigned Scope:</span>
                  <span className="font-semibold text-slate-800">
                    {user?.role === 'patient'
                      ? (user?.patient_id || 'Self')
                      : user?.role === 'doctor'
                      ? 'Assigned Patients'
                      : user?.role === 'hospital_admin'
                      ? 'Hospital Patients'
                      : user?.role === 'ova_admin'
                      ? 'System Admin (Audit Only)'
                      : 'All Org'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Org Facility:</span>
                  <span className="font-semibold text-slate-800">{user?.hospital_id || user?.org_id || 'ORG-Y'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Audit Active:</span>
                  <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    100%
                  </span>
                </div>
              </div>
            </div>
          </nav>
        </aside>

        {/* Content Area */}
        <main className="flex-1 min-w-0" id="main-content">
          {children}
        </main>
      </div>
    </div>
  );
};
