import React from 'react';
import { Lock } from 'lucide-react';

export const PrivacyNotice = () => {
  return (
    <div style={{
      background: '#f8fafc',
      border: '1px solid var(--border-color)',
      borderRadius: 'var(--radius-md)',
      padding: '0.85rem 1.15rem',
      display: 'flex',
      alignItems: 'flex-start',
      gap: '0.75rem',
      fontSize: '0.8rem',
      color: 'var(--text-secondary)',
      lineHeight: 1.5,
      marginTop: '1.5rem'
    }}>
      <div style={{
        padding: '0.35rem',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--primary-light)',
        color: 'var(--primary)',
        flexShrink: 0
      }}>
        <Lock size={15} />
      </div>
      <div>
        <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '0.15rem', fontSize: '0.825rem' }}>
          Biometric Privacy & Local Host Compliance
        </strong>
        All facial biometric data and camera frames are processed on-premise. Face samples are stored in local storage and erased upon deregistration. No biometric data is transmitted to third-party cloud services.
      </div>
    </div>
  );
};

export default PrivacyNotice;
