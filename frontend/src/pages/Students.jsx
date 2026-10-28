import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Users,
  UserPlus,
  Search,
  Filter,
  Trash2,
  Camera,
  Eye,
  AlertCircle,
  CheckCircle2,
  Image as ImageIcon
} from 'lucide-react';
import { studentService } from '../services/studentService';
import { StatusBadge } from '../components/StatusBadge';
import { Modal } from '../components/Modal';
import { WebcamCapture } from '../components/WebcamCapture';
import { NotificationToast } from '../components/NotificationToast';

export const Students = () => {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [sectionFilter, setSectionFilter] = useState('');
  const [toast, setToast] = useState(null);

  // Selected student for details or sample upload modal
  const [viewStudent, setViewStudent] = useState(null);
  const [captureModalStudent, setCaptureModalStudent] = useState(null);
  const [capturedImages, setCapturedImages] = useState([]);
  const [uploadingSamples, setUploadingSamples] = useState(false);
  const [deleteConfirmStudent, setDeleteConfirmStudent] = useState(null);

  const fetchStudents = async () => {
    try {
      setLoading(true);
      const params = {};
      if (search) params.search = search;
      if (sectionFilter) params.section = sectionFilter;
      const data = await studentService.getStudents(params);
      setStudents(data.students || []);
    } catch (err) {
      console.error('Failed to fetch students:', err);
      setToast({ message: 'Failed to load student directory', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStudents();
  }, [sectionFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchStudents();
  };

  const handleSaveAdditionalSamples = async () => {
    if (!captureModalStudent || capturedImages.length === 0) return;
    try {
      setUploadingSamples(true);
      const res = await studentService.uploadFaceSamplesBase64(
        captureModalStudent.id,
        capturedImages
      );
      setToast({ message: res.message || 'Face samples updated successfully!', type: 'success' });
      setCaptureModalStudent(null);
      setCapturedImages([]);
      fetchStudents();
    } catch (err) {
      setToast({
        message: err.response?.data?.detail || 'Failed to process face samples.',
        type: 'error'
      });
    } finally {
      setUploadingSamples(false);
    }
  };

  const handleDeleteStudent = async () => {
    if (!deleteConfirmStudent) return;
    try {
      await studentService.deleteStudent(deleteConfirmStudent.id);
      setToast({
        message: `Student ${deleteConfirmStudent.name} (${deleteConfirmStudent.roll_number}) deleted.`,
        type: 'success'
      });
      setDeleteConfirmStudent(null);
      fetchStudents();
    } catch (err) {
      setToast({
        message: err.response?.data?.detail || 'Failed to delete student.',
        type: 'error'
      });
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
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem',
        marginBottom: '2rem'
      }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Student Directory</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
            Manage registered students, view enrolled biometric samples, and update records.
          </p>
        </div>

        <Link to="/students/register" className="btn btn-primary">
          <UserPlus size={18} />
          <span>Register New Student</span>
        </Link>
      </div>

      {/* Filter and Search Bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '220px', position: 'relative' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Search by name, roll number, or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ paddingLeft: '2.5rem' }}
            />
            <Search size={16} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          </div>

          <div style={{ width: '180px' }}>
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
            <span>Search</span>
          </button>
        </form>
      </div>

      {/* Students Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Roll Number</th>
                <th>Student Name</th>
                <th>Section</th>
                <th>Email</th>
                <th>Face Samples</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    Loading student directory...
                  </td>
                </tr>
              ) : students.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    No students registered yet. Click "Register New Student" to enroll candidates.
                  </td>
                </tr>
              ) : (
                students.map((student) => (
                  <tr key={student.id}>
                    <td>
                      <code style={{
                        background: 'rgba(99, 102, 241, 0.15)',
                        color: '#818cf8',
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        fontWeight: 600
                      }}>
                        {student.roll_number}
                      </code>
                    </td>
                    <td style={{ fontWeight: 600 }}>{student.name}</td>
                    <td><span className="badge badge-info">{student.section}</span></td>
                    <td style={{ color: 'var(--text-secondary)' }}>{student.email || '—'}</td>
                    <td>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                        fontWeight: 600,
                        color: student.samples_count >= 3 ? '#10b981' : '#f59e0b'
                      }}>
                        <ImageIcon size={14} />
                        {student.samples_count} {student.samples_count === 1 ? 'sample' : 'samples'}
                      </span>
                    </td>
                    <td>
                      <StatusBadge
                        status={student.samples_count > 0 ? 'active' : 'warning'}
                        text={student.samples_count > 0 ? 'Enrolled' : 'No Samples'}
                      />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                        <button
                          onClick={() => setCaptureModalStudent(student)}
                          className="btn btn-secondary btn-sm"
                          title="Capture/Add Face Samples"
                        >
                          <Camera size={14} />
                          <span>Capture</span>
                        </button>
                        <button
                          onClick={() => setDeleteConfirmStudent(student)}
                          className="btn btn-danger btn-sm"
                          title="Delete Student"
                          style={{ padding: '0.4rem 0.6rem' }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Capture Additional Face Samples Modal */}
      <Modal
        isOpen={!!captureModalStudent}
        onClose={() => { setCaptureModalStudent(null); setCapturedImages([]); }}
        title={`Enroll Face Samples: ${captureModalStudent?.name} (${captureModalStudent?.roll_number})`}
        maxWidth="600px"
      >
        <div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            Capture 3 to 5 images in different facial expressions and slight head rotations.
          </p>

          <WebcamCapture
            onCaptureComplete={(imgs) => setCapturedImages(imgs)}
            maxImages={5}
            requiredImages={3}
          />

          <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="button"
              onClick={() => { setCaptureModalStudent(null); setCapturedImages([]); }}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveAdditionalSamples}
              disabled={capturedImages.length === 0 || uploadingSamples}
              className="btn btn-primary"
            >
              {uploadingSamples ? 'Processing Samples...' : `Save ${capturedImages.length} Samples & Enroll`}
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deleteConfirmStudent}
        onClose={() => setDeleteConfirmStudent(null)}
        title="Confirm Student Deregistration"
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', color: '#f87171' }}>
            <AlertCircle size={28} style={{ flexShrink: 0 }} />
            <div>
              <p style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                Are you sure you want to delete {deleteConfirmStudent?.name}?
              </p>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                This will permanently remove the student's records, attendance logs, and delete all associated facial biometric samples from the server disk.
              </p>
            </div>
          </div>

          <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="button"
              onClick={() => setDeleteConfirmStudent(null)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleDeleteStudent}
              className="btn btn-danger"
            >
              Confirm Delete
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
