import React, { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  Sliders,
  CheckCircle2,
  Database,
  Cpu,
  ShieldCheck,
  HardDrive,
  Info,
  Server
} from 'lucide-react';
import { modelService } from '../services/modelService';
import { PrivacyNotice } from '../components/PrivacyNotice';
import { NotificationToast } from '../components/NotificationToast';

export const Settings = () => {
  const [threshold, setThreshold] = useState(75.0);
  const [modelStatus, setModelStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        setLoading(true);
        const data = await modelService.getStatus();
        setModelStatus(data);
        if (data.confidence_threshold) {
          setThreshold(data.confidence_threshold);
        }
      } catch (err) {
        console.error('Failed to load settings:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchStatus();
  }, []);

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      await modelService.updateThreshold(threshold);
      setToast({ message: 'Recognition parameters saved successfully!', type: 'success' });
    } catch (err) {
      setToast({ message: 'Failed to update settings', type: 'error' });
    } finally {
      setSaving(false);
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
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>System Configuration & Diagnostics</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
          Tuning parameters, database diagnostics, biometric policies, and hardware setup.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem' }}>
        {/* Computer Vision Parameter Tuning */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Sliders size={18} color="#6366f1" />
              Face Recognition Parameters
            </span>
          </div>

          <form onSubmit={handleSaveSettings}>
            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>LBPH Distance Threshold</span>
                <strong style={{ color: '#818cf8' }}>{threshold.toFixed(1)}</strong>
              </label>
              <input
                type="range"
                min="30"
                max="120"
                step="1"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: '#6366f1', cursor: 'pointer' }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginTop: '0.25rem' }}>
                Lower values require closer facial match (strict). Higher values increase recall (lenient).
              </span>
            </div>

            <div className="form-group">
              <label className="form-label">Active Face Detector</label>
              <input
                type="text"
                className="form-input"
                value="Haar Cascade (haarcascade_frontalface_default.xml)"
                disabled
              />
            </div>

            <div className="form-group">
              <label className="form-label">Recognition Algorithm</label>
              <input
                type="text"
                className="form-input"
                value="OpenCV LBPHFaceRecognizer (8-neighbor circular, 200x200 ROI)"
                disabled
              />
            </div>

            <button type="submit" disabled={saving} className="btn btn-primary" style={{ width: '100%' }}>
              <CheckCircle2 size={16} />
              <span>{saving ? 'Saving Parameters...' : 'Save Parameters'}</span>
            </button>
          </form>
        </div>

        {/* System Diagnostics */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Server size={18} color="#10b981" />
              Runtime Diagnostics
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.85rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Backend Framework</span>
              <strong style={{ color: 'var(--text-primary)' }}>FastAPI + Uvicorn (Python 3.13)</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Frontend Architecture</span>
              <strong style={{ color: 'var(--text-primary)' }}>React 19 + Vite</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Database Engine</span>
              <strong style={{ color: '#10b981' }}>SQLite 3 (Relational ORM via SQLAlchemy)</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>OpenCV Contrib Module</span>
              <strong style={{ color: '#818cf8' }}>cv2.face (LBPH Enabled)</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Haar Cascade XML Status</span>
              <strong style={{ color: '#10b981' }}>Loaded & Initialized</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Biometric Storage Path</span>
              <code style={{ fontSize: '0.75rem', color: '#94a3b8' }}>backend/data/faces/</code>
            </div>
          </div>
        </div>
      </div>

      <PrivacyNotice />
    </div>
  );
};
