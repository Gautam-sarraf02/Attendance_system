import React, { useEffect, useState } from 'react';
import { LogOut, UserCircle, Radio, Clock } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { attendanceService } from '../services/attendanceService';
import { Link } from 'react-router-dom';

export const Navbar = () => {
  const { user, logout } = useAuth();
  const [activeSession, setActiveSession] = useState(null);

  useEffect(() => {
    const fetchActiveSession = async () => {
      try {
        const session = await attendanceService.getActiveSession();
        setActiveSession(session);
      } catch (err) {
        // quiet fail
      }
    };

    fetchActiveSession();
    const interval = setInterval(fetchActiveSession, 6000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header style={{
      height: '60px',
      background: '#ffffff',
      borderBottom: '1px solid var(--border-color)',
      padding: '0 2rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      position: 'sticky',
      top: 0,
      zIndex: 9
    }}>
      {/* Active Session Alert Banner */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {activeSession ? (
          <Link
            to="/attendance/live"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.35rem 0.8rem',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--success-light)',
              border: '1px solid var(--success-border)',
              color: 'var(--success)',
              fontSize: '0.8rem',
              fontWeight: 600,
              textDecoration: 'none'
            }}
          >
            <span className="pulse-indicator pulse-green" />
            <span>Active Session: <strong>{activeSession.subject}</strong> ({activeSession.section})</span>
            <span style={{ color: 'var(--text-muted)' }}>• {activeSession.total_present} Present</span>
          </Link>
        ) : (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.45rem',
            color: 'var(--text-muted)',
            fontSize: '0.8rem',
            fontWeight: 500
          }}>
            <Radio size={14} />
            <span>No Active Class Session</span>
          </div>
        )}
      </div>

      {/* User Actions & Date */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
        <div style={{
          fontSize: '0.8rem',
          color: 'var(--text-muted)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.35rem'
        }}>
          <Clock size={14} />
          <span>{new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}</span>
        </div>

        <div style={{
          width: '1px',
          height: '24px',
          background: 'var(--border-color)'
        }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'right' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              {user?.full_name || user?.name || user?.username || 'User'}
            </span>
            <span style={{
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
              textTransform: 'capitalize'
            }}>
              Role: {user?.role || 'User'}
            </span>
          </div>

          <button
            onClick={logout}
            className="btn btn-secondary btn-sm"
            title="Sign out"
            style={{
              padding: '0.35rem 0.75rem',
              fontSize: '0.78rem'
            }}
          >
            <LogOut size={14} />
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
