import React, { type ReactNode } from 'react';
import { Navigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../types/api';
import { ShieldX, Loader2, ArrowLeft } from 'lucide-react';

interface ProtectedRouteProps {
  children: ReactNode;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-[#F08080] animate-spin" />
          <p className="text-sm font-medium text-slate-600">
            Verifying clinical credentials...
          </p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    if (user.role === 'patient') {
      return <Navigate to={`/patients/${user.patient_id || 'P-101'}`} replace />;
    }
    if (user.role === 'ova_admin') {
      return <Navigate to="/audit" replace />;
    }
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-white rounded-xl border border-rose-200 p-6 shadow-sm text-center">
          <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 mx-auto flex items-center justify-center mb-4">
            <ShieldX className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-2">
            Access Restricted (403 Forbidden)
          </h2>
          <p className="text-sm text-slate-600 mb-4 leading-relaxed">
            Your role (<strong className="capitalize">{user.role}</strong>) does not have authorization to view this clinical resource under EMR governance rules.
          </p>
          <div className="bg-slate-50 rounded-lg p-3 text-xs text-slate-500 font-mono mb-6 text-left border border-slate-200">
            <div>User: {user.username}</div>
            <div>Facility: {user.org_id}</div>
            <div>Allowed: {allowedRoles.join(', ')}</div>
          </div>
          <Link
            to="/patients"
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-800 text-white text-sm font-medium rounded-lg hover:bg-slate-700 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Return to Patient Search</span>
          </Link>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
