import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LogIn,
  Key,
  User,
  GraduationCap,
  AlertCircle,
  ShieldCheck,
  Shield,
  BookOpen
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import acasBg from '../assets/acas-portal-bg.png';
import './Login.css';

const ROLE_CONFIGS = {
  admin: {
    key: 'admin',
    label: 'Admin',
    heading: 'Admin Portal Login',
    subheading: 'System administration, timetables, and academic year settings',
    usernameLabel: 'Admin Username',
    usernamePlaceholder: 'Enter admin username',
    passwordPlaceholder: 'Enter admin password',
    icon: Shield,
    demo: {
      username: 'admin',
      password: 'admin123',
      displayNote: 'admin / admin123'
    }
  },
  faculty: {
    key: 'faculty',
    label: 'Faculty',
    heading: 'Faculty Terminal Login',
    subheading: 'Classroom timetable sessions and teacher face verification',
    usernameLabel: 'Faculty Username',
    usernamePlaceholder: 'Enter faculty username',
    passwordPlaceholder: 'Enter faculty password',
    icon: BookOpen,
    demo: {
      username: 'teacher',
      password: 'teacher123',
      displayNote: 'teacher / teacher123'
    }
  },
  student: {
    key: 'student',
    label: 'Student',
    heading: 'Student Portal Login',
    subheading: 'Attendance profile, lecture history, and correction requests',
    usernameLabel: 'Student Username or Roll No',
    usernamePlaceholder: 'Enter student username or roll number',
    passwordPlaceholder: 'Enter student password',
    icon: GraduationCap,
    demo: {
      username: 'student',
      password: 'student123',
      displayNote: 'student (or 11242211) / student123'
    }
  }
};

export const Login = () => {
  const [selectedRole, setSelectedRole] = useState('admin');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const currentRoleConfig = ROLE_CONFIGS[selectedRole];

  const handleRoleSelect = (roleKey) => {
    if (roleKey === selectedRole) return;
    setSelectedRole(roleKey);
    setUsername('');
    setPassword('');
    setError('');
  };

  const handleAutoFillDemo = () => {
    if (currentRoleConfig.demo) {
      setUsername(currentRoleConfig.demo.username);
      setPassword(currentRoleConfig.demo.password);
      setError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Please enter both username and password.');
      return;
    }

    try {
      setError('');
      setLoading(true);
      await login(username, password, selectedRole);
      navigate('/');
    } catch (err) {
      if (!err.response) {
        setError('Cannot connect to backend server at http://127.0.0.1:8000. Please ensure the backend is running.');
      } else if (err.response.status === 401) {
        setError(err.response.data?.detail || 'Incorrect username or password.');
      } else if (err.response.status === 403) {
        setError(err.response.data?.detail || 'Role mismatch: Your account is not authorized for this role.');
      } else {
        setError(err.response.data?.detail || `Authentication failed (${err.response.status}).`);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="acas-login-wrapper" style={{ backgroundImage: `url(${acasBg})` }}>
      <div className="acas-login-overlay" />

      <div className="acas-login-container">
        {/* Left Branding Section */}
        <div className="acas-brand-section">
          <div className="acas-brand-badge">
            <GraduationCap size={16} />
            <span>Classroom Attendance Management System</span>
          </div>

          <h1 className="acas-brand-title">
            ACAS-<span className="acas-brand-title-accent">Portal</span>
          </h1>

          <p className="acas-brand-subtitle">
            Classroom Attendance Management System
          </p>

          <div className="acas-brand-tagline">
            Smart Attendance &nbsp;|&nbsp; Secure Campus &nbsp;|&nbsp; Better Tomorrow
          </div>
        </div>

        {/* Right Login Card Section */}
        <div className="acas-card-section">
          <div className="acas-login-card">
            {/* Card Header */}
            <div className="acas-card-header">
              <div className="acas-card-logo-box">
                <GraduationCap size={28} />
              </div>
              <h2 className="acas-card-title">
                ACAS-<span>Portal</span>
              </h2>
              <p className="acas-card-subtitle">
                Classroom Attendance Management System
              </p>
            </div>

            {/* Role Selection Segmented Control */}
            <div className="acas-role-selector-wrap">
              <label className="acas-role-selector-label" htmlFor="role-selector">
                Select Your Role
              </label>

              <div id="role-selector" className="acas-role-selector">
                {Object.values(ROLE_CONFIGS).map((roleItem) => {
                  const isSelected = selectedRole === roleItem.key;
                  const RoleIcon = roleItem.icon;
                  return (
                    <button
                      key={roleItem.key}
                      type="button"
                      id={`role-btn-${roleItem.key}`}
                      onClick={() => handleRoleSelect(roleItem.key)}
                      className={`acas-role-btn ${isSelected ? 'active' : ''}`}
                    >
                      <RoleIcon size={15} />
                      <span>{roleItem.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Role Form Heading */}
            <div className="acas-role-heading-banner">
              <h3 className="acas-role-heading">
                {currentRoleConfig.heading}
              </h3>
              <p className="acas-role-subheading">
                {currentRoleConfig.subheading}
              </p>
            </div>

            {/* Error message */}
            {error && (
              <div style={{
                background: 'var(--danger-light)',
                border: '1px solid var(--danger-border)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.65rem 0.85rem',
                color: 'var(--danger)',
                fontSize: '0.825rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginBottom: '1.25rem'
              }}>
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <span>{error}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit}>
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label" htmlFor="username">
                  {currentRoleConfig.usernameLabel}
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    id="username"
                    type="text"
                    className="form-input"
                    placeholder={currentRoleConfig.usernamePlaceholder}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    style={{ paddingLeft: '2.4rem' }}
                    autoComplete="username"
                  />
                  <User
                    size={16}
                    style={{
                      position: 'absolute',
                      left: '0.85rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted)'
                    }}
                  />
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                <label className="form-label" htmlFor="password">
                  Password
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    id="password"
                    type="password"
                    className="form-input"
                    placeholder={currentRoleConfig.passwordPlaceholder}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    style={{ paddingLeft: '2.4rem' }}
                    autoComplete="current-password"
                  />
                  <Key
                    size={16}
                    style={{
                      position: 'absolute',
                      left: '0.85rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted)'
                    }}
                  />
                </div>
              </div>

              <button
                type="submit"
                id="sign-in-btn"
                disabled={loading}
                className="acas-submit-btn"
              >
                <LogIn size={16} />
                <span>{loading ? 'Authenticating...' : `Sign In as ${currentRoleConfig.label}`}</span>
              </button>
            </form>

            {/* Role-Specific Demo Credentials Helper */}
            <div className="acas-demo-box">
              {currentRoleConfig.demo ? (
                <>
                  <div className="acas-demo-title">
                    Configured Demo Account for {currentRoleConfig.label}:
                  </div>
                  <div className="acas-demo-code">
                    <code>{currentRoleConfig.demo.displayNote}</code>
                  </div>
                  <button
                    type="button"
                    id="autofill-demo-btn"
                    onClick={handleAutoFillDemo}
                    className="acas-demo-btn"
                  >
                    <ShieldCheck size={14} /> Auto-fill {currentRoleConfig.label} Credentials
                  </button>
                </>
              ) : (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  No demo credentials configured for {currentRoleConfig.label}.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
