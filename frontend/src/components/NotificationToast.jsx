import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export const NotificationToast = ({ message, type = 'success', onClose }) => {
  if (!message) return null;

  const bgStyles = {
    success: { bg: '#ffffff', border: '#bbf7d0', icon: CheckCircle2, text: '#166534', iconColor: '#16a34a' },
    error: { bg: '#ffffff', border: '#fecaca', icon: AlertCircle, text: '#991b1b', iconColor: '#dc2626' },
    info: { bg: '#ffffff', border: '#bae6fd', icon: Info, text: '#075985', iconColor: '#0284c7' },
    warning: { bg: '#ffffff', border: '#fde68a', icon: AlertCircle, text: '#92400e', iconColor: '#d97706' }
  };

  const style = bgStyles[type] || bgStyles.info;
  const Icon = style.icon;

  return (
    <div style={{
      position: 'fixed',
      bottom: '1.5rem',
      right: '1.5rem',
      zIndex: 9999,
      background: style.bg,
      border: `1px solid ${style.border}`,
      color: style.text,
      padding: '0.85rem 1.25rem',
      borderRadius: 'var(--radius-md)',
      boxShadow: '0 4px 14px rgba(0, 0, 0, 0.1)',
      display: 'flex',
      alignItems: 'center',
      gap: '0.75rem',
      maxWidth: '420px'
    }}>
      <Icon size={18} color={style.iconColor} style={{ flexShrink: 0 }} />
      <span style={{ fontSize: '0.875rem', fontWeight: 600, flex: 1, color: '#1e293b' }}>{message}</span>
      {onClose && (
        <button onClick={onClose} style={{ color: '#94a3b8', cursor: 'pointer', padding: '2px' }}>
          <X size={15} />
        </button>
      )}
    </div>
  );
};

export default NotificationToast;
