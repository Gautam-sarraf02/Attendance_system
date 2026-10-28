import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Calendar,
  Clock,
  BookOpen,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldCheck,
  RefreshCw,
  TrendingUp,
  ArrowRight,
  GraduationCap
} from 'lucide-react';
import { attendanceService } from '../services/attendanceService';
import { NotificationToast } from '../components/NotificationToast';

export const StudentDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [toast, setToast] = useState(null);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const dashData = await attendanceService.getStudentDashboard();
      setData(dashData);
    } catch (err) {
      console.error('Failed to load student dashboard:', err);
      setToast({
        message: err.response?.data?.detail || 'Failed to load your attendance overview.',
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  if (loading && !data) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        gap: '1rem'
      }}>
        <div className="spin" style={{
          width: '36px',
          height: '36px',
          border: '3px solid #cbd5e1',
          borderTopColor: '#243B64',
          borderRadius: '50%'
        }} />
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          Loading your attendance overview...
        </span>
      </div>
    );
  }

  const profile = data?.profile || {};
  const validity = data?.validity || {};
  const stats = data?.stats || {};
  const subjectStats = data?.subject_stats || [];
  const monthlyStats = data?.monthly_stats || [];

  const isEligible = stats.is_eligible_for_exams ?? (stats.overall_percentage >= 75);

  return (
    <div className="page-body">
      {toast && (
        <NotificationToast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* 1. Student Identity & Registration Profile Card */}
      <div style={{
        background: '#ffffff',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-lg)',
        padding: '1.5rem',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1.25rem',
        marginBottom: '1.5rem'
      }}>
        {/* Student Profile Info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.15rem' }}>
          <div style={{
            width: '54px',
            height: '54px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontWeight: 800,
            fontSize: '1.35rem',
            flexShrink: 0
          }}>
            {profile.name ? profile.name.charAt(0).toUpperCase() : 'S'}
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
              <h1 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                {profile.name || 'Student Attendance'}
              </h1>
              <span style={{
                background: 'var(--primary-light)',
                color: '#1e3a8a',
                padding: '0.15rem 0.55rem',
                borderRadius: '4px',
                fontSize: '0.78rem',
                fontWeight: 700,
                border: '1px solid #bfdbfe'
              }}>
                Roll #{profile.roll_number || 'N/A'}
              </span>
            </div>

            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              marginTop: '0.35rem',
              color: 'var(--text-secondary)',
              fontSize: '0.825rem',
              flexWrap: 'wrap'
            }}>
              <span>Dept: <strong style={{ color: 'var(--text-primary)' }}>{profile.department || 'CSE'}</strong></span>
              <span>•</span>
              <span>Semester: <strong style={{ color: 'var(--text-primary)' }}>{profile.semester || 8}</strong></span>
              <span>•</span>
              <span>Section: <strong style={{ color: 'var(--text-primary)' }}>{profile.section || 'A'}</strong></span>
              <span>•</span>
              <span>Academic Year: <strong style={{ color: 'var(--text-primary)' }}>{profile.academic_year_code || 'Current Year'}</strong></span>
            </div>
          </div>
        </div>

        {/* Biometric Status & Quick Action */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{
            background: '#f8fafc',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-md)',
            padding: '0.75rem 1rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.85rem'
          }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              background: validity.is_valid ? 'var(--success-light)' : 'var(--danger-light)',
              color: validity.is_valid ? 'var(--success)' : 'var(--danger)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {validity.is_valid ? <ShieldCheck size={20} /> : <AlertTriangle size={20} />}
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Biometric Face ID
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: validity.is_valid ? 'var(--success)' : 'var(--danger)' }}>
                {validity.is_valid ? 'Active & Valid' : 'Enrollment Required'}
              </div>
            </div>
          </div>

          <button
            onClick={fetchDashboardData}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
              padding: '0.6rem 0.95rem',
              borderRadius: 'var(--radius-md)',
              background: '#ffffff',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-color)',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            <RefreshCw size={14} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 2. Top Metric Cards: Overview Attendance Numbers */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '1rem',
        marginBottom: '1.5rem'
      }}>
        {/* Overall Percentage */}
        <div style={{
          background: '#ffffff',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.25rem 1.4rem',
          boxShadow: 'var(--shadow-sm)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Overall Attendance
          </span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', margin: '0.35rem 0' }}>
            <span style={{
              fontSize: '2.1rem',
              fontWeight: 800,
              color: isEligible ? 'var(--success)' : '#d97706',
              lineHeight: 1
            }}>
              {stats.overall_percentage ?? 0}%
            </span>
          </div>
          <div style={{ paddingTop: '0.5rem', borderTop: '1px solid #f1f5f9' }}>
            {isEligible ? (
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.3rem',
                fontSize: '0.75rem',
                color: 'var(--success)',
                fontWeight: 700
              }}>
                <CheckCircle2 size={13} /> Eligible for Exams (≥ 75%)
              </span>
            ) : (
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.3rem',
                fontSize: '0.75rem',
                color: 'var(--danger)',
                fontWeight: 700
              }}>
                <AlertTriangle size={13} /> Attendance Warning (&lt; 75%)
              </span>
            )}
          </div>
        </div>

        {/* Total Lectures */}
        <div style={{
          background: '#ffffff',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.25rem 1.4rem',
          boxShadow: 'var(--shadow-sm)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Total Lectures
          </span>
          <div style={{ fontSize: '2.1rem', fontWeight: 800, color: 'var(--text-primary)', margin: '0.35rem 0', lineHeight: 1 }}>
            {stats.total_classes ?? 0}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', paddingTop: '0.5rem', borderTop: '1px solid #f1f5f9' }}>
            Conducted sessions in semester
          </div>
        </div>

        {/* Lectures Attended (Present) */}
        <div style={{
          background: '#ffffff',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.25rem 1.4rem',
          boxShadow: 'var(--shadow-sm)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Lectures Attended
          </span>
          <div style={{ fontSize: '2.1rem', fontWeight: 800, color: 'var(--success)', margin: '0.35rem 0', lineHeight: 1 }}>
            {stats.total_present ?? 0}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', paddingTop: '0.5rem', borderTop: '1px solid #f1f5f9' }}>
            Verified biometric face punches
          </div>
        </div>

        {/* Finalized Absent Lectures */}
        <div style={{
          background: '#ffffff',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.25rem 1.4rem',
          boxShadow: 'var(--shadow-sm)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Finalized Absences
          </span>
          <div style={{ fontSize: '2.1rem', fontWeight: 800, color: 'var(--danger)', margin: '0.35rem 0', lineHeight: 1 }}>
            {stats.total_absent ?? 0}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', paddingTop: '0.5rem', borderTop: '1px solid #f1f5f9' }}>
            Closed unverified slots
          </div>
        </div>
      </div>

      {/* 3. Callout Link to Dedicated Punch History Page */}
      <div style={{
        background: 'var(--primary-light)',
        border: '1px solid #bfdbfe',
        borderRadius: 'var(--radius-md)',
        padding: '1rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
        marginBottom: '1.5rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Calendar size={20} color="#243B64" />
          <div>
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--primary)' }}>
              Looking for your period-wise Daily Punch History?
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              View individual lecture timestamps, period breakdown indicators, and submit attendance correction requests.
            </div>
          </div>
        </div>

        <Link
          to="/attendance/history"
          className="btn btn-primary btn-sm"
          style={{ textDecoration: 'none' }}
        >
          <span>Open Punch History</span>
          <ArrowRight size={14} />
        </Link>
      </div>

      {/* 4. Subject-wise Attendance Breakdown Table */}
      <div style={{
        background: '#ffffff',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-lg)',
        padding: '1.5rem',
        boxShadow: 'var(--shadow-sm)',
        marginBottom: '1.5rem'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '1.15rem',
          flexWrap: 'wrap',
          gap: '0.75rem'
        }}>
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Course & Subject-wise Attendance Status
            </h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
              Enrolled subjects, attendance percentage, and minimum 75% exam criteria
            </p>
          </div>
        </div>

        {subjectStats.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2.5rem 1.5rem', color: 'var(--text-muted)' }}>
            <BookOpen size={36} style={{ margin: '0 auto 0.5rem', opacity: 0.4 }} />
            <p style={{ margin: 0, fontWeight: 500 }}>No attendance records available yet.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '700px' }}>
              <thead>
                <tr style={{
                  background: '#f8fafc',
                  borderBottom: '1px solid var(--border-color)',
                  color: '#475569',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em'
                }}>
                  <th style={{ padding: '0.75rem 1rem' }}>Subject Name & Code</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Total Classes</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Present</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Absent</th>
                  <th style={{ padding: '0.75rem 1rem', width: '200px' }}>Percentage</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Exam Eligibility</th>
                </tr>
              </thead>
              <tbody>
                {subjectStats.map((sub, idx) => {
                  const pct = sub.percentage ?? 0;
                  const eligible = sub.is_eligible ?? (pct >= 75);
                  return (
                    <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9', fontSize: '0.875rem' }}>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <BookOpen size={15} color="#243B64" />
                          <span>{sub.subject}</span>
                          {sub.subject_code && (
                            <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 500 }}>
                              ({sub.subject_code})
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '0.85rem 1rem', textAlign: 'center', color: 'var(--text-secondary)', fontWeight: 600 }}>
                        {sub.total_classes}
                      </td>
                      <td style={{ padding: '0.85rem 1rem', textAlign: 'center', color: 'var(--success)', fontWeight: 700 }}>
                        {sub.present_count}
                      </td>
                      <td style={{ padding: '0.85rem 1rem', textAlign: 'center', color: sub.absent_count > 0 ? 'var(--danger)' : 'var(--text-muted)', fontWeight: 600 }}>
                        {sub.absent_count}
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                          <div style={{
                            flex: 1,
                            height: '6px',
                            background: '#e2e8f0',
                            borderRadius: '3px',
                            overflow: 'hidden'
                          }}>
                            <div style={{
                              width: `${Math.min(pct, 100)}%`,
                              height: '100%',
                              background: eligible ? 'var(--success)' : '#d97706',
                              borderRadius: '3px'
                            }} />
                          </div>
                          <span style={{
                            fontWeight: 700,
                            fontSize: '0.825rem',
                            color: eligible ? 'var(--success)' : '#d97706',
                            minWidth: '38px',
                            textAlign: 'right'
                          }}>
                            {pct}%
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: '0.85rem 1rem', textAlign: 'center' }}>
                        {eligible ? (
                          <span style={{
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            color: 'var(--success)',
                            background: 'var(--success-light)',
                            border: '1px solid var(--success-border)',
                            padding: '0.2rem 0.55rem',
                            borderRadius: '4px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem'
                          }}>
                            <CheckCircle2 size={12} /> Eligible
                          </span>
                        ) : (
                          <span style={{
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            color: 'var(--danger)',
                            background: 'var(--danger-light)',
                            border: '1px solid var(--danger-border)',
                            padding: '0.2rem 0.55rem',
                            borderRadius: '4px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem'
                          }}>
                            <AlertTriangle size={12} /> Shortage
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 5. Monthly Attendance Trend */}
      {monthlyStats.length > 0 && (
        <div style={{
          background: '#ffffff',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.5rem',
          boxShadow: 'var(--shadow-sm)'
        }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '1rem' }}>
            Monthly Attendance Trend
          </h2>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '1rem'
          }}>
            {monthlyStats.map((m, idx) => {
              const mPct = m.percentage ?? 0;
              const isPassing = mPct >= 75;
              return (
                <div key={idx} style={{
                  background: '#f8fafc',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  padding: '1rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.5rem'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                      {m.month || m.month_name || m.month_key}
                    </span>
                    <span style={{
                      fontWeight: 800,
                      fontSize: '0.95rem',
                      color: isPassing ? 'var(--success)' : '#d97706'
                    }}>
                      {mPct}%
                    </span>
                  </div>

                  <div style={{
                    width: '100%',
                    height: '5px',
                    background: '#e2e8f0',
                    borderRadius: '3px',
                    overflow: 'hidden'
                  }}>
                    <div style={{
                      width: `${Math.min(mPct, 100)}%`,
                      height: '100%',
                      background: isPassing ? 'var(--success)' : '#d97706',
                      borderRadius: '3px'
                    }} />
                  </div>

                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '0.78rem',
                    color: 'var(--text-secondary)'
                  }}>
                    <span>Conducted: <strong>{m.total_classes}</strong></span>
                    <span>Attended: <strong style={{ color: 'var(--success)' }}>{m.present_count}</strong></span>
                    <span>Missed: <strong style={{ color: 'var(--danger)' }}>{m.absent_count}</strong></span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default StudentDashboard;
