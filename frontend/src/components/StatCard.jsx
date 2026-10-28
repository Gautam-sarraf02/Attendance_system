import React from 'react';

export const StatCard = ({ title, value, subtext, icon: Icon, color = 'primary', badgeText }) => {
  const colorMap = {
    primary: {
      bg: '#eff6ff',
      text: '#1e3a8a',
      iconColor: '#2563eb'
    },
    success: {
      bg: '#f0fdf4',
      text: '#166534',
      iconColor: '#16a34a'
    },
    warning: {
      bg: '#fffbeb',
      text: '#92400e',
      iconColor: '#d97706'
    },
    danger: {
      bg: '#fef2f2',
      text: '#991b1b',
      iconColor: '#dc2626'
    },
    info: {
      bg: '#f0f9ff',
      text: '#075985',
      iconColor: '#0284c7'
    }
  };

  const scheme = colorMap[color] || colorMap.primary;

  return (
    <div className="card" style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      padding: '1.25rem 1.4rem'
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <div>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {title}
          </span>
          <div style={{ fontSize: '1.85rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.2rem', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
            {value}
          </div>
        </div>
        <div style={{
          padding: '0.6rem',
          borderRadius: 'var(--radius-md)',
          background: scheme.bg,
          color: scheme.iconColor,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          {Icon && <Icon size={20} />}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid #f1f5f9' }}>
        {subtext && (
          <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
            {subtext}
          </span>
        )}
        {badgeText && (
          <span style={{
            fontSize: '0.7rem',
            fontWeight: 700,
            padding: '0.15rem 0.45rem',
            borderRadius: '4px',
            background: scheme.bg,
            color: scheme.text
          }}>
            {badgeText}
          </span>
        )}
      </div>
    </div>
  );
};

export default StatCard;
