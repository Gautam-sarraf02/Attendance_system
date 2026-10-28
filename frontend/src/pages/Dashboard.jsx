import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Users,
  CheckCircle2,
  Calendar,
  Radio,
  Cpu,
  ArrowRight,
  BookOpen,
  TrendingUp,
  Clock,
  Video
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';
import { attendanceService } from '../services/attendanceService';
import { modelService } from '../services/modelService';
import { StatCard } from '../components/StatCard';
import { StatusBadge } from '../components/StatusBadge';
import { PrivacyNotice } from '../components/PrivacyNotice';
import { useAuth } from '../context/AuthContext';
import { StudentDashboard } from './StudentDashboard';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export const Dashboard = () => {
  const { user } = useAuth();
  if (user?.role === 'student') {
    return <StudentDashboard />;
  }

  const [stats, setStats] = useState(null);
  const [modelStatus, setModelStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [dashData, mStatus] = await Promise.all([
        attendanceService.getDashboardStats(),
        modelService.getStatus()
      ]);
      setStats(dashData);
      setModelStatus(mStatus);
    } catch (err) {
      console.error('Failed to load dashboard statistics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  // Daily Trend Chart configuration
  const trendLabels = (stats?.daily_trends || []).map((t) => t.date);
  const trendValues = (stats?.daily_trends || []).map((t) => t.present);

  const lineChartData = {
    labels: trendLabels.length ? trendLabels : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Today'],
    datasets: [
      {
        label: 'Students Present',
        data: trendValues.length ? trendValues : [0, 0, 0, 0, 0, 0, 0],
        borderColor: '#243B64',
        backgroundColor: 'rgba(36, 59, 100, 0.08)',
        fill: true,
        tension: 0.25,
        pointBackgroundColor: '#243B64',
        pointBorderColor: '#ffffff',
        pointRadius: 4,
      },
    ],
  };

  // Subject distribution configuration
  const subjectLabels = (stats?.subject_distribution || []).map((s) => s.subject);
  const subjectCounts = (stats?.subject_distribution || []).map((s) => s.count);

  const barChartData = {
    labels: subjectLabels.length ? subjectLabels : ['Computer Vision', 'Machine Learning', 'Cloud Systems'],
    datasets: [
      {
        label: 'Attendance Records',
        data: subjectCounts.length ? subjectCounts : [0, 0, 0],
        backgroundColor: [
          '#243B64',
          '#0284c7',
          '#16a34a',
          '#d97706',
          '#475569',
        ],
        borderRadius: 4,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#0f172a',
        titleColor: '#f8fafc',
        bodyColor: '#e2e8f0',
        borderColor: '#cbd5e1',
        borderWidth: 1,
        padding: 8,
        cornerRadius: 6,
      },
    },
    scales: {
      x: {
        grid: { color: '#f1f5f9' },
        ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11 } },
      },
      y: {
        beginAtZero: true,
        grid: { color: '#f1f5f9' },
        ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11 } },
      },
    },
  };

  return (
    <div className="page-body">
      {/* Top Banner / Welcome */}
      <div style={{
        marginBottom: '1.75rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem'
      }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {user?.role === 'admin' ? 'Administrative Operations Hub' : 'Faculty Dashboard'}
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.2rem' }}>
            Real-time classroom attendance tracking, biometric session management, and academic metrics
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <Link to="/attendance/live" className="btn btn-primary">
            <Video size={16} />
            <span>Launch Live Session</span>
          </Link>
          <Link to="/students/register" className="btn btn-secondary">
            <Users size={16} />
            <span>Register Student</span>
          </Link>
        </div>
      </div>

      {/* Active Session Notification Card */}
      {stats?.active_session && (
        <div style={{
          marginBottom: '1.5rem',
          padding: '1rem 1.25rem',
          borderRadius: 'var(--radius-md)',
          background: 'var(--success-light)',
          border: '1px solid var(--success-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <span className="pulse-indicator pulse-green" style={{ width: '10px', height: '10px' }} />
            <div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--success)' }}>
                Active Classroom Attendance Session
              </div>
              <div style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', marginTop: '0.1rem' }}>
                Subject: <strong style={{ color: 'var(--text-primary)' }}>{stats.active_session.subject}</strong> | Section: <strong style={{ color: 'var(--text-primary)' }}>{stats.active_session.section}</strong> | Verified Present: <strong style={{ color: 'var(--success)' }}>{stats.active_session.present_count} students</strong>
              </div>
            </div>
          </div>
          <Link to="/attendance/live" className="btn btn-success btn-sm">
            <span>Enter Live Terminal</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      )}

      {/* 4 Stat Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
        gap: '1rem',
        marginBottom: '1.75rem'
      }}>
        <StatCard
          title="Total Students"
          value={stats?.total_students ?? 0}
          subtext="Enrolled students in section"
          icon={Users}
          color="primary"
          badgeText="Active"
        />
        <StatCard
          title="Present Today"
          value={stats?.present_today ?? 0}
          subtext="Verified face-recognition marks"
          icon={CheckCircle2}
          color="success"
          badgeText="Today"
        />
        <StatCard
          title="Attendance Records"
          value={stats?.total_attendance_records ?? 0}
          subtext="Finalized & logged punches"
          icon={Calendar}
          color="info"
        />
        <StatCard
          title="Total Lecture Sessions"
          value={stats?.total_sessions ?? 0}
          subtext="Classroom slots conducted"
          icon={BookOpen}
          color="warning"
        />
      </div>

      {/* Model Status Card & Quick Controls */}
      <div style={{
        marginBottom: '1.75rem',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '1rem'
      }}>
        {/* Model Health */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div className="card-header">
              <span className="card-title">
                <Cpu size={17} color="#2563eb" />
                Face Recognition Engine Status
              </span>
              <StatusBadge
                status={modelStatus?.is_trained ? 'trained' : 'untrained'}
                text={modelStatus?.is_trained ? 'Model Ready' : 'Needs Training'}
              />
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
              <div>Algorithm: <strong style={{ color: 'var(--text-primary)' }}>OpenCV LBPH (Local Binary Patterns)</strong></div>
              <div>Face Detector: <strong style={{ color: 'var(--text-primary)' }}>Haar Cascade Frontal Face</strong></div>
              <div>Registered Biometric Templates: <strong style={{ color: 'var(--text-primary)' }}>{modelStatus?.total_samples || 0} samples</strong></div>
              <div>Trained Students: <strong style={{ color: 'var(--text-primary)' }}>{modelStatus?.total_students_with_samples || 0} / {modelStatus?.total_students_enrolled || 0}</strong></div>
              {modelStatus?.last_trained && (
                <div>Last Model Compilation: <strong style={{ color: 'var(--text-primary)' }}>{new Date(modelStatus.last_trained).toLocaleString()}</strong></div>
              )}
            </div>
          </div>

          <div style={{ marginTop: '1.25rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)', display: 'flex', gap: '0.75rem' }}>
            <Link to="/model" className="btn btn-secondary btn-sm" style={{ flex: 1 }}>
              <Cpu size={14} />
              <span>Model Management & Training</span>
            </Link>
          </div>
        </div>

        {/* Workflow Procedures */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <BookOpen size={17} color="#243B64" />
              Standard Attendance Workflow
            </span>
            <span className="badge badge-primary">SOP Guide</span>
          </div>
          <ol style={{ paddingLeft: '1.25rem', fontSize: '0.825rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <li><strong style={{ color: 'var(--text-primary)' }}>Timetable Schedule:</strong> Admin sets weekly timetable slots per semester & section.</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>Teacher Verification:</strong> Faculty verifies face before starting assigned slot.</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>Real-time Detection:</strong> Camera detects student faces and matches biometric templates.</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>15-Min Deadline:</strong> Attendance window automatically closes after 15 minutes.</li>
            <li><strong style={{ color: 'var(--text-primary)' }}>Finalization & Audit:</strong> Unpunched students finalized as absent; reports generated.</li>
          </ol>
        </div>
      </div>

      {/* Analytics Charts */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
        gap: '1rem',
        marginBottom: '1.75rem'
      }}>
        {/* Daily Trend */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <TrendingUp size={17} color="#2563eb" />
              Daily Attendance Trend (Last 7 Days)
            </span>
          </div>
          <div style={{ height: '220px', position: 'relative' }}>
            <Line data={lineChartData} options={chartOptions} />
          </div>
        </div>

        {/* Subject Breakdown */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <BookOpen size={17} color="#0284c7" />
              Attendance by Subject
            </span>
          </div>
          <div style={{ height: '220px', position: 'relative' }}>
            <Bar data={barChartData} options={chartOptions} />
          </div>
        </div>
      </div>

      {/* Recent Live Activity Table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Clock size={17} color="#16a34a" />
            Recent Attendance Feed
          </span>
          <Link to="/attendance/history" style={{ fontSize: '0.8rem', color: '#2563eb', fontWeight: 600 }}>
            View Full Register →
          </Link>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Student Name</th>
                <th>Roll Number</th>
                <th>Subject</th>
                <th>Date</th>
                <th>Time</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {stats?.recent_activity?.length ? (
                stats.recent_activity.map((rec) => (
                  <tr key={rec.id}>
                    <td style={{ fontWeight: 600 }}>{rec.student_name}</td>
                    <td><code style={{ fontSize: '0.8rem', color: '#243B64' }}>{rec.roll_number}</code></td>
                    <td>{rec.subject}</td>
                    <td>{rec.date}</td>
                    <td>{rec.time}</td>
                    <td><StatusBadge status={rec.status} /></td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                    No recent attendance recorded. Start an attendance session to mark students.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <PrivacyNotice />
    </div>
  );
};

export default Dashboard;
