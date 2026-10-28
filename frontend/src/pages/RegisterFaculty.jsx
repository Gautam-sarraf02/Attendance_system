import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  UserCheck,
  Camera,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  BookOpen,
  Calendar,
  Lock,
  Mail,
  User,
  Hash,
  Sparkles,
  Layers,
  RefreshCw,
  Eye,
  EyeOff
} from 'lucide-react';
import { authService } from '../services/authService';
import { academicService } from '../services/academicService';
import { enrollmentService } from '../services/enrollmentService';
import { WebcamCapture } from '../components/WebcamCapture';
import { NotificationToast } from '../components/NotificationToast';

export const RegisterFaculty = () => {
  const navigate = useNavigate();

  // Form State
  const [facultyId, setFacultyId] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [role, setRole] = useState('faculty');
  const [isActive, setIsActive] = useState(true);

  // Teaching Assignments
  const [availableSubjects, setAvailableSubjects] = useState([]);
  const [selectedSubjectIds, setSelectedSubjectIds] = useState([]);
  const [selectedSections, setSelectedSections] = useState(['A']);
  const [academicYears, setAcademicYears] = useState([]);
  const [selectedAcademicYearId, setSelectedAcademicYearId] = useState('');

  // Camera & Biometrics State
  const [capturedImages, setCapturedImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [toast, setToast] = useState(null);
  const [successData, setSuccessData] = useState(null);

  // Load available subjects and academic years
  useEffect(() => {
    const loadMetadata = async () => {
      try {
        setLoadingMeta(true);
        const [subList, ayList] = await Promise.all([
          academicService.getSubjects().catch(() => []),
          academicService.getAcademicYears().catch(() => [])
        ]);
        setAvailableSubjects(subList || []);
        setAcademicYears(ayList || []);

        // Default to active / current academic year
        const currentAy = ayList.find((y) => y.is_current) || ayList[0];
        if (currentAy) {
          setSelectedAcademicYearId(String(currentAy.id));
        }
      } catch (err) {
        console.warn('Metadata load note:', err);
      } finally {
        setLoadingMeta(false);
      }
    };
    loadMetadata();
  }, []);

  const handleToggleSubject = (subjectId) => {
    setSelectedSubjectIds((prev) =>
      prev.includes(subjectId) ? prev.filter((id) => id !== subjectId) : [...prev, subjectId]
    );
  };

  const handleToggleSection = (sec) => {
    setSelectedSections((prev) =>
      prev.includes(sec) ? prev.filter((s) => s !== sec) : [...prev, sec]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validations
    if (!facultyId.trim()) {
      setToast({ message: 'Faculty ID is required and must be unique.', type: 'warning' });
      return;
    }
    if (!fullName.trim()) {
      setToast({ message: 'Faculty full name is required.', type: 'warning' });
      return;
    }
    if (!username.trim()) {
      setToast({ message: 'Login username is required.', type: 'warning' });
      return;
    }
    if (!password || password.length < 8) {
      setToast({ message: 'Password must be at least 8 characters long.', type: 'warning' });
      return;
    }
    if (capturedImages.length < 3) {
      setToast({
        message: 'Please capture at least 3 face samples via the webcam before submitting.',
        type: 'warning'
      });
      return;
    }
    if (!selectedAcademicYearId) {
      setToast({ message: 'Please select an academic year for facial enrollment validity.', type: 'warning' });
      return;
    }

    try {
      setLoading(true);

      // 1. Create Faculty Account
      const facultyData = {
        faculty_id: facultyId.trim().toUpperCase(),
        username: username.trim(),
        full_name: fullName.trim(),
        email: email.trim() || undefined,
        password: password,
        role: role,
        is_active: isActive,
        assigned_subject_ids: selectedSubjectIds.length > 0 ? selectedSubjectIds : undefined,
        assigned_sections: selectedSections.length > 0 ? selectedSections : undefined
      };

      const newFaculty = await authService.createFaculty(facultyData);

      // 2. Register Biometric Face Samples via Camera
      const enrollPayload = {
        academic_year_id: parseInt(selectedAcademicYearId, 10),
        user_id: newFaculty.id,
        images: capturedImages,
        notes: `Admin enrolled biometrics for ${newFaculty.full_name} (${newFaculty.faculty_id})`
      };

      const enrollResult = await enrollmentService.registerFaceCamera(enrollPayload);

      // 3. Display Success Confirmation
      setSuccessData({
        faculty: newFaculty,
        enrollment: enrollResult,
        samplesCount: enrollResult.samples_saved || capturedImages.length
      });

      setToast({
        message: `Faculty ${newFaculty.full_name} (${newFaculty.faculty_id}) successfully registered and biometrics enrolled!`,
        type: 'success'
      });
    } catch (err) {
      console.error('Faculty registration failed:', err);
      const detail = err.response?.data?.detail;
      setToast({
        message: typeof detail === 'string' ? detail : 'Registration failed. Check if Faculty ID or username already exists.',
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFacultyId('');
    setFullName('');
    setEmail('');
    setUsername('');
    setPassword('');
    setSelectedSubjectIds([]);
    setSelectedSections(['A']);
    setCapturedImages([]);
    setSuccessData(null);
  };

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto', paddingBottom: '3rem' }}>
      {toast && (
        <NotificationToast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Header & Breadcrumb */}
      <div style={{ marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
          <Link to="/admin" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Admin Hub</Link>
          <span>/</span>
          <span style={{ color: 'var(--primary)', fontWeight: 600 }}>Register Faculty</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <UserCheck size={28} color="#243B64" /> Register Faculty Member
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', marginTop: '0.2rem' }}>
              Provision faculty credentials, set course teaching permissions, and capture live webcam facial biometrics.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Link to="/admin" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
              <ShieldCheck size={16} /> Admin Hub
            </Link>
            <Link to="/students/register" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
              Register Student
            </Link>
          </div>
        </div>
      </div>

      {/* Success View */}
      {successData ? (
        <div className="card" style={{ maxWidth: '720px', margin: '2rem auto', textAlign: 'center', padding: '2.5rem 2rem' }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            background: '#ecfdf5',
            color: '#059669',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1.25rem'
          }}>
            <CheckCircle2 size={36} />
          </div>

          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#065f46', marginBottom: '0.5rem' }}>
            Faculty Biometrics Registered!
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1.75rem' }}>
            Faculty account <strong>{successData.faculty.full_name}</strong> is active with secure facial credentials for classroom session verification.
          </p>

          <div style={{
            background: '#f8fafc',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-md)',
            padding: '1.25rem',
            textAlign: 'left',
            marginBottom: '1.75rem'
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Faculty ID</span>
                <div style={{ fontSize: '1.05rem', fontWeight: 700, fontFamily: 'monospace', color: 'var(--primary)' }}>
                  {successData.faculty.faculty_id}
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Login Username</span>
                <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {successData.faculty.username}
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Official Email</span>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                  {successData.faculty.email || 'Not specified'}
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Face Biometrics</span>
                <div>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                    background: '#d1fae5',
                    color: '#065f46',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    padding: '0.2rem 0.55rem',
                    borderRadius: '12px'
                  }}>
                    <Sparkles size={12} /> Active ({successData.samplesCount} samples)
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button onClick={handleReset} className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
              <RefreshCw size={16} /> Register Another Faculty
            </button>
            <Link to="/admin" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
              View in Faculty Directory <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      ) : (
        /* Registration & Enrollment Grid */
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 1fr) minmax(340px, 1fr)', gap: '1.75rem', alignItems: 'start' }}>
          {/* Left Form: Faculty Details */}
          <div className="card">
            <div className="card-header" style={{ marginBottom: '1.25rem' }}>
              <span className="card-title">
                <BookOpen size={18} color="#243B64" /> 1. Faculty Profile & Permissions
              </span>
            </div>

            <form onSubmit={handleSubmit} id="faculty-reg-form">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Faculty ID * (Unique)</label>
                  <div style={{ position: 'relative' }}>
                    <Hash size={16} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
                    <input
                      type="text"
                      className="form-input"
                      style={{ paddingLeft: '2.2rem', textTransform: 'uppercase', fontWeight: 600 }}
                      placeholder="e.g. FAC-KV01"
                      value={facultyId}
                      onChange={(e) => setFacultyId(e.target.value)}
                      required
                    />
                  </div>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Institutional identity number</span>
                </div>

                <div className="form-group">
                  <label className="form-label">Full Name *</label>
                  <div style={{ position: 'relative' }}>
                    <User size={16} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
                    <input
                      type="text"
                      className="form-input"
                      style={{ paddingLeft: '2.2rem' }}
                      placeholder="e.g. Kavita Ma'am"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Login Username *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. kavita_maam"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                  />
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Used to sign in to faculty portal</span>
                </div>

                <div className="form-group">
                  <label className="form-label">Official Email</label>
                  <div style={{ position: 'relative' }}>
                    <Mail size={16} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
                    <input
                      type="email"
                      className="form-input"
                      style={{ paddingLeft: '2.2rem' }}
                      placeholder="kavita@acasportal.edu"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Login Password * (Min 8 chars)</label>
                <div style={{ position: 'relative' }}>
                  <Lock size={16} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    className="form-input"
                    style={{ paddingLeft: '2.2rem', paddingRight: '2.5rem' }}
                    placeholder="••••••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      top: '8px',
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer'
                    }}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Stored as cryptographically secure bcrypt hash</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '0.5rem' }}>
                <div className="form-group">
                  <label className="form-label">System Role</label>
                  <select className="form-input" value={role} onChange={(e) => setRole(e.target.value)}>
                    <option value="faculty">Faculty Member</option>
                    <option value="teacher">Instructor / Teacher</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Academic Year Validity *</label>
                  <select
                    className="form-input"
                    value={selectedAcademicYearId}
                    onChange={(e) => setSelectedAcademicYearId(e.target.value)}
                    required
                  >
                    {academicYears.map((ay) => (
                      <option key={ay.id} value={ay.id}>
                        {ay.name} {ay.is_current ? '(Current Active)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Teaching Subject Assignment */}
              <div style={{ marginTop: '0.75rem', padding: '0.85rem', background: '#f8fafc', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                <label className="form-label" style={{ marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Layers size={15} color="var(--primary)" /> Teaching Subject Assignments (Optional)
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', maxHeight: '110px', overflowY: 'auto', padding: '0.2rem 0' }}>
                  {availableSubjects.map((sub) => {
                    const isSelected = selectedSubjectIds.includes(sub.id);
                    return (
                      <button
                        type="button"
                        key={sub.id}
                        onClick={() => handleToggleSubject(sub.id)}
                        style={{
                          fontSize: '0.75rem',
                          padding: '0.25rem 0.6rem',
                          borderRadius: '16px',
                          border: isSelected ? '1px solid #3b82f6' : '1px solid #cbd5e1',
                          background: isSelected ? '#eff6ff' : '#ffffff',
                          color: isSelected ? '#1d4ed8' : '#475569',
                          fontWeight: isSelected ? 700 : 500,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem'
                        }}
                      >
                        {isSelected && <CheckCircle2 size={12} color="#1d4ed8" />}
                        {sub.name}
                      </button>
                    );
                  })}
                  {availableSubjects.length === 0 && (
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No subjects found. Create subjects in Admin Hub.</span>
                  )}
                </div>

                {/* Section Permissions */}
                <div style={{ marginTop: '0.75rem' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, display: 'block', marginBottom: '0.3rem' }}>
                    Authorized Sections:
                  </span>
                  <div style={{ display: 'flex', gap: '1rem' }}>
                    {['A', 'B', 'C'].map((sec) => (
                      <label key={sec} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={selectedSections.includes(sec)}
                          onChange={() => handleToggleSection(sec)}
                        />
                        Section {sec}
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <input
                  type="checkbox"
                  id="account-active-check"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                />
                <label htmlFor="account-active-check" style={{ fontSize: '0.85rem', cursor: 'pointer', userSelect: 'none' }}>
                  Account is active immediately upon registration
                </label>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '1.25rem', padding: '0.75rem', fontWeight: 700 }}
              >
                {loading ? 'Registering & Enrolling...' : 'Register Faculty & Save Biometrics'}
              </button>
            </form>
          </div>

          {/* Right Column: Live Camera Biometrics */}
          <div className="card">
            <div className="card-header" style={{ marginBottom: '1rem' }}>
              <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Camera size={18} color="#243B64" /> 2. Live Webcam Face Enrollment
              </span>
              <span style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                color: capturedImages.length >= 3 ? '#059669' : '#b45309',
                background: capturedImages.length >= 3 ? '#d1fae5' : '#fef3c7',
                padding: '0.2rem 0.55rem',
                borderRadius: '12px'
              }}>
                {capturedImages.length}/5 Captured {capturedImages.length >= 3 ? '✓ (Ready)' : '(Min 3 req)'}
              </span>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                Position the faculty member in front of the camera with good illumination. Capture 3 to 5 clear samples from slightly different angles (center, slight left, slight right) for accurate LBPH recognition.
              </p>

              <WebcamCapture
                onCaptureComplete={(images) => setCapturedImages(images)}
                maxImages={5}
                requiredImages={3}
              />
            </div>

            <div style={{
              background: '#f8fafc',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-md)',
              padding: '0.85rem',
              fontSize: '0.8rem',
              color: 'var(--text-secondary)'
            }}>
              <strong style={{ color: 'var(--primary)', display: 'block', marginBottom: '0.25rem' }}>
                Biometric Protection Guarantee:
              </strong>
              • Face representations are processed locally and securely stored with restricted file permissions.<br />
              • Raw embeddings and live camera feeds are strictly excluded from public API responses.<br />
              • Captured models are automatically verified with Anti-Spoofing before attendance session authorization.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RegisterFaculty;
