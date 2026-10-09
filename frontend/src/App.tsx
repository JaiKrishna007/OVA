import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { ClinicalLayout } from './components/ClinicalLayout';
import { LoginPage } from './pages/LoginPage';
import { PatientSearchPage } from './pages/PatientSearchPage';
import { PatientDetailPage } from './pages/PatientDetailPage';
import { EvalPage } from './pages/EvalPage';
import { ImportPage } from './pages/ImportPage';
import { AuditPage } from './pages/AuditPage';
import { TransfersPage } from './pages/TransfersPage';

import { useAuth } from './context/AuthContext';

import { useParams } from 'react-router-dom';

const RoleBasedRedirect: React.FC = () => {
  const { user } = useAuth();
  if (user?.role === 'patient') {
    return <Navigate to={`/patients/${user.patient_id || 'P-101'}`} replace />;
  }
  if (user?.role === 'ova_admin') {
    return <Navigate to="/audit" replace />;
  }
  return <Navigate to="/patients" replace />;
};

const PatientRedirect: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  return <Navigate to={`/patients/${id || 'P-101'}`} replace />;
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public login route */}
          <Route path="/login" element={<LoginPage />} />

          {/* Direct aliases for /home and /patient (singular) */}
          <Route path="/home" element={<RoleBasedRedirect />} />
          <Route path="/patient" element={<RoleBasedRedirect />} />
          <Route path="/patient/:id" element={<PatientRedirect />} />

          {/* Protected clinical routes */}
          <Route
            path="/patients"
            element={
              <ProtectedRoute allowedRoles={['doctor', 'hospital_admin', 'staff', 'admin']}>
                <ClinicalLayout>
                  <PatientSearchPage />
                </ClinicalLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/patients/:id"
            element={
              <ProtectedRoute allowedRoles={['doctor', 'hospital_admin', 'patient', 'staff', 'admin']}>
                <ClinicalLayout>
                  <PatientDetailPage />
                </ClinicalLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/eval"
            element={
              <ProtectedRoute allowedRoles={['doctor', 'admin', 'ova_admin']}>
                <ClinicalLayout>
                  <EvalPage />
                </ClinicalLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/import"
            element={
              <ProtectedRoute allowedRoles={['hospital_admin', 'staff', 'admin']}>
                <ClinicalLayout>
                  <ImportPage />
                </ClinicalLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/transfers"
            element={
              <ProtectedRoute allowedRoles={['doctor', 'hospital_admin', 'staff', 'admin']}>
                <ClinicalLayout>
                  <TransfersPage />
                </ClinicalLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/audit"
            element={
              <ProtectedRoute allowedRoles={['hospital_admin', 'admin', 'ova_admin']}>
                <ClinicalLayout>
                  <AuditPage />
                </ClinicalLayout>
              </ProtectedRoute>
            }
          />

          {/* Fallback & Root redirects */}
          <Route path="/" element={<RoleBasedRedirect />} />
          <Route path="*" element={<RoleBasedRedirect />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
