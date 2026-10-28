import React from 'react';

export const StatusBadge = ({ status, text }) => {
  const norm = (status || '').toLowerCase();
  
  if (norm === 'present' || norm === 'active' || norm === 'trained' || norm === 'success') {
    return <span className="badge badge-success">{text || status}</span>;
  }
  if (norm === 'absent' || norm === 'failed' || norm === 'error') {
    return <span className="badge badge-danger">{text || status}</span>;
  }
  if (norm === 'unknown' || norm === 'warning' || norm === 'untrained' || norm === 'not trained') {
    return <span className="badge badge-warning">{text || status}</span>;
  }
  if (norm === 'completed' || norm === 'inactive') {
    return <span className="badge badge-info">{text || status}</span>;
  }
  
  return <span className="badge badge-primary">{text || status}</span>;
};
