import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  UserPlus,
  Camera,
  Upload,
  CheckCircle2,
  AlertCircle,
  Cpu,
  ArrowRight,
  ShieldAlert,
  Sparkles
} from 'lucide-react';
import { studentService } from '../services/studentService';
import { WebcamCapture } from '../components/WebcamCapture';
import { NotificationToast } from '../components/NotificationToast';

export const RegisterStudent = () => {
  const navigate = useNavigate();

  // Form State
  const [rollNumber, setRollNumber] = useState('');
  const [name, setName] = useState('');
  const [section, setSection] = useState('CSE-A');
  const [email, setEmail] = useState('');

  // Mode: 'webcam' or 'files'
  const [enrollMode, setEnrollMode] = useState('webcam');
  const [capturedImages, setCapturedImages] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [filePreviews, setFilePreviews] = useState([]);

  // Submission & UI states
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [successData, setSuccessData] = useState(null);

  const handleFilesChange = (e) => {
    const files = Array.from(e.target.files);
    setSelectedFiles(files);
    
    // Create local object URLs for previews
    const previews = files.map((file) => URL.createObjectURL(file));
    setFilePreviews(previews);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!rollNumber.trim() || !name.trim()) {
      setToast({ message: 'Roll number and student name are required.', type: 'error' });
      return;
    }

    if (enrollMode === 'webcam' && capturedImages.length < 3) {
      setToast({
        message: 'Please capture at least 3 face samples (different angles/expressions) for accurate recognition.',
        type: 'warning'
      });
      return;
    }

    if (enrollMode === 'files' && selectedFiles.length < 1) {
      setToast({ message: 'Please select at least 1 face image file.', type: 'warning' });
      return;
    }

    try {
      setLoading(true);
      
      // 1. Create Student record
      const student = await studentService.createStudent({
        roll_number: rollNumber.trim(),
        name: name.trim(),
        section: section.trim().toUpperCase(),
        email: email.trim() || undefined
      });

      // 2. Upload face samples
      let sampleResult = null;
      if (enrollMode === 'webcam') {
        sampleResult = await studentService.uploadFaceSamplesBase64(student.id, capturedImages);
      } else {
        const formData = new FormData();
        selectedFiles.forEach((f) => formData.append('files', f));
        sampleResult = await studentService.uploadFaceSamplesFiles(student.id, formData);
      }

      setSuccessData({
        student,
        samplesCount: sampleResult.samples_saved || capturedImages.length || selectedFiles.length
      });

      setToast({
        message: `Student ${student.name} successfully registered with ${sampleResult.samples_saved} face samples!`,
        type: 'success'
      });

    } catch (err) {
      console.error('Registration failed:', err);
      const detail = err.response?.data?.detail;
      setToast({
        message: typeof detail === 'string' ? detail : 'Registration failed. Check if roll number already exists.',
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleResetForm = () => {
    setRollNumber('');
    setName('');
    setSection('CSE-A');
    setEmail('');
    setCapturedImages([]);
    setSelectedFiles([]);
    setFilePreviews([]);
    setSuccessData(null);
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
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Student Registration & Face Enrollment</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
          Enroll student profile and capture 3-5 facial biometric samples for OpenCV LBPH training.
        </p>
      </div>

      {successData ? (
        /* Success Confirmation Card */
        <div className="card" style={{ maxWidth: '650px', margin: '2rem auto', textAlign: 'center', padding: '3rem 2rem' }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            background: 'rgba(16, 185, 129, 0.15)',
            color: '#10b981',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '1.25rem'
          }}>
            <CheckCircle2 size={36} />
          </div>

          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            Student Registered Successfully!
          </h2>

          <div style={{
            background: 'rgba(15, 23, 42, 0.6)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-md)',
            padding: '1.25rem',
            margin: '1.5rem 0',
            textAlign: 'left'
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.9rem' }}>
              <div>Student Name: <strong style={{ color: 'var(--text-primary)' }}>{successData.student.name}</strong></div>
              <div>Roll Number: <strong style={{ color: '#818cf8' }}>{successData.student.roll_number}</strong></div>
              <div>Section: <strong style={{ color: 'var(--text-primary)' }}>{successData.student.section}</strong></div>
              <div>Face Samples Saved: <strong style={{ color: '#10b981' }}>{successData.samplesCount} photos</strong></div>
            </div>
          </div>

          <p style={{ fontSize: '0.85rem', color: '#f59e0b', marginBottom: '1.75rem' }}>
            <Sparkles size={16} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />
            Remember to <strong>Train the Face Model</strong> before running live classroom attendance so the new face samples are compiled!
          </p>

          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button onClick={handleResetForm} className="btn btn-secondary">
              <UserPlus size={16} /> Register Another Student
            </button>
            <Link to="/model" className="btn btn-primary">
              <Cpu size={16} /> Go to Train Model <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      ) : (
        /* Registration Form & Biometric Capture */
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '2rem' }}>
          {/* Step 1: Student Information */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                <UserPlus size={18} color="#6366f1" />
                Step 1: Student Information
              </span>
            </div>

            <form id="register-form" onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label" htmlFor="roll">Roll Number *</label>
                <input
                  id="roll"
                  type="text"
                  className="form-input"
                  placeholder="e.g. 11242211"
                  value={rollNumber}
                  onChange={(e) => setRollNumber(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="name">Full Name *</label>
                <input
                  id="name"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Gurpreet Maan"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="section">Section / Batch *</label>
                <select
                  id="section"
                  className="form-select"
                  value={section}
                  onChange={(e) => setSection(e.target.value)}
                  required
                >
                  <option value="CSE-A">CSE-A</option>
                  <option value="CSE-B">CSE-B</option>
                  <option value="CSE-C">CSE-C</option>
                  <option value="IT-A">IT-A</option>
                  <option value="ECE-A">ECE-A</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="email">Email Address (Optional)</label>
                <input
                  id="email"
                  type="email"
                  className="form-input"
                  placeholder="e.g. gurpreet.m@college.edu"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div style={{
                padding: '1rem',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(99, 102, 241, 0.08)',
                border: '1px solid rgba(99, 102, 241, 0.2)',
                fontSize: '0.8rem',
                color: 'var(--text-secondary)'
              }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                  OpenCV Haar Cascade Pre-processing:
                </div>
                The backend automatically runs Haar face detection on each uploaded photo to crop, grayscale, and normalize the facial region (200x200) with histogram equalization.
              </div>
            </form>
          </div>

          {/* Step 2: Biometric Face Capture */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                <Camera size={18} color="#10b981" />
                Step 2: Face Sample Acquisition
              </span>
              
              {/* Mode Switcher */}
              <div style={{ display: 'flex', gap: '0.35rem', background: 'var(--bg-tertiary)', padding: '0.2rem', borderRadius: 'var(--radius-sm)' }}>
                <button
                  type="button"
                  onClick={() => setEnrollMode('webcam')}
                  className={`btn btn-sm ${enrollMode === 'webcam' ? 'btn-primary' : ''}`}
                  style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                >
                  <Camera size={13} /> Webcam
                </button>
                <button
                  type="button"
                  onClick={() => setEnrollMode('files')}
                  className={`btn btn-sm ${enrollMode === 'files' ? 'btn-primary' : ''}`}
                  style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                >
                  <Upload size={13} /> Upload
                </button>
              </div>
            </div>

            {enrollMode === 'webcam' ? (
              <div>
                <WebcamCapture
                  onCaptureComplete={(images) => setCapturedImages(images)}
                  maxImages={5}
                  requiredImages={3}
                />
              </div>
            ) : (
              <div>
                <label style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '2.5rem',
                  border: '2px dashed var(--border-color)',
                  borderRadius: 'var(--radius-lg)',
                  cursor: 'pointer',
                  background: 'rgba(15, 23, 42, 0.4)',
                  transition: 'border-color 0.2s'
                }}>
                  <Upload size={32} color="#6366f1" style={{ marginBottom: '0.75rem' }} />
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Select 3-5 Face Image Files</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    JPG, PNG, JPEG formats supported
                  </span>
                  <input
                    type="file"
                    multiple
                    accept="image/jpeg,image/png,image/jpg"
                    onChange={handleFilesChange}
                    style={{ display: 'none' }}
                  />
                </label>

                {filePreviews.length > 0 && (
                  <div style={{ marginTop: '1rem' }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.5rem' }}>
                      Selected Files ({filePreviews.length}):
                    </span>
                    <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.5rem' }}>
                      {filePreviews.map((src, i) => (
                        <img
                          key={i}
                          src={src}
                          alt="preview"
                          style={{
                            width: '60px',
                            height: '60px',
                            borderRadius: '8px',
                            objectFit: 'cover',
                            border: '1px solid #6366f1'
                          }}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Submit Action */}
            <div style={{ marginTop: '2rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-color)' }}>
              <button
                type="submit"
                form="register-form"
                disabled={loading}
                className="btn btn-primary"
                style={{ width: '100%', padding: '0.85rem', fontSize: '0.95rem' }}
              >
                <UserPlus size={18} />
                <span>{loading ? 'Validating Faces & Enrolling...' : 'Complete Student Registration'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
