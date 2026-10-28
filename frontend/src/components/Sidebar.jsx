import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  UserPlus,
  Cpu,
  Video,
  History,
  FileBarChart,
  Settings,
  ShieldCheck,
  GraduationCap,
  LogOut,
  UserCircle,
  UserCheck
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Sidebar = () => {
  const { user, logout } = useAuth();

  let navItems = [];
  if (user?.role === 'student') {
    navItems = [
      { to: '/', label: 'My Attendance', icon: LayoutDashboard },
      { to: '/attendance/history', label: 'Punch History', icon: History },
    ];
  } else if (user?.role === 'teacher' || user?.role === 'faculty') {
    navItems = [
      { to: '/', label: 'Faculty Dashboard', icon: LayoutDashboard },
      { to: '/attendance/live', label: 'Live Session', icon: Video, badge: 'FACULTY' },
      { to: '/attendance/history', label: 'Attendance History', icon: History },
      { to: '/reports', label: 'Reports & Export', icon: FileBarChart },
    ];
  } else {
    // Admin role
    navItems = [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/admin', label: 'Admin Hub', icon: ShieldCheck, badge: 'ADMIN' },
      { to: '/attendance/live', label: 'Live Attendance', icon: Video, badge: 'LIVE' },
      { to: '/students', label: 'Students Directory', icon: Users },
      { to: '/students/register', label: 'Register Student', icon: UserPlus },
      { to: '/faculty/register', label: 'Register Faculty', icon: UserCheck },
      { to: '/model', label: 'Face Model (LBPH)', icon: Cpu },
      { to: '/attendance/history', label: 'Attendance History', icon: History },
      { to: '/reports', label: 'Reports & Export', icon: FileBarChart },
      { to: '/settings', label: 'System Settings', icon: Settings },
    ];
  }

  return (
    <aside style={{
      width: '250px',
      background: '#ffffff',
      borderRight: '1px solid var(--border-color)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      height: '100vh',
      position: 'sticky',
      top: 0,
      zIndex: 10
    }}>
      {/* Brand Header */}
      <div style={{
        padding: '1.25rem 1.25rem',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem'
      }}>
        <div style={{
          width: '36px',
          height: '36px',
          borderRadius: 'var(--radius-md)',
          background: 'var(--primary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          flexShrink: 0
        }}>
          <GraduationCap size={20} />
        </div>
        <div style={{ minWidth: 0 }}>
          <h2 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--primary)', lineHeight: 1.2, letterSpacing: '-0.02em' }}>
            ACAS-Portal
          </h2>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 500, lineHeight: 1.25, display: 'block' }}>
            Campus Attendance Management System
          </span>
        </div>
      </div>

      {/* Nav Menu */}
      <nav style={{
        flex: 1,
        padding: '1rem 0.75rem',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.25rem'
      }}>
        <div style={{
          fontSize: '0.68rem',
          fontWeight: 700,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          padding: '0.4rem 0.75rem'
        }}>
          Main Navigation
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.65rem 0.85rem',
                borderRadius: 'var(--radius-md)',
                color: isActive ? '#1e3a8a' : 'var(--text-secondary)',
                background: isActive ? '#eff6ff' : 'transparent',
                fontWeight: isActive ? 700 : 500,
                fontSize: '0.875rem',
                transition: 'background 0.12s ease, color 0.12s ease',
                textDecoration: 'none',
                borderLeft: isActive ? '3px solid #2563eb' : '3px solid transparent'
              })}
            >
              <Icon size={17} style={{ flexShrink: 0 }} />
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.badge && (
                <span style={{
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  padding: '0.1rem 0.45rem',
                  borderRadius: '3px',
                  background: item.badge === 'LIVE' ? '#fef2f2' : '#f1f5f9',
                  color: item.badge === 'LIVE' ? '#dc2626' : '#475569',
                  border: `1px solid ${item.badge === 'LIVE' ? '#fecaca' : '#e2e8f0'}`
                }}>
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* User Account Footer */}
      <div style={{
        padding: '1rem 1.25rem',
        borderTop: '1px solid var(--border-color)',
        background: '#f8fafc',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '0.5rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', overflow: 'hidden' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: '#e2e8f0',
            color: 'var(--primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: '0.8rem',
            flexShrink: 0
          }}>
            {user?.name ? user.name.charAt(0).toUpperCase() : (user?.username?.charAt(0).toUpperCase() || 'U')}
          </div>
          <div style={{ overflow: 'hidden' }}>
            <div style={{
              fontSize: '0.825rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {user?.name || user?.username || 'User'}
            </div>
            <div style={{
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
              textTransform: 'capitalize'
            }}>
              {user?.role || 'User'}
            </div>
          </div>
        </div>

        <button
          onClick={logout}
          title="Sign out of ACAS-Portal"
          style={{
            padding: '0.4rem',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer'
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.background = '#fef2f2'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.background = 'transparent'; }}
        >
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
