import React, { useState, useEffect } from 'react';
import {
  History,
  Search,
  Filter,
  Calendar,
  PlusCircle,
  Trash2,
  Download,
  CheckCircle2,
  FileSpreadsheet
} from 'lucide-react';
import { attendanceService } from '../services/attendanceService';
import { studentService } from '../services/studentService';
import { reportService } from '../services/reportService';
import { StatusBadge } from '../components/StatusBadge';
import { Modal } from '../components/Modal';
import { NotificationToast } from '../components/NotificationToast';
import { useAuth } from '../context/AuthContext';
import { StudentPunchHistory } from './StudentPunchHistory';

export const AttendanceHistory = () => {
  const { user } = useAuth();

  if (user?.role === 'student') {
    return <StudentPunchHistory />;
  }
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);

  // Filters
  const [dateFilter, setDateFilter] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [sectionFilter, setSectionFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Manual mark modal state
  const [manualModalOpen, setManualModalOpen] = useState(false);
  const [studentsList, setStudentsList] = useState([]);
  const [manualStudentId, setManualStudentId] = useState('');
  const [manualSubject, setManualSubject] = useState('Computer Vision');
  const [manualStatus, setManualStatus] = useState('present');
  const [manualDate, setManualDate] = useState(new Date().toISOString().slice(0, 10));

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const params = {};
      if (dateFilter) params.date = dateFilter;
      if (subjectFilter) params.subject = subjectFilter;
      if (sectionFilter) params.section = sectionFilter;
      if (statusFilter) params.status = statusFilter;

      const data = await attendanceService.getHistory(params);
      setRecords(data.records || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to load attendance history:', err);
      setToast({ message: 'Failed to load attendance history', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [sectionFilter, statusFilter]);

  const handleFilterSubmit = (e) => {
    e.preventDefault();
    fetchHistory();
  };

  const handleClearFilters = () => {
    setDateFilter('');
    setSubjectFilter('');
    setSectionFilter('');
    setStatusFilter('');
    fetchHistory();
  };

  const openManualModal = async () => {
    try {
      const data = await studentService.getStudents({ limit: 200 });
      setStudentsList(data.students || []);
      if (data.students && data.students.length > 0) {
        setManualStudentId(data.students[0].id);
      }
      setManualModalOpen(true);
    } catch (err) {
      setToast({ message: 'Failed to load students list', type: 'error' });
    }
  };

  const handleManualMarkSubmit = async (e) => {
    e.preventDefault();
    if (!manualStudentId || !manualSubject) return;

    try {
      await attendanceService.markManual({
        student_id: parseInt(manualStudentId, 10),
        subject: manualSubject.trim(),
        status: manualStatus,
        date: manualDate || undefined
      });
      setToast({ message: 'Attendance marked manually.', type: 'success' });
      setManualModalOpen(false);
      fetchHistory();
    } catch (err) {
      setToast({
        message: err.response?.data?.detail || 'Failed to mark manual attendance.',
        type: 'error'
      });
    }
  };

  const handleDeleteRecord = async (recordId) => {
    if (!window.confirm('Delete this attendance record?')) return;
    try {
      await attendanceService.deleteRecord(recordId);
      setToast({ message: 'Attendance record deleted.', type: 'success' });
      fetchHistory();
    } catch (err) {
      setToast({ message: 'Failed to delete record', type: 'error' });
    }
  };

  const handleExport = async (format) => {
    try {
      setToast({ message: `Generating ${format.toUpperCase()} export...`, type: 'info' });
      await reportService.downloadExport(format, 'detailed', {
        date: dateFilter || undefined,
        subject: subjectFilter || undefined,
        section: sectionFilter || undefined
      });
      setToast({ message: `${format.toUpperCase()} downloaded successfully!`, type: 'success' });
    } catch (err) {
      setToast({ message: 'Export generation failed', type: 'error' });
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
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>
            {user?.role === 'student' ? 'My Attendance History' : 'Attendance History & Registers'}
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
            {user?.role === 'student'
              ? 'View and filter your verified classroom punches and finalized session attendance records.'
              : 'Search, filter, verify, and export timestamped digital attendance records.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button onClick={() => handleExport('excel')} className="btn btn-secondary btn-sm">
            <FileSpreadsheet size={16} color="#10b981" />
            <span>Export Excel</span>
          </button>
          <button onClick={() => handleExport('csv')} className="btn btn-secondary btn-sm">
            <Download size={16} color="#0ea5e9" />
            <span>Export CSV</span>
          </button>
          {user?.role !== 'student' && (
            <button onClick={openManualModal} className="btn btn-primary btn-sm">
              <PlusCircle size={16} />
              <span>Manual Entry</span>
            </button>
          )}
        </div>
      </div>

      {/* Filter Bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1.25rem' }}>
        <form onSubmit={handleFilterSubmit} style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: 1, minWidth: '160px' }}>
            <label className="form-label">Filter by Date</label>
            <input
              type="date"
              className="form-input"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
            />
          </div>

          <div style={{ flex: 1.2, minWidth: '180px' }}>
            <label className="form-label">Filter by Subject</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Computer Vision"
              value={subjectFilter}
              onChange={(e) => setSubjectFilter(e.target.value)}
            />
          </div>

          <div style={{ width: '150px' }}>
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

          <div style={{ width: '140px' }}>
            <label className="form-label">Status</label>
            <select
              className="form-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="present">Present</option>
              <option value="absent">Absent</option>
            </select>
          </div>

          <button type="submit" className="btn btn-secondary">
            <Filter size={16} />
            <span>Apply</span>
          </button>

          {(dateFilter || subjectFilter || sectionFilter || statusFilter) && (
            <button type="button" onClick={handleClearFilters} className="btn btn-secondary btn-sm" style={{ padding: '0.65rem' }}>
              Reset
            </button>
          )}
        </form>
      </div>

      {/* History Data Table */}
      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            Showing <strong>{records.length}</strong> of <strong>{total}</strong> attendance entries
          </span>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Roll No</th>
                <th>Student Name</th>
                <th>Section</th>
                <th>Subject</th>
                <th>Status</th>
                <th>Date</th>
                <th>Time</th>
                <th>Confidence</th>
                <th style={{ textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    Loading attendance records...
                  </td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    No attendance records found matching the specified criteria.
                  </td>
                </tr>
              ) : (
                records.map((rec) => (
                  <tr key={rec.id}>
                    <td>
                      <code>{rec.roll_number}</code>
                    </td>
                    <td style={{ fontWeight: 600 }}>{rec.student_name}</td>
                    <td><span className="badge badge-info">{rec.section}</span></td>
                    <td>{rec.subject}</td>
                    <td><StatusBadge status={rec.status} /></td>
                    <td>{rec.date}</td>
                    <td>{rec.time}</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                      {rec.confidence_score != null ? `${rec.confidence_score.toFixed(1)} dist` : 'Manual'}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {user?.role !== 'student' ? (
                        <button
                          onClick={() => handleDeleteRecord(rec.id)}
                          className="btn btn-danger btn-sm"
                          title="Delete Record"
                          style={{ padding: '0.35rem 0.55rem' }}
                        >
                          <Trash2 size={13} />
                        </button>
                      ) : (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Manual Attendance Modal */}
      <Modal
        isOpen={manualModalOpen}
        onClose={() => setManualModalOpen(false)}
        title="Manual Attendance Entry / Override"
      >
        <form onSubmit={handleManualMarkSubmit}>
          <div className="form-group">
            <label className="form-label">Select Student *</label>
            <select
              className="form-select"
              value={manualStudentId}
              onChange={(e) => setManualStudentId(e.target.value)}
              required
            >
              {studentsList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.roll_number} - {s.name} ({s.section})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Subject *</label>
            <input
              type="text"
              className="form-input"
              value={manualSubject}
              onChange={(e) => setManualSubject(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Attendance Date</label>
              <input
                type="date"
                className="form-input"
                value={manualDate}
                onChange={(e) => setManualDate(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Status</label>
              <select
                className="form-select"
                value={manualStatus}
                onChange={(e) => setManualStatus(e.target.value)}
              >
                <option value="present">Present</option>
                <option value="absent">Absent</option>
              </select>
            </div>
          </div>

          <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button type="button" onClick={() => setManualModalOpen(false)} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Log Attendance Record
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
