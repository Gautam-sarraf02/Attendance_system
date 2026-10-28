import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';

// Pages
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Students } from './pages/Students';
import { RegisterStudent } from './pages/RegisterStudent';
import { RegisterFaculty } from './pages/RegisterFaculty';
import { FaceModel } from './pages/FaceModel';
import { LiveAttendance } from './pages/LiveAttendance';
import { AttendanceHistory } from './pages/AttendanceHistory';
import { Reports } from './pages/Reports';
import { Settings } from './pages/Settings';
import { AdminManagement } from './pages/AdminManagement';

const ProtectedLayout = () => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-primary)',
        color: 'var(--text-secondary)'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spin" style={{
            width: '40px',
            height: '40px',
            border: '3px solid #cbd5e1',
            borderTopColor: 'var(--primary)',
            borderRadius: '50%',
            margin: '0 auto 1rem'
          }} />
          <span>Loading ACAS-Portal...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-content">
        <Navbar />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/attendance/live" element={<LiveAttendance />} />
          <Route path="/students" element={<Students />} />
          <Route path="/students/register" element={<RegisterStudent />} />
          <Route path="/faculty/register" element={<RegisterFaculty />} />
          <Route path="/model" element={<FaceModel />} />
          <Route path="/attendance/history" element={<AttendanceHistory />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/admin" element={<AdminManagement />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
};

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={<ProtectedLayout />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
