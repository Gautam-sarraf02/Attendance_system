import React, { useState, useEffect } from 'react';
import {
  FileBarChart,
  Download,
  FileSpreadsheet,
  Users,
  BookOpen,
  Calendar,
  Percent,
  TrendingUp,
  Filter,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { reportService } from '../services/reportService';
import { NotificationToast } from '../components/NotificationToast';

export const Reports = () => {
  const [activeTab, setActiveTab] = useState('student_summary'); // 'student_summary', 'subject_wise', 'daily', 'monthly'
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);

  // Data states
  const [studentStats, setStudentStats] = useState([]);
  const [subjectStats, setSubjectStats] = useState([]);
  const [dailyStats, setDailyStats] = useState([]);
  const [monthlyStats, setMonthlyStats] = useState([]);

  // Filter states
  const [subjectFilter, setSubjectFilter] = useState('');
  const [sectionFilter, setSectionFilter] = useState('');

  const fetchReportData = async () => {
    try {
      setLoading(true);
      if (activeTab === 'student_summary') {
        const data = await reportService.getStudentReports({
          subject: subjectFilter || undefined,
          section: sectionFilter || undefined
        });
        setStudentStats(data);
      } else if (activeTab === 'subject_wise') {
        const data = await reportService.getSubjectReports();
        setSubjectStats(data);
      } else if (activeTab === 'daily') {
        const data = await reportService.getDailyReports();
        setDailyStats(data);
      } else if (activeTab === 'monthly') {
        const data = await reportService.getMonthlyReports();
        setMonthlyStats(data);
      }
    } catch (err) {
      console.error('Failed to load report data:', err);
      setToast({ message: 'Failed to load report statistics', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReportData();
  }, [activeTab, sectionFilter]);

  const handleApplyFilter = (e) => {
    e.preventDefault();
    fetchReportData();
  };

  const handleExport = async (format) => {
    try {
      setToast({ message: `Preparing ${format.toUpperCase()} report export...`, type: 'info' });
      await reportService.downloadExport(format, activeTab === 'student_summary' ? 'student_summary' : 'detailed', {
        subject: subjectFilter || undefined,
        section: sectionFilter || undefined
      });
      setToast({ message: `${format.toUpperCase()} report exported successfully!`, type: 'success' });
    } catch (err) {
      setToast({ message: 'Failed to export report', type: 'error' });
    }
  };

  return (
    <div className="page-body">
      {toast && (
        <NotificationToast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Header */}
      <div style={{
        marginBottom: '2rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem'
      }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Reports & Analytics</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
            Attendance percentage calculations, subject breakdowns, and Excel/CSV exports.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => handleExport('excel')}
            className="btn btn-success"
            style={{ padding: '0.65rem 1.25rem' }}
          >
            <FileSpreadsheet size={16} />
            <span>Download Excel (.xlsx)</span>
          </button>
          <button
            onClick={() => handleExport('csv')}
            className="btn btn-secondary"
            style={{ padding: '0.65rem 1.25rem' }}
          >
            <Download size={16} />
            <span>Download CSV</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div style={{
        display: 'flex',
        gap: '0.5rem',
        borderBottom: '1px solid var(--border-color)',
        marginBottom: '1.5rem',
        overflowX: 'auto',
        paddingBottom: '0.25rem'
      }}>
        <button
          onClick={() => setActiveTab('student_summary')}
          className={`btn ${activeTab === 'student_summary' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ borderRadius: 'var(--radius-md) var(--radius-md) 0 0' }}
        >
          <Percent size={16} />
          <span>Student Attendance %</span>
        </button>

        <button
          onClick={() => setActiveTab('subject_wise')}
          className={`btn ${activeTab === 'subject_wise' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ borderRadius: 'var(--radius-md) var(--radius-md) 0 0' }}
        >
          <BookOpen size={16} />
          <span>Subject Breakdown</span>
        </button>

        <button
          onClick={() => setActiveTab('daily')}
          className={`btn ${activeTab === 'daily' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ borderRadius: 'var(--radius-md) var(--radius-md) 0 0' }}
        >
          <Calendar size={16} />
          <span>Daily Register</span>
        </button>

        <button
          onClick={() => setActiveTab('monthly')}
          className={`btn ${activeTab === 'monthly' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ borderRadius: 'var(--radius-md) var(--radius-md) 0 0' }}
        >
          <TrendingUp size={16} />
          <span>Monthly Trends</span>
        </button>
      </div>

      {/* Tab 1: Student Attendance Percentage */}
      {activeTab === 'student_summary' && (
        <div>
          {/* Filter Bar */}
          <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
            <form onSubmit={handleApplyFilter} style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div style={{ flex: 1, minWidth: '200px' }}>
                <label className="form-label">Subject Filter</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Computer Vision"
                  value={subjectFilter}
                  onChange={(e) => setSubjectFilter(e.target.value)}
                />
              </div>

              <div style={{ width: '160px' }}>
                <label className="form-label">Section</label>
                <select
                  className="form-select"
                  value={sectionFilter}
                  onChange={(e) => setSectionFilter(e.target.value)}
                >
                  <option value="">All Sections</option>
                  <option value="CSE-A">CSE-A</option>
                  <option value="CSE-B">CSE-B</option>
                  <option value="CSE-C">CSE-C</option>
                </select>
              </div>

              <button type="submit" className="btn btn-secondary">
                <Filter size={16} />
                <span>Filter</span>
              </button>
            </form>
          </div>

          {/* Formula Explanation Banner */}
          <div style={{
            padding: '0.85rem 1.25rem',
            background: 'rgba(99, 102, 241, 0.08)',
            border: '1px solid rgba(99, 102, 241, 0.2)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1.5rem',
            fontSize: '0.85rem',
            color: 'var(--text-secondary)'
          }}>
            <strong style={{ color: 'var(--text-primary)' }}>Formula: </strong>
            <code>Attendance % = (Number of Present Lectures / Total Sessions Held) × 100</code>
          </div>

          {/* Data Table */}
          <div className="card" style={{ padding: 0 }}>
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Roll Number</th>
                    <th>Student Name</th>
                    <th>Section</th>
                    <th>Total Lectures</th>
                    <th>Lectures Present</th>
                    <th>Attendance %</th>
                    <th>Eligibility Status</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan="7" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                        Computing attendance percentages...
                      </td>
                    </tr>
                  ) : studentStats.length === 0 ? (
                    <tr>
                      <td colSpan="7" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                        No student statistics available.
                      </td>
                    </tr>
                  ) : (
                    studentStats.map((s) => {
                      const isEligible = s.percentage >= 75.0;
                      return (
                        <tr key={s.student_id}>
                          <td><code>{s.roll_number}</code></td>
                          <td style={{ fontWeight: 600 }}>{s.name}</td>
                          <td><span className="badge badge-info">{s.section}</span></td>
                          <td>{s.total_lectures}</td>
                          <td><strong style={{ color: '#10b981' }}>{s.present_count}</strong></td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                              <div style={{
                                width: '80px',
                                height: '8px',
                                background: 'var(--bg-tertiary)',
                                borderRadius: '4px',
                                overflow: 'hidden'
                              }}>
                                <div style={{
                                  width: `${Math.min(100, s.percentage)}%`,
                                  height: '100%',
                                  background: s.percentage >= 75 ? '#10b981' : s.percentage >= 60 ? '#f59e0b' : '#ef4444'
                                }} />
                              </div>
                              <strong style={{
                                color: s.percentage >= 75 ? '#10b981' : s.percentage >= 60 ? '#f59e0b' : '#ef4444'
                              }}>
                                {s.percentage}%
                              </strong>
                            </div>
                          </td>
                          <td>
                            <span className={`badge ${isEligible ? 'badge-success' : 'badge-danger'}`}>
                              {isEligible ? 'Eligible' : 'Shortage'}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Subject Breakdown */}
      {activeTab === 'subject_wise' && (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Section</th>
                  <th>Total Lectures Held</th>
                  <th>Total Attendance Records</th>
                  <th>Average Attendance / Session</th>
                </tr>
              </thead>
              <tbody>
                {subjectStats.map((sub, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600 }}>{sub.subject}</td>
                    <td><span className="badge badge-info">{sub.section}</span></td>
                    <td>{sub.total_sessions}</td>
                    <td><strong style={{ color: '#818cf8' }}>{sub.total_attendances_marked}</strong></td>
                    <td>{sub.average_attendance_per_session} students</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Daily Register */}
      {activeTab === 'daily' && (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Total Present</th>
                  <th>Sessions Conducted</th>
                  <th>Subjects Covered</th>
                </tr>
              </thead>
              <tbody>
                {dailyStats.map((d, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600 }}>{d.date}</td>
                    <td><strong style={{ color: '#10b981' }}>{d.total_present} students</strong></td>
                    <td>{d.total_sessions}</td>
                    <td>{d.subjects_covered.join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Monthly Trends */}
      {activeTab === 'monthly' && (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Total Attendances Logged</th>
                  <th>Sessions Completed</th>
                </tr>
              </thead>
              <tbody>
                {monthlyStats.map((m, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600 }}>{m.month}</td>
                    <td><strong style={{ color: '#818cf8' }}>{m.total_present} records</strong></td>
                    <td>{m.total_sessions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
