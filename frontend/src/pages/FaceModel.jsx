import React, { useState, useEffect } from 'react';
import {
  Cpu,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  Sparkles,
  Sliders,
  ShieldCheck,
  Binary
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { modelService } from '../services/modelService';
import { StatusBadge } from '../components/StatusBadge';
import { NotificationToast } from '../components/NotificationToast';

export const FaceModel = () => {
  const [modelStatus, setModelStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [toast, setToast] = useState(null);
  const [trainingResult, setTrainingResult] = useState(null);
  const [threshold, setThreshold] = useState(75.0);
  const [savingThreshold, setSavingThreshold] = useState(false);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const data = await modelService.getStatus();
      setModelStatus(data);
      if (data.confidence_threshold) {
        setThreshold(data.confidence_threshold);
      }
    } catch (err) {
      console.error('Failed to get model status:', err);
      setToast({ message: 'Failed to load face model status', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleTrainModel = async () => {
    try {
      setTraining(true);
      setTrainingResult(null);
      const res = await modelService.trainModel();
      setTrainingResult(res);
      setToast({
        message: res.message || 'LBPH Face Model trained successfully!',
        type: 'success'
      });
      // Fire celebration confetti
      confetti({
        particleCount: 80,
        spread: 60,
        origin: { y: 0.6 }
      });
      fetchStatus();
    } catch (err) {
      console.error('Training failed:', err);
      const detail = err.response?.data?.detail || 'Model training failed.';
      setToast({ message: detail, type: 'error' });
    } finally {
      setTraining(false);
    }
  };

  const handleThresholdSave = async () => {
    try {
      setSavingThreshold(true);
      await modelService.updateThreshold(threshold);
      setToast({
        message: `Recognition distance threshold updated to ${threshold}`,
        type: 'success'
      });
      fetchStatus();
    } catch (err) {
      setToast({ message: 'Failed to update threshold', type: 'error' });
    } finally {
      setSavingThreshold(false);
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
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Face Recognition Model Management</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
          OpenCV LBPH (Local Binary Patterns Histograms) Model Training & Threshold Tuning
        </p>
      </div>

      {/* Model Status Card & Quick Action */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        {/* Status Details */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Cpu size={18} color="#6366f1" />
              Active Classifier Status
            </span>
            <StatusBadge
              status={modelStatus?.is_trained ? 'trained' : 'untrained'}
              text={modelStatus?.is_trained ? 'Trained & Ready' : 'Not Trained'}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.875rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Algorithm</span>
              <strong style={{ color: 'var(--text-primary)' }}>OpenCV LBPH</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Face Detector</span>
              <strong style={{ color: 'var(--text-primary)' }}>Haar Cascade Frontal Face</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Total Enrolled Students</span>
              <strong style={{ color: 'var(--text-primary)' }}>{modelStatus?.total_students_enrolled || 0} students</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Students with Face Samples</span>
              <strong style={{ color: '#10b981' }}>{modelStatus?.total_students_with_samples || 0} students</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Total Biometric Samples</span>
              <strong style={{ color: '#818cf8' }}>{modelStatus?.total_samples || 0} samples</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Last Trained</span>
              <strong style={{ color: 'var(--text-primary)' }}>
                {modelStatus?.last_trained ? new Date(modelStatus.last_trained).toLocaleString() : 'Never'}
              </strong>
            </div>
          </div>

          {/* Train Button */}
          <div style={{ marginTop: '1.75rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-color)' }}>
            <button
              onClick={handleTrainModel}
              disabled={training || (modelStatus?.total_samples || 0) === 0}
              className="btn btn-primary"
              style={{ width: '100%', padding: '0.85rem', fontSize: '1rem' }}
            >
              <RefreshCw size={18} className={training ? 'spin' : ''} />
              <span>{training ? 'Compiling LBPH Histograms...' : 'Train / Re-train Face Model'}</span>
            </button>
            {(modelStatus?.total_samples || 0) === 0 && (
              <span style={{ fontSize: '0.75rem', color: '#f59e0b', display: 'block', textAlign: 'center', marginTop: '0.5rem' }}>
                Register students with face samples first before training.
              </span>
            )}
          </div>
        </div>

        {/* Confidence Threshold Tuning */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Sliders size={18} color="#0ea5e9" />
              Recognition Distance Threshold
            </span>
            <span className="badge badge-info">{threshold.toFixed(1)}</span>
          </div>

          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
            In OpenCV LBPH, confidence represents <strong>histogram Chi-square distance</strong>. A <em>lower value</em> means closer facial similarity. If distance exceeds the threshold, the student is classified as <strong>"Unknown"</strong>.
          </p>

          <div style={{ marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
              <span>Strict Match (40.0)</span>
              <span style={{ color: '#818cf8', fontWeight: 700 }}>Current: {threshold.toFixed(1)}</span>
              <span>Lenient Match (100.0)</span>
            </div>
            <input
              type="range"
              min="35"
              max="110"
              step="1"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: '#6366f1', cursor: 'pointer' }}
            />
          </div>

          <div style={{
            background: 'rgba(15, 23, 42, 0.6)',
            padding: '1rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-color)',
            fontSize: '0.8rem',
            color: 'var(--text-secondary)',
            marginBottom: '1.25rem'
          }}>
            <div><strong>Recommended Threshold:</strong> 65.0 – 78.0 for standard classroom webcam lighting.</div>
          </div>

          <button
            onClick={handleThresholdSave}
            disabled={savingThreshold}
            className="btn btn-secondary btn-sm"
            style={{ width: '100%' }}
          >
            <CheckCircle2 size={16} />
            <span>{savingThreshold ? 'Saving...' : 'Apply Threshold'}</span>
          </button>
        </div>
      </div>

      {/* Latest Training Result Feedback */}
      {trainingResult && (
        <div className="card" style={{
          marginBottom: '2rem',
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(99, 102, 241, 0.12))',
          border: '1px solid rgba(16, 185, 129, 0.4)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#10b981', marginBottom: '0.5rem' }}>
            <CheckCircle2 size={22} />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Model Successfully Trained & Saved to Disk</h3>
          </div>
          <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', marginTop: '0.75rem' }}>
            <div>Students Included: <strong>{trainingResult.students_trained}</strong></div>
            <div>Sample Images Used: <strong>{trainingResult.samples_used}</strong></div>
            <div>Training Time: <strong>{trainingResult.training_time_seconds} seconds</strong></div>
            <div>Model File: <code>backend/data/models/lbph_model.xml</code></div>
          </div>
        </div>
      )}

      {/* Theoretical & Technical Architecture Breakdown (Synopsis Alignment) */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Binary size={18} color="#f59e0b" />
            Methodology & Technical Pipeline (B.Tech CSE Project Scope)
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1.5rem', fontSize: '0.85rem' }}>
          <div style={{ padding: '1rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ fontWeight: 700, color: '#818cf8', marginBottom: '0.5rem' }}>1. Image Acquisition</div>
            <p style={{ color: 'var(--text-secondary)' }}>
              Real-time video frames are captured through the classroom webcam via browser HTML5 MediaDevices API at controlled intervals (1 frame / 1.2s).
            </p>
          </div>

          <div style={{ padding: '1rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '0.5rem' }}>2. Face Detection (Haar)</div>
            <p style={{ color: 'var(--text-secondary)' }}>
              Frames are converted to grayscale and equalized. OpenCV Haar Cascade detects all simultaneous faces in the classroom and extracts ROIs.
            </p>
          </div>

          <div style={{ padding: '1rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ fontWeight: 700, color: '#34d399', marginBottom: '0.5rem' }}>3. Feature Extraction (LBPH)</div>
            <p style={{ color: 'var(--text-secondary)' }}>
              Local Binary Pattern operator labels 8-neighbor circular pixels by thresholding center values into binary patterns and histograms.
            </p>
          </div>

          <div style={{ padding: '1rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ fontWeight: 700, color: '#fbbf24', marginBottom: '0.5rem' }}>4. Matching & Marking</div>
            <p style={{ color: 'var(--text-secondary)' }}>
              Chi-square distance compares candidate histograms against trained database models. Verified students are marked present with duplicate protection.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
