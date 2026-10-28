import React, { useState, useEffect } from 'react';
import {
  Calendar,
  Clock,
  BookOpen,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
  Filter,
  Search,
  ShieldCheck,
  Send,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  CalendarCheck,
  UserCheck
} from 'lucide-react';
import { attendanceService } from '../services/attendanceService';
import { Modal } from '../components/Modal';
import { NotificationToast } from '../components/NotificationToast';

export const StudentPunchHistory = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [toast, setToast] = useState(null);

  // Filters for daily punch history
  const [monthFilter, setMonthFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [dateRangeFrom, setDateRangeFrom] = useState('');
  const [dateRangeTo, setDateRangeTo] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedDates, setExpandedDates] = useState({});

  // Correction Request Modal state
  const [correctionModalOpen, setCorrectionModalOpen] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [reasonCategory, setReasonCategory] = useState('Camera / Face Not Recognized');
  const [reasonDetails, setReasonDetails] = useState('');
  const [evidenceNote, setEvidenceNote] = useState('');
  const [submittingCorrection, setSubmittingCorrection] = useState(false);

  // Correction Requests List state
  const [myCorrections, setMyCorrections] = useState([]);
  const [activeTab, setActiveTab] = useState('punches'); // 'punches' | 'corrections'

  const fetchPunchData = async () => {
    try {
      setLoading(true);
      const dashData = await attendanceService.getStudentDashboard();
      setData(dashData);

      // Also fetch existing corrections for this student
      try {
        const correctionsData = await attendanceService.getCorrections();
        setMyCorrections(correctionsData || []);
      } catch (cErr) {
        console.warn('Could not load correction requests history:', cErr);
      }
    } catch (err) {
      console.error('Failed to load student punch history:', err);
      setToast({
        message: err.response?.data?.detail || 'Failed to load your attendance punch records.',
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPunchData();
  }, []);

  const openCorrectionModal = (record) => {
    setSelectedRecord(record);
    setReasonCategory('Camera / Face Not Recognized');
    setReasonDetails('');
    setEvidenceNote('');
    setCorrectionModalOpen(true);
  };

  const handleCorrectionSubmit = async (e) => {
    e.preventDefault();
    if (!reasonDetails.trim()) {
      setToast({ message: 'Please provide a detailed explanation for your correction request.', type: 'warning' });
      return;
    }

    try {
      setSubmittingCorrection(true);
      const payload = {
        session_id: selectedRecord?.session_id,
        student_id: data?.profile?.id,
        attendance_id: selectedRecord?.attendance_id || selectedRecord?.id || undefined,
        requested_status: 'present',
        reason: `[${reasonCategory}] ${reasonDetails.trim()}`,
        evidence_notes: evidenceNote.trim() || undefined
      };

      await attendanceService.submitCorrection(payload);
      setToast({
        message: 'Attendance correction request submitted successfully. Awaiting faculty/admin approval.',
        type: 'success'
      });
      setCorrectionModalOpen(false);

      // Refresh corrections list
      const correctionsData = await attendanceService.getCorrections();
      setMyCorrections(correctionsData || []);
    } catch (err) {
      console.error('Failed to submit correction:', err);
      setToast({
        message: err.response?.data?.detail || 'Failed to submit correction request.',
        type: 'error'
      });
    } finally {
      setSubmittingCorrection(false);
    }
  };

  if (loading && !data) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        gap: '1rem'
      }}>
        <div className="spin" style={{
          width: '44px',
          height: '44px',
          border: '3px solid rgba(99, 102, 241, 0.2)',
          borderTopColor: '#6366f1',
          borderRadius: '50%'
        }} />
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          Loading your biometric punch records...
        </span>
      </div>
    );
  }

  const profile = data?.profile || {};
  const dailyPunchRecords = data?.daily_punch_records || [];
  const rawPunches = data?.punch_history || [];

  const availableMonths = Array.from(new Set(dailyPunchRecords.map(d => d.month_key).filter(Boolean)));
  const uniqueSubjects = Array.from(new Set([
    ...dailyPunchRecords.flatMap(d => d.lectures.map(l => l.subject_name)),
    ...rawPunches.map(p => p.subject)
  ].filter(Boolean)));

  const toggleDateExpanded = (dateStr) => {
    setExpandedDates(prev => ({
      ...prev,
      [dateStr]: !prev[dateStr]
    }));
  };

  // Filter daily punch records according to active filters
  const filteredDailyRecords = dailyPunchRecords.filter((d) => {
    if (monthFilter && d.month_key !== monthFilter) return false;
    if (dateFilter && d.date !== dateFilter) return false;
    if (dateRangeFrom && d.date < dateRangeFrom) return false;
    if (dateRangeTo && d.date > dateRangeTo) return false;
    if (subjectFilter) {
      const hasSub = d.lectures.some(l => l.subject_name === subjectFilter || l.subject_code === subjectFilter);
      if (!hasSub) return false;
    }
    if (statusFilter) {
      if (statusFilter === 'all_attended' && d.status_type !== 'all_attended') return false;
      if (statusFilter === 'absent' && d.absent_count === 0) return false;
      if (statusFilter === 'in_progress' && d.in_progress_count === 0) return false;
      if (statusFilter === 'under_review' && d.under_review_count === 0) return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      const matchDate = d.date.toLowerCase().includes(q) || d.day_name.toLowerCase().includes(q) || d.month_name.toLowerCase().includes(q);
      const matchLec = d.lectures.some(l =>
        l.subject_name.toLowerCase().includes(q) ||
        l.subject_code.toLowerCase().includes(q) ||
        (l.teacher_name && l.teacher_name.toLowerCase().includes(q))
      );
      if (!matchDate && !matchLec) return false;
    }
    return true;
  });

  // Group filtered daily records by month
  const filteredMonthGroups = [];
  const mGroupsMap = {};
  filteredDailyRecords.forEach((d) => {
    if (!mGroupsMap[d.month_key]) {
      mGroupsMap[d.month_key] = {
        month_title: d.month_key,
        year: d.year,
        dates: []
      };
      filteredMonthGroups.push(mGroupsMap[d.month_key]);
    }
    mGroupsMap[d.month_key].dates.push(d);
  });

  // Calculate dynamic monthly counts from actual filtered records
  filteredMonthGroups.forEach((mg) => {
    const tot = mg.dates.reduce((acc, d) => acc + d.total_lectures, 0);
    const att = mg.dates.reduce((acc, d) => acc + d.attended_count, 0);
    const abs = mg.dates.reduce((acc, d) => acc + d.absent_count, 0);
    const pct = tot > 0 ? Math.round((att / tot) * 1000) / 10 : 0;
    mg.total_lectures = tot;
    mg.attended_count = att;
    mg.absent_count = abs;
    mg.percentage = pct;
  });

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {toast && (
        <NotificationToast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Header Banner */}
      <div style={{
        background: '#ffffff',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-lg)',
        padding: '1.25rem 1.5rem',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1.25rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontWeight: 800,
            fontSize: '1.25rem',
            flexShrink: 0
          }}>
            <CalendarCheck size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                Punch History & Attendance Log
              </h1>
              <span style={{
                background: 'var(--primary-light)',
                color: '#1e3a8a',
                padding: '0.15rem 0.55rem',
                borderRadius: '4px',
                fontSize: '0.75rem',
                fontWeight: 700,
                border: '1px solid #bfdbfe'
              }}>
                Roll #{profile.roll_number || 'N/A'}
              </span>
            </div>
            <p style={{ margin: '0.2rem 0 0', fontSize: '0.825rem', color: 'var(--text-secondary)' }}>
              Detailed date-wise lectures, biometric timestamps, period indicators, and official correction audit requests
            </p>
          </div>
        </div>

        <button
          onClick={fetchPunchData}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.55rem 1rem',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-card)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-color)',
            fontSize: '0.875rem',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          <RefreshCw size={15} /> Refresh Records
        </button>
      </div>

      {/* Tabs & Content Box */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-lg)',
        padding: '1.5rem',
        boxShadow: 'var(--shadow-sm)'
      }}>
        {/* Navigation Tabs Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--border-color)',
          paddingBottom: '1rem',
          marginBottom: '1.25rem',
          flexWrap: 'wrap',
          gap: '1rem'
        }}>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              onClick={() => setActiveTab('punches')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.5rem 1rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.9rem',
                fontWeight: 600,
                background: activeTab === 'punches' ? 'var(--primary)' : 'transparent',
                color: activeTab === 'punches' ? '#ffffff' : 'var(--text-secondary)',
                border: activeTab === 'punches' ? 'none' : '1px solid var(--border-color)',
                transition: 'all 0.15s ease',
                cursor: 'pointer'
              }}
            >
              <CalendarCheck size={16} /> Daily Punch History ({filteredDailyRecords.length})
            </button>

            <button
              onClick={() => setActiveTab('corrections')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.5rem 1rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.9rem',
                fontWeight: 600,
                background: activeTab === 'corrections' ? 'var(--primary)' : 'transparent',
                color: activeTab === 'corrections' ? '#ffffff' : 'var(--text-secondary)',
                border: activeTab === 'corrections' ? 'none' : '1px solid var(--border-color)',
                transition: 'all 0.15s ease',
                cursor: 'pointer'
              }}
            >
              <FileText size={16} /> My Correction Requests ({myCorrections.length})
            </button>
          </div>
        </div>

        {activeTab === 'punches' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Top Summary Legend */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '1rem',
              background: '#ffffff',
              padding: '0.9rem 1.25rem',
              borderRadius: '10px 10px 0 0',
              borderBottom: '1px solid #f1f5f9',
              borderTop: '3px solid #7c3aed',
              boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', flexWrap: 'wrap' }}>
                {/* Green indicator: Punched */}
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem' }}>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '22px',
                    height: '22px',
                    borderRadius: '50%',
                    background: '#10b981',
                    color: '#ffffff',
                    fontWeight: 700,
                    fontSize: '0.75rem'
                  }}>
                    1
                  </span>
                  <span style={{ color: '#1f2937', fontWeight: 600, fontSize: '0.875rem' }}>
                    Punched
                  </span>
                </div>

                {/* Red indicator: Not punched */}
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem' }}>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '22px',
                    height: '22px',
                    borderRadius: '50%',
                    background: '#ef4444',
                    color: '#ffffff',
                    fontWeight: 700,
                    fontSize: '0.75rem'
                  }}>
                    1
                  </span>
                  <span style={{ color: '#1f2937', fontWeight: 600, fontSize: '0.875rem' }}>
                    Not punched
                  </span>
                </div>

                {/* Amber indicator: Pending */}
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem' }}>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '22px',
                    height: '22px',
                    borderRadius: '50%',
                    background: '#f59e0b',
                    color: '#ffffff',
                    fontWeight: 700,
                    fontSize: '0.75rem'
                  }}>
                    ·
                  </span>
                  <span style={{ color: '#1f2937', fontWeight: 600, fontSize: '0.875rem' }}>
                    Pending / Active
                  </span>
                </div>
              </div>

              {/* Legend subtitle text */}
              <div style={{ color: '#6b7280', fontSize: '0.85rem', fontWeight: 400 }}>
                Newest day first · Times as recorded by the attendance system
              </div>
            </div>

            {/* Filter Controls Row */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.5rem 0',
              flexWrap: 'wrap'
            }}>
              {/* Month Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Month:</span>
                <select
                  value={monthFilter}
                  onChange={(e) => setMonthFilter(e.target.value)}
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.45rem 0.65rem',
                    fontSize: '0.825rem'
                  }}
                >
                  <option value="">All Months</option>
                  {availableMonths.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              {/* Subject Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Subject:</span>
                <select
                  value={subjectFilter}
                  onChange={(e) => setSubjectFilter(e.target.value)}
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.45rem 0.65rem',
                    fontSize: '0.825rem',
                    maxWidth: '180px'
                  }}
                >
                  <option value="">All Subjects</option>
                  {uniqueSubjects.map((sub) => (
                    <option key={sub} value={sub}>{sub}</option>
                  ))}
                </select>
              </div>

              {/* Status Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Status:</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.45rem 0.65rem',
                    fontSize: '0.825rem'
                  }}
                >
                  <option value="">All Statuses</option>
                  <option value="all_attended">All Attended</option>
                  <option value="absent">Has Absence</option>
                  <option value="in_progress">In Progress</option>
                  <option value="under_review">Under Review</option>
                </select>
              </div>

              {/* Date From */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>From:</span>
                <input
                  type="date"
                  value={dateRangeFrom}
                  onChange={(e) => setDateRangeFrom(e.target.value)}
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.4rem 0.55rem',
                    fontSize: '0.8rem'
                  }}
                />
              </div>

              {/* Date To */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>To:</span>
                <input
                  type="date"
                  value={dateRangeTo}
                  onChange={(e) => setDateRangeTo(e.target.value)}
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.4rem 0.55rem',
                    fontSize: '0.8rem'
                  }}
                />
              </div>

              {/* Free Text Search */}
              <div style={{ position: 'relative', flex: 1, minWidth: '160px' }}>
                <Search size={14} style={{ position: 'absolute', left: '0.65rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Search subject, faculty, date..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.45rem 0.75rem 0.45rem 2rem',
                    fontSize: '0.825rem'
                  }}
                />
              </div>

              {(monthFilter || subjectFilter || statusFilter || dateRangeFrom || dateRangeTo || searchQuery) && (
                <button
                  onClick={() => {
                    setMonthFilter('');
                    setSubjectFilter('');
                    setStatusFilter('');
                    setDateRangeFrom('');
                    setDateRangeTo('');
                    setSearchQuery('');
                  }}
                  style={{
                    padding: '0.45rem 0.75rem',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(239, 68, 68, 0.1)',
                    color: '#ef4444',
                    border: '1px solid rgba(239, 68, 68, 0.25)',
                    fontSize: '0.8rem',
                    cursor: 'pointer'
                  }}
                >
                  Reset
                </button>
              )}
            </div>

            {/* Attendance History Table with Monthly Groupings */}
            {filteredDailyRecords.length === 0 ? (
              <div style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                padding: '3rem 1.5rem',
                textAlign: 'center',
                color: '#64748b'
              }}>
                <CalendarCheck size={40} style={{ margin: '0 auto 0.75rem', opacity: 0.5, color: '#94a3b8' }} />
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#334155', margin: '0 0 0.25rem' }}>
                  No attendance records available yet
                </h3>
                <p style={{ fontSize: '0.85rem', margin: 0, color: '#64748b' }}>
                  No timetable sessions or punch records matched your selected filters.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                {filteredMonthGroups.map((group, gIdx) => {
                  return (
                    <div
                      key={gIdx}
                      style={{
                        background: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                        overflow: 'hidden',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
                      }}
                    >
                      {/* Monthly Header */}
                      <div style={{
                        padding: '0.75rem 1.25rem',
                        borderBottom: '1px solid #e2e8f0',
                        background: '#f8fafc',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: '0.5rem'
                      }}>
                        <div style={{
                          fontWeight: 700,
                          fontSize: '0.9rem',
                          color: '#1e293b'
                        }}>
                          {group.month_title} · {group.attended_count} of {group.total_lectures} lectures punched · {group.percentage}%
                        </div>
                        <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 500 }}>
                          {group.dates.length} scheduled days
                        </span>
                      </div>

                      {/* Responsive Table */}
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '850px' }}>
                          <thead>
                            <tr style={{
                              background: '#f8fafc',
                              borderBottom: '1px solid #e2e8f0',
                              color: '#64748b',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em'
                            }}>
                              <th style={{ padding: '0.75rem 1.25rem', width: '130px' }}>DATE</th>
                              <th style={{ padding: '0.75rem 1rem', width: '180px' }}>LECTURES</th>
                              <th style={{ padding: '0.75rem 1rem' }}>SUBJECTS</th>
                              <th style={{ padding: '0.75rem 1rem', width: '130px' }}>PUNCH TIME</th>
                              <th style={{ padding: '0.75rem 1.25rem', width: '200px' }}>STATUS</th>
                            </tr>
                          </thead>
                          <tbody>
                            {group.dates.map((day, dIdx) => {
                              const isExpanded = !!expandedDates[day.date];
                              const latestPunch = day.lectures.find(l => l.punch_time && l.punch_time !== '—')?.punch_time || '—';

                              return (
                                <React.Fragment key={dIdx}>
                                  <tr
                                    onClick={() => toggleDateExpanded(day.date)}
                                    style={{
                                      borderBottom: '1px solid #f1f5f9',
                                      background: isExpanded ? '#fbfcfe' : '#ffffff',
                                      cursor: 'pointer',
                                      transition: 'background 0.15s ease'
                                    }}
                                  >
                                    {/* Column 1: DATE */}
                                    <td style={{ padding: '1rem 1.25rem', verticalAlign: 'middle' }}>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        {isExpanded ? (
                                          <ChevronDown size={16} color="#7c3aed" />
                                        ) : (
                                          <ChevronRight size={16} color="#94a3b8" />
                                        )}
                                        <div>
                                          <span style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0f172a', marginRight: '0.35rem' }}>
                                            {day.day_number}
                                          </span>
                                          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155' }}>
                                            {day.day_name}
                                          </span>
                                        </div>
                                      </div>
                                    </td>

                                    {/* Column 2: LECTURES (Compact indicators) */}
                                    <td style={{ padding: '1rem', verticalAlign: 'middle' }}>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
                                        {day.lectures.map((lec, lIdx) => {
                                          let bg = '#10b981';
                                          if (lec.status === 'absent') bg = '#ef4444';
                                          else if (lec.session_status === 'scheduled' || lec.session_status === 'active') bg = '#f59e0b';
                                          else if (lec.session_status === 'review_required') bg = '#8b5cf6';

                                          return (
                                            <span
                                              key={lIdx}
                                              title={`Period ${lec.period_number}: ${lec.subject_name} (${lec.status})`}
                                              style={{
                                                display: 'inline-flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                width: '24px',
                                                height: '24px',
                                                borderRadius: '50%',
                                                background: bg,
                                                color: '#ffffff',
                                                fontWeight: 700,
                                                fontSize: '0.75rem',
                                                boxShadow: '0 1px 2px rgba(0,0,0,0.1)'
                                              }}
                                            >
                                              {lec.period_number || (lIdx + 1)}
                                            </span>
                                          );
                                        })}
                                      </div>
                                    </td>

                                    {/* Column 3: SUBJECTS */}
                                    <td style={{ padding: '1rem', verticalAlign: 'middle' }}>
                                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                                        <div style={{
                                          color: '#7c3aed',
                                          fontWeight: 700,
                                          fontSize: '0.9rem',
                                          lineHeight: 1.3
                                        }}>
                                          {day.lectures.map(l => l.subject_code).join(', ') || 'No subject scheduled'}
                                        </div>
                                        <div style={{ color: '#64748b', fontSize: '0.78rem' }}>
                                          {day.timetable_info || `Section ${profile.section || 'A'}`}
                                        </div>
                                      </div>
                                    </td>

                                    {/* Column 4: PUNCH TIME */}
                                    <td style={{ padding: '1rem', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                                      <span style={{
                                        color: latestPunch !== '—' ? '#0f172a' : '#94a3b8',
                                        fontSize: '0.875rem',
                                        fontWeight: latestPunch !== '—' ? 600 : 400
                                      }}>
                                        {latestPunch}
                                      </span>
                                    </td>

                                    {/* Column 5: STATUS */}
                                    <td style={{ padding: '1rem 1.25rem', verticalAlign: 'middle' }}>
                                      {day.status_type === 'all_attended' ? (
                                        <span style={{
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          gap: '0.35rem',
                                          color: '#10b981',
                                          fontWeight: 600,
                                          fontSize: '0.85rem'
                                        }}>
                                          <CheckCircle2 size={16} /> {day.status_label}
                                        </span>
                                      ) : day.status_type === 'under_review' ? (
                                        <span style={{
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          gap: '0.35rem',
                                          color: '#8b5cf6',
                                          fontWeight: 600,
                                          fontSize: '0.85rem'
                                        }}>
                                          <Clock size={16} /> Under review
                                        </span>
                                      ) : day.status_type === 'in_progress' ? (
                                        <span style={{
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          gap: '0.35rem',
                                          color: '#f59e0b',
                                          fontWeight: 600,
                                          fontSize: '0.85rem'
                                        }}>
                                          <Clock size={16} /> Attendance in progress
                                        </span>
                                      ) : (
                                        <span style={{
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          gap: '0.35rem',
                                          color: '#ef4444',
                                          fontWeight: 600,
                                          fontSize: '0.85rem'
                                        }}>
                                          <XCircle size={16} /> {day.status_label}
                                        </span>
                                      )}
                                    </td>
                                  </tr>

                                  {/* Expanded Period Breakdown */}
                                  {isExpanded && (
                                    <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                                      <td colSpan={5} style={{ padding: '1rem 1.5rem' }}>
                                        <div style={{
                                          background: '#ffffff',
                                          border: '1px solid #e2e8f0',
                                          borderRadius: '8px',
                                          padding: '1rem',
                                          boxShadow: '0 1px 2px rgba(0,0,0,0.02)'
                                        }}>
                                          <div style={{
                                            fontSize: '0.8rem',
                                            fontWeight: 700,
                                            color: '#475569',
                                            textTransform: 'uppercase',
                                            letterSpacing: '0.04em',
                                            marginBottom: '0.75rem',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'space-between'
                                          }}>
                                            <span>Period Breakdown for {day.date}</span>
                                            <span style={{ textTransform: 'none', color: '#64748b', fontWeight: 500 }}>
                                              {day.lectures.length} scheduled periods
                                            </span>
                                          </div>

                                          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.825rem' }}>
                                            <thead>
                                              <tr style={{ borderBottom: '1px solid #f1f5f9', color: '#64748b' }}>
                                                <th style={{ padding: '0.5rem 0.75rem' }}>PERIOD</th>
                                                <th style={{ padding: '0.5rem 0.75rem' }}>TIME</th>
                                                <th style={{ padding: '0.5rem 0.75rem' }}>SUBJECT</th>
                                                <th style={{ padding: '0.5rem 0.75rem' }}>FACULTY</th>
                                                <th style={{ padding: '0.5rem 0.75rem' }}>PUNCH TIMESTAMP</th>
                                                <th style={{ padding: '0.5rem 0.75rem' }}>STATUS</th>
                                                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'right' }}>ACTION</th>
                                              </tr>
                                            </thead>
                                            <tbody>
                                              {day.lectures.map((lec, lIdx) => {
                                                const isAttended = (lec.status === 'present');
                                                const isAbsent = (lec.status === 'absent');
                                                const isPending = (lec.session_status === 'active' || lec.session_status === 'scheduled');

                                                return (
                                                  <tr key={lIdx} style={{ borderBottom: '1px solid #f8fafc' }}>
                                                    <td style={{ padding: '0.65rem 0.75rem', fontWeight: 700, color: '#1e293b' }}>
                                                      Period {lec.period_number}
                                                    </td>
                                                    <td style={{ padding: '0.65rem 0.75rem', color: '#64748b' }}>
                                                      {lec.start_time} - {lec.end_time}
                                                    </td>
                                                    <td style={{ padding: '0.65rem 0.75rem' }}>
                                                      <span style={{ fontWeight: 600, color: '#0f172a' }}>{lec.subject_name}</span>
                                                      <span style={{ color: '#7c3aed', marginLeft: '0.4rem', fontSize: '0.75rem' }}>({lec.subject_code})</span>
                                                    </td>
                                                    <td style={{ padding: '0.65rem 0.75rem', color: '#475569' }}>
                                                      {lec.teacher_name || 'Faculty Member'}
                                                    </td>
                                                    <td style={{ padding: '0.65rem 0.75rem' }}>
                                                      {isAttended ? (
                                                        <span style={{ color: '#10b981', fontWeight: 600 }}>
                                                          ✓ {lec.punch_time}
                                                        </span>
                                                      ) : (
                                                        <span style={{ color: '#94a3b8' }}>—</span>
                                                      )}
                                                    </td>
                                                    <td style={{ padding: '0.65rem 0.75rem' }}>
                                                      {isAttended ? (
                                                        <span style={{
                                                          display: 'inline-flex',
                                                          alignItems: 'center',
                                                          gap: '0.25rem',
                                                          color: '#10b981',
                                                          fontWeight: 600
                                                        }}>
                                                          <CheckCircle2 size={13} /> Present
                                                        </span>
                                                      ) : isAbsent ? (
                                                        <span style={{
                                                          display: 'inline-flex',
                                                          alignItems: 'center',
                                                          gap: '0.25rem',
                                                          color: '#ef4444',
                                                          fontWeight: 600
                                                        }}>
                                                          <XCircle size={13} /> Absent
                                                        </span>
                                                      ) : isPending ? (
                                                        <span style={{
                                                          display: 'inline-flex',
                                                          alignItems: 'center',
                                                          gap: '0.25rem',
                                                          color: '#f59e0b',
                                                          fontWeight: 600
                                                        }}>
                                                          <Clock size={13} /> Pending
                                                        </span>
                                                      ) : (
                                                        <span style={{ color: '#64748b' }}>{lec.status}</span>
                                                      )}
                                                    </td>
                                                    <td style={{ padding: '0.65rem 0.75rem', textAlign: 'right' }}>
                                                      {lec.correction_status ? (
                                                        <span style={{
                                                          fontSize: '0.72rem',
                                                          fontWeight: 600,
                                                          color: lec.correction_status === 'approved' ? '#10b981' : lec.correction_status === 'rejected' ? '#ef4444' : '#f59e0b',
                                                          background: lec.correction_status === 'approved' ? 'rgba(16, 185, 129, 0.1)' : lec.correction_status === 'rejected' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                                                          padding: '0.2rem 0.45rem',
                                                          borderRadius: '4px'
                                                        }}>
                                                          Correction: {lec.correction_status}
                                                        </span>
                                                      ) : (
                                                        <button
                                                          onClick={(e) => {
                                                            e.stopPropagation();
                                                            openCorrectionModal(lec);
                                                          }}
                                                          style={{
                                                            fontSize: '0.75rem',
                                                            padding: '0.25rem 0.55rem',
                                                            borderRadius: '4px',
                                                            background: '#f1f5f9',
                                                            color: '#475569',
                                                            border: '1px solid #cbd5e1',
                                                            cursor: 'pointer'
                                                          }}
                                                        >
                                                          Correction
                                                        </button>
                                                      )}
                                                    </td>
                                                  </tr>
                                                );
                                              })}
                                            </tbody>
                                          </table>
                                        </div>
                                      </td>
                                    </tr>
                                  )}
                                </React.Fragment>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* My Correction Requests Tab */}
        {activeTab === 'corrections' && (
          <div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1rem',
              flexWrap: 'wrap',
              gap: '0.5rem'
            }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                  Attendance Correction Requests
                </h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0' }}>
                  Audit log of correction claims submitted for faculty or administrative review
                </p>
              </div>
            </div>

            {myCorrections.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '3rem 1.5rem', color: 'var(--text-muted)' }}>
                <FileText size={36} style={{ margin: '0 auto 0.75rem', opacity: 0.5 }} />
                <p style={{ margin: 0, fontWeight: 500 }}>No correction requests submitted yet.</p>
                <p style={{ fontSize: '0.8rem', margin: '0.25rem 0 0' }}>
                  If you were present but marked absent due to biometric failure, expand any day row above and click "Correction".
                </p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.78rem', textTransform: 'uppercase' }}>
                      <th style={{ padding: '0.75rem 1rem' }}>Request ID</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Subject / Session</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Reason</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Submitted On</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Review Status</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Admin / Faculty Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {myCorrections.map((corr) => (
                      <tr key={corr.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                        <td style={{ padding: '0.85rem 1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                          #{corr.id}
                        </td>
                        <td style={{ padding: '0.85rem 1rem' }}>
                          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                            {corr.subject || `Session #${corr.session_id}`}
                          </span>
                        </td>
                        <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary)', maxWidth: '280px' }}>
                          {corr.reason}
                        </td>
                        <td style={{ padding: '0.85rem 1rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                          {corr.created_at ? corr.created_at.slice(0, 10) : '—'}
                        </td>
                        <td style={{ padding: '0.85rem 1rem', textAlign: 'center' }}>
                          <span style={{
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            padding: '0.25rem 0.6rem',
                            borderRadius: '999px',
                            background: corr.status === 'approved' ? 'rgba(16, 185, 129, 0.12)' : corr.status === 'rejected' ? 'rgba(239, 68, 68, 0.12)' : 'rgba(245, 158, 11, 0.12)',
                            color: corr.status === 'approved' ? '#10b981' : corr.status === 'rejected' ? '#ef4444' : '#f59e0b'
                          }}>
                            {corr.status ? corr.status.toUpperCase() : 'PENDING'}
                          </span>
                        </td>
                        <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary)', fontSize: '0.825rem' }}>
                          {corr.review_notes || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Correction Request Modal */}
      <Modal
        isOpen={correctionModalOpen}
        onClose={() => setCorrectionModalOpen(false)}
        title="Submit Attendance Correction Request"
      >
        <form onSubmit={handleCorrectionSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
          <div style={{
            background: 'var(--bg-input)',
            padding: '1rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-color)',
            fontSize: '0.85rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.35rem'
          }}>
            <div><strong>Subject:</strong> {selectedRecord?.subject_name || selectedRecord?.subject || 'Class Lecture'}</div>
            <div><strong>Period:</strong> Period {selectedRecord?.period_number} ({selectedRecord?.start_time} - {selectedRecord?.end_time})</div>
            <div><strong>Faculty:</strong> {selectedRecord?.teacher_name || 'Faculty Member'}</div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
              Reason Category *
            </label>
            <select
              value={reasonCategory}
              onChange={(e) => setReasonCategory(e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                padding: '0.65rem 0.85rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.9rem'
              }}
            >
              <option value="Camera / Face Not Recognized">Camera / Face Not Recognized</option>
              <option value="Approved On-Duty / University Event">Approved On-Duty / University Event</option>
              <option value="Medical Leave / Doctor Certificate">Medical Leave / Doctor Certificate</option>
              <option value="Late Entry with Faculty Permission">Late Entry with Faculty Permission</option>
              <option value="Other Legitimate Reason">Other Legitimate Reason</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
              Detailed Explanation *
            </label>
            <textarea
              required
              rows={3}
              value={reasonDetails}
              onChange={(e) => setReasonDetails(e.target.value)}
              placeholder="Explain why you were present and why your face punch was not recorded..."
              style={{
                width: '100%',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                padding: '0.65rem 0.85rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.9rem',
                resize: 'vertical'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
              Supporting Evidence Reference (Optional)
            </label>
            <input
              type="text"
              value={evidenceNote}
              onChange={(e) => setEvidenceNote(e.target.value)}
              placeholder="e.g., Medical slip ref #1234, OD letter signed by HOD"
              style={{
                width: '100%',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                padding: '0.65rem 0.85rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.9rem'
              }}
            />
          </div>

          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0 }}>
            * Note: Submitting this request sends an official audit review entry to the course faculty and administrator. Your record will only be updated upon administrative verification.
          </p>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setCorrectionModalOpen(false)}
              style={{
                padding: '0.6rem 1rem',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-input)',
                color: 'var(--text-secondary)',
                fontSize: '0.875rem',
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submittingCorrection}
              style={{
                padding: '0.6rem 1.25rem',
                borderRadius: 'var(--radius-md)',
                background: 'linear-gradient(135deg, #4f46e5, #6366f1)',
                color: 'white',
                fontWeight: 600,
                fontSize: '0.875rem',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                opacity: submittingCorrection ? 0.7 : 1,
                cursor: submittingCorrection ? 'not-allowed' : 'pointer'
              }}
            >
              {submittingCorrection ? (
                <>
                  <div className="spin" style={{ width: '14px', height: '14px', border: '2px solid white', borderTopColor: 'transparent', borderRadius: '50%' }} />
                  Submitting...
                </>
              ) : (
                <>
                  <Send size={15} /> Submit Request
                </>
              )}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default StudentPunchHistory;
