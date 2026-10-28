import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Shield,
  Calendar,
  BookOpen,
  Users,
  Camera,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Clock,
  Trash2,
  Sparkles,
  ArrowRight,
  GraduationCap,
  KeyRound,
  UserCheck,
  UserX,
  Upload,
  Download,
  FileSpreadsheet,
  AlertTriangle
} from 'lucide-react';
import { academicService } from '../services/academicService';
import { enrollmentService } from '../services/enrollmentService';
import { authService } from '../services/authService';
import { studentService } from '../services/studentService';
import { WebcamCapture } from '../components/WebcamCapture';
import { NotificationToast } from '../components/NotificationToast';
import { Modal } from '../components/Modal';

export const AdminManagement = () => {
  const [activeTab, setActiveTab] = useState('enrollment');
  const [toast, setToast] = useState(null);
  const [loading, setLoading] = useState(false);

  // Data states
  const [academicYears, setAcademicYears] = useState([]);
  const [semesters, setSemesters] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [students, setStudents] = useState([]);
  const [enrollments, setEnrollments] = useState([]);
  const [timetableEntries, setTimetableEntries] = useState([]);
  const [holidays, setHolidays] = useState([]);

  // Modals
  const [showEnrollModal, setShowEnrollModal] = useState(false);
  const [showRenewModal, setShowRenewModal] = useState(false);
  const [selectedEnrollmentForRenew, setSelectedEnrollmentForRenew] = useState(null);
  const [showAddTimetableModal, setShowAddTimetableModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showHolidayModal, setShowHolidayModal] = useState(false);

  // Timetable Filter & Form States
  const [selectedSemesterForTimetable, setSelectedSemesterForTimetable] = useState('all');
  const [selectedSectionForTimetable, setSelectedSectionForTimetable] = useState('all');
  const [ttSemId, setTtSemId] = useState('');
  const [ttSubId, setTtSubId] = useState('');
  const [ttTeacherId, setTtTeacherId] = useState('');
  const [ttSection, setTtSection] = useState('CSE-A');
  const [ttDay, setTtDay] = useState(0);
  const [ttPeriod, setTtPeriod] = useState(1);
  const [ttStartTime, setTtStartTime] = useState('09:00');
  const [ttEndTime, setTtEndTime] = useState('10:00');

  // Timetable Import States
  const [importPreview, setImportPreview] = useState(null);
  const [replaceConflicts, setReplaceConflicts] = useState(false);
  const [previewRowsEditable, setPreviewRowsEditable] = useState([]);

  // Holiday Form State
  const [holidayName, setHolidayName] = useState('');
  const [holidayDate, setHolidayDate] = useState('');
  const [holidayDesc, setHolidayDesc] = useState('');

  // Enrollment Form State
  const [enrollPersonType, setEnrollPersonType] = useState('student');
  const [enrollTargetId, setEnrollTargetId] = useState('');
  const [enrollAcademicYearId, setEnrollAcademicYearId] = useState('');
  const [capturedImages, setCapturedImages] = useState([]);
  const [enrollNotes, setEnrollNotes] = useState('');
  const [renewAcademicYearId, setRenewAcademicYearId] = useState('');

  // Academic Year Form State
  const [ayName, setAyName] = useState('');
  const [ayStartDate, setAyStartDate] = useState('');
  const [ayEndDate, setAyEndDate] = useState('');
  const [ayIsCurrent, setAyIsCurrent] = useState(false);

  // Semester Form State
  const [semName, setSemName] = useState('');
  const [semAyId, setSemAyId] = useState('');
  const [semStartDate, setSemStartDate] = useState('');
  const [semEndDate, setSemEndDate] = useState('');

  // Subject Form State
  const [subCode, setSubCode] = useState('');
  const [subName, setSubName] = useState('');
  const [subSemId, setSubSemId] = useState('');
  const [subSection, setSubSection] = useState('CSE-A');

  // Teacher / Faculty Form State
  const [facultyId, setFacultyId] = useState('');
  const [teacherUsername, setTeacherUsername] = useState('');
  const [teacherFullName, setTeacherFullName] = useState('');
  const [teacherEmail, setTeacherEmail] = useState('');
  const [teacherPassword, setTeacherPassword] = useState('');

  const loadAllData = async () => {
    try {
      setLoading(true);
      const [ayList, semList, subList, facList, stuRes, enrollList, ttList, holList] = await Promise.all([
        academicService.getAcademicYears().catch(() => []),
        academicService.getSemesters().catch(() => []),
        academicService.getSubjects().catch(() => []),
        authService.getFaculty().catch(() => []),
        studentService.getStudents({ limit: 200 }).catch(() => ({ students: [] })),
        enrollmentService.getEnrollments().catch(() => []),
        academicService.getTimetableEntries().catch(() => []),
        academicService.getHolidays().catch(() => [])
      ]);

      setAcademicYears(ayList);
      setSemesters(semList);
      setSubjects(subList);
      setTeachers(facList || []);
      setStudents(stuRes.students || []);
      setEnrollments(enrollList);
      setTimetableEntries(ttList);
      setHolidays(holList);

      // Default selected academic year if available
      const currentYear = ayList.find((y) => y.is_current) || ayList[0];
      if (currentYear) {
        setEnrollAcademicYearId(String(currentYear.id));
        setSemAyId(String(currentYear.id));
      }
      if (semList[0]) {
        setSubSemId(String(semList[0].id));
        setTtSemId(String(semList[0].id));
      }
    } catch (err) {
      console.error('Failed to load admin data:', err);
      setToast({ message: 'Failed to fetch administrative data.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

  // ─── Face Enrollment Handlers ──────────────────────────────────────────────

  const handleRegisterFace = async (e) => {
    e.preventDefault();
    if (!enrollTargetId) {
      setToast({ message: 'Please select a person to enroll.', type: 'warning' });
      return;
    }
    if (!enrollAcademicYearId) {
      setToast({ message: 'Please select an academic year.', type: 'warning' });
      return;
    }
    if (capturedImages.length < 1) {
      setToast({ message: 'Please capture at least 1 clear face image (3+ recommended).', type: 'warning' });
      return;
    }

    try {
      setLoading(true);
      const payload = {
        person_type: enrollPersonType,
        student_id: enrollPersonType === 'student' ? Number(enrollTargetId) : undefined,
        user_id: enrollPersonType === 'teacher' ? Number(enrollTargetId) : undefined,
        academic_year_id: Number(enrollAcademicYearId),
        images: capturedImages,
        notes: enrollNotes.trim() || undefined,
        re_enroll: true
      };

      const res = await enrollmentService.registerFaceCamera(payload);
      setToast({
        message: res.message || 'Face enrollment completed successfully!',
        type: 'success'
      });
      setShowEnrollModal(false);
      setCapturedImages([]);
      setEnrollNotes('');
      setEnrollTargetId('');
      loadAllData();
    } catch (err) {
      console.error('Enrollment registration error:', err);
      const detail = err.response?.data?.detail;
      setToast({
        message: typeof detail === 'string' ? detail : 'Biometric enrollment failed.',
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRenewEnrollment = async (e) => {
    e.preventDefault();
    if (!selectedEnrollmentForRenew || !renewAcademicYearId) return;

    try {
      setLoading(true);
      await enrollmentService.renewEnrollment(selectedEnrollmentForRenew.id, {
        academic_year_id: Number(renewAcademicYearId)
      });
      setToast({ message: 'Face enrollment renewed for subsequent academic year!', type: 'success' });
      setShowRenewModal(false);
      setSelectedEnrollmentForRenew(null);
      loadAllData();
    } catch (err) {
      console.error('Renew error:', err);
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to renew enrollment.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleRevokeEnrollment = async (enrollmentId) => {
    if (!window.confirm('Are you sure you want to revoke this biometric enrollment? The user will no longer be authorized for attendance.')) {
      return;
    }
    try {
      setLoading(true);
      await enrollmentService.revokeEnrollment(enrollmentId);
      setToast({ message: 'Enrollment revoked successfully.', type: 'success' });
      loadAllData();
    } catch (err) {
      console.error('Revoke error:', err);
      setToast({ message: 'Failed to revoke enrollment.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteEnrollment = async (enrollmentId) => {
    if (!window.confirm('Delete this face enrollment record and its stored biometric template?')) {
      return;
    }
    try {
      setLoading(true);
      await enrollmentService.deleteEnrollment(enrollmentId);
      setToast({ message: 'Enrollment record deleted.', type: 'success' });
      loadAllData();
    } catch (err) {
      console.error('Delete enrollment error:', err);
      setToast({ message: 'Failed to delete enrollment.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // ─── Academic Calendar Handlers ────────────────────────────────────────────

  const handleAddAcademicYear = async (e) => {
    e.preventDefault();
    if (!ayName || !ayStartDate || !ayEndDate) {
      setToast({ message: 'Please fill in all academic year fields.', type: 'warning' });
      return;
    }
    try {
      setLoading(true);
      await academicService.createAcademicYear({
        name: ayName.trim(),
        start_date: ayStartDate,
        end_date: ayEndDate,
        is_current: ayIsCurrent
      });
      setToast({ message: `Academic year '${ayName}' created.`, type: 'success' });
      setAyName('');
      setAyStartDate('');
      setAyEndDate('');
      setAyIsCurrent(false);
      loadAllData();
    } catch (err) {
      console.error('Create academic year error:', err);
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to create academic year.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAcademicYear = async (id, name) => {
    if (!window.confirm(`Delete academic year '${name}'? This may cascade to semesters and enrollments.`)) return;
    try {
      await academicService.deleteAcademicYear(id);
      setToast({ message: `Academic year '${name}' deleted.`, type: 'success' });
      loadAllData();
    } catch (err) {
      setToast({ message: 'Failed to delete academic year.', type: 'error' });
    }
  };

  const handleAddSemester = async (e) => {
    e.preventDefault();
    if (!semName || !semAyId || !semStartDate || !semEndDate) {
      setToast({ message: 'Please fill in all semester fields.', type: 'warning' });
      return;
    }
    try {
      setLoading(true);
      await academicService.createSemester({
        name: semName.trim(),
        academic_year_id: Number(semAyId),
        start_date: semStartDate,
        end_date: semEndDate,
        is_active: true
      });
      setToast({ message: `Semester '${semName}' created.`, type: 'success' });
      setSemName('');
      setSemStartDate('');
      setSemEndDate('');
      loadAllData();
    } catch (err) {
      console.error('Create semester error:', err);
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to create semester.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSemester = async (id, name) => {
    if (!window.confirm(`Delete semester '${name}'?`)) return;
    try {
      await academicService.deleteSemester(id);
      setToast({ message: `Semester '${name}' deleted.`, type: 'success' });
      loadAllData();
    } catch (err) {
      setToast({ message: 'Failed to delete semester.', type: 'error' });
    }
  };

  const handleAddSubject = async (e) => {
    e.preventDefault();
    if (!subCode || !subName || !subSemId || !subSection) {
      setToast({ message: 'Please fill in all subject fields.', type: 'warning' });
      return;
    }
    try {
      setLoading(true);
      await academicService.createSubject({
        code: subCode.trim().toUpperCase(),
        name: subName.trim(),
        semester_id: Number(subSemId),
        section: subSection.trim().toUpperCase(),
        is_active: true
      });
      setToast({ message: `Subject '${subCode}' created for section ${subSection}.`, type: 'success' });
      setSubCode('');
      setSubName('');
      loadAllData();
    } catch (err) {
      console.error('Create subject error:', err);
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to create subject.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSubject = async (id, name) => {
    if (!window.confirm(`Delete subject '${name}'?`)) return;
    try {
      await academicService.deleteSubject(id);
      setToast({ message: `Subject '${name}' deleted.`, type: 'success' });
      loadAllData();
    } catch (err) {
      setToast({ message: 'Failed to delete subject.', type: 'error' });
    }
  };

  // ─── Teacher / User Management Handlers ────────────────────────────────────

  const handleAddTeacher = async (e) => {
    e.preventDefault();
    if (!facultyId || !teacherUsername || !teacherPassword) {
      setToast({ message: 'Faculty ID, username, and password (min 8 chars) are required.', type: 'warning' });
      return;
    }
    if (teacherPassword.length < 8) {
      setToast({ message: 'Password must be at least 8 characters.', type: 'warning' });
      return;
    }
    try {
      setLoading(true);
      await authService.createFaculty({
        faculty_id: facultyId.trim(),
        username: teacherUsername.trim(),
        password: teacherPassword,
        full_name: teacherFullName.trim() || teacherUsername.trim(),
        email: teacherEmail.trim() || undefined
      });
      setToast({ message: `Faculty account '${teacherFullName || teacherUsername}' (${facultyId.trim()}) registered successfully.`, type: 'success' });
      setFacultyId('');
      setTeacherUsername('');
      setTeacherFullName('');
      setTeacherEmail('');
      setTeacherPassword('');
      loadAllData();
    } catch (err) {
      console.error('Create faculty error:', err);
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to register faculty account.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleOpenFacultyFaceEnroll = (teacher) => {
    setEnrollPersonType('teacher');
    setEnrollTargetId(String(teacher.id));
    setCapturedImages([]);
    setEnrollNotes(`Biometric enrollment for faculty ${teacher.full_name || teacher.username} (${teacher.faculty_id || teacher.username})`);
    setShowEnrollModal(true);
  };

  const handleToggleUserActive = async (user) => {
    try {
      await authService.updateUser(user.id, { is_active: !user.is_active });
      setToast({ message: `Account status updated for ${user.username}.`, type: 'success' });
      loadAllData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to update user status.', type: 'error' });
    }
  };

  const handleDeleteUser = async (id, username) => {
    if (!window.confirm(`Delete user '${username}'?`)) return;
    try {
      await authService.deleteUser(id);
      setToast({ message: `User '${username}' deleted.`, type: 'success' });
      loadAllData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to delete user.', type: 'error' });
    }
  };

  // ─── Timetable & Holiday Handlers ──────────────────────────────────────────

  const handleCreateTimetableEntry = async (e) => {
    e.preventDefault();
    if (!ttSemId || !ttSubId || !ttTeacherId || !ttSection.trim()) {
      setToast({ message: 'Please fill in all required fields.', type: 'warning' });
      return;
    }
    try {
      setLoading(true);
      await academicService.createTimetableEntry({
        semester_id: Number(ttSemId),
        subject_id: Number(ttSubId),
        teacher_id: Number(ttTeacherId),
        section: ttSection.trim().toUpperCase(),
        day_of_week: Number(ttDay),
        period_number: Number(ttPeriod),
        start_time: ttStartTime.length === 5 ? `${ttStartTime}:00` : ttStartTime,
        end_time: ttEndTime.length === 5 ? `${ttEndTime}:00` : ttEndTime
      });
      setToast({ message: 'Timetable slot created successfully.', type: 'success' });
      setShowAddTimetableModal(false);
      loadAllData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to create timetable slot.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTimetableEntry = async (id) => {
    if (!window.confirm('Delete this timetable entry?')) return;
    try {
      await academicService.deleteTimetableEntry(id);
      setToast({ message: 'Timetable entry removed.', type: 'success' });
      loadAllData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to delete entry.', type: 'error' });
    }
  };

  const handleFileSelectForImport = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      setLoading(true);
      const formData = new FormData();
      formData.append('file', file);
      const previewRes = await academicService.previewTimetableImport(formData);
      setImportPreview(previewRes);
      setPreviewRowsEditable(previewRes.rows.map(r => ({
        ...r,
        edited_resolved: r.resolved ? { ...r.resolved } : null
      })));
      setToast({
        message: `Preview generated: ${previewRes.valid_count} valid, ${previewRes.conflict_count} conflicts, ${previewRes.error_count} errors.`,
        type: previewRes.error_count > 0 ? 'warning' : 'success'
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to parse timetable file.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleCommitImport = async () => {
    const rowsToCommit = previewRowsEditable
      .filter(r => r.edited_resolved || r.resolved)
      .map(r => r.edited_resolved || r.resolved);

    if (rowsToCommit.length === 0) {
      setToast({ message: 'No valid rows to commit.', type: 'warning' });
      return;
    }

    try {
      setLoading(true);
      const res = await academicService.commitTimetableImport({
        rows: rowsToCommit,
        replace_conflicts: replaceConflicts
      });
      setToast({ message: res.message || 'Timetable imported successfully!', type: 'success' });
      setShowImportModal(false);
      setImportPreview(null);
      setPreviewRowsEditable([]);
      loadAllData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to commit timetable import.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateHoliday = async (e) => {
    e.preventDefault();
    if (!holidayName.trim() || !holidayDate) {
      setToast({ message: 'Please provide holiday name and date.', type: 'warning' });
      return;
    }
    try {
      setLoading(true);
      await academicService.createHoliday({
        name: holidayName.trim(),
        date: holidayDate,
        description: holidayDesc.trim() || undefined
      });
      setToast({ message: `Holiday '${holidayName}' added to academic calendar.`, type: 'success' });
      setHolidayName('');
      setHolidayDate('');
      setHolidayDesc('');
      setShowHolidayModal(false);
      loadAllData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to add holiday.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteHoliday = async (id, name) => {
    if (!window.confirm(`Delete holiday '${name}'?`)) return;
    try {
      await academicService.deleteHoliday(id);
      setToast({ message: 'Holiday removed.', type: 'success' });
      loadAllData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ message: typeof detail === 'string' ? detail : 'Failed to delete holiday.', type: 'error' });
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div style={{ padding: '0.5rem', borderRadius: '10px', background: 'rgba(99, 102, 241, 0.15)', color: '#6366f1' }}>
              <Shield size={24} />
            </div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Admin Console & Face Enrollment Hub</h1>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Manage academic structure, faculty accounts, and annual biometric facial enrollments.
          </p>
        </div>

        <button
          onClick={loadAllData}
          disabled={loading}
          className="btn btn-secondary btn-sm"
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh All
        </button>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex',
        gap: '0.5rem',
        borderBottom: '1px solid var(--border-color)',
        marginBottom: '1.5rem',
        overflowX: 'auto',
        paddingBottom: '0.25rem'
      }}>
        {[
          { id: 'enrollment', label: 'Face Enrollment Hub', icon: Camera, count: enrollments.length },
          { id: 'timetable', label: 'Weekly Timetables', icon: Clock, count: timetableEntries.length },
          { id: 'calendar', label: 'Academic Years & Semesters', icon: Calendar, count: academicYears.length },
          { id: 'subjects', label: 'Subjects & Sections', icon: BookOpen, count: subjects.length },
          { id: 'teachers', label: 'Teachers & Faculty', icon: Users, count: teachers.length }
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.65rem 1rem',
                border: 'none',
                background: isActive ? '#eff6ff' : 'transparent',
                color: isActive ? '#1e3a8a' : 'var(--text-secondary)',
                fontWeight: isActive ? 700 : 500,
                fontSize: '0.875rem',
                borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
                borderBottom: isActive ? '2px solid #2563eb' : '2px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.15s',
                whiteSpace: 'nowrap'
              }}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
              <span style={{
                fontSize: '0.7rem',
                padding: '0.1rem 0.45rem',
                borderRadius: '999px',
                background: isActive ? 'var(--primary)' : '#f1f5f9',
                color: isActive ? 'white' : '#64748b'
              }}>
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* ─── TAB 1: Face Enrollment Hub ─────────────────────────────────────── */}
      {activeTab === 'enrollment' && (
        <div>
          {/* Action Banner */}
          <div className="card" style={{
            background: '#ffffff',
            border: '1px solid var(--border-color)',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
            padding: '1.25rem 1.5rem'
          }}>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                Annual Face Enrollment Lifecycle
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                Face enrollments are strictly valid for 1 academic year. Expired or revoked enrollments prevent attendance authorization.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <Link to="/faculty/register" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.65rem 1rem' }}>
                <UserCheck size={16} /> Register Faculty
              </Link>
              <Link to="/students/register" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.65rem 1rem' }}>
                <Users size={16} /> Register Student
              </Link>
              <button
                onClick={() => setShowEnrollModal(true)}
                className="btn btn-primary"
                style={{ padding: '0.65rem 1.25rem' }}
              >
                <Camera size={18} /> Quick Enroll (Camera)
              </button>
            </div>
          </div>

          {/* Enrollments Table */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                Enrolled Biometrics Directory ({enrollments.length})
              </span>
            </div>

            {enrollments.length === 0 ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Camera size={40} style={{ margin: '0 auto 1rem', opacity: 0.5 }} />
                <p>No face enrollments found for the selected criteria.</p>
                <button
                  onClick={() => setShowEnrollModal(true)}
                  className="btn btn-primary btn-sm"
                  style={{ marginTop: '1rem' }}
                >
                  <Plus size={14} /> Start First Enrollment
                </button>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ width: '100%' }}>
                  <thead>
                    <tr>
                      <th>Person Name</th>
                      <th>Role / Type</th>
                      <th>Identifier</th>
                      <th>Academic Year</th>
                      <th>Validity Window</th>
                      <th>Status</th>
                      <th>Samples</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {enrollments.map((e) => {
                      const isExpired = e.status === 'expired' || !e.is_valid_today;
                      return (
                        <tr key={e.id}>
                          <td>
                            <strong style={{ color: 'var(--text-primary)' }}>{e.person_name || 'N/A'}</strong>
                          </td>
                          <td>
                            <span style={{
                              textTransform: 'capitalize',
                              padding: '0.2rem 0.5rem',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              background: e.person_type === 'student' ? 'rgba(99, 102, 241, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                              color: e.person_type === 'student' ? '#818cf8' : '#10b981'
                            }}>
                              {e.person_type}
                            </span>
                          </td>
                          <td>
                            <code style={{ color: '#818cf8' }}>{e.identifier || '—'}</code>
                          </td>
                          <td>{e.academic_year_name || '—'}</td>
                          <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            {e.valid_from} → {e.valid_until}
                          </td>
                          <td>
                            <span style={{
                              padding: '0.2rem 0.55rem',
                              borderRadius: '999px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              background:
                                e.status === 'active'
                                  ? 'rgba(16, 185, 129, 0.15)'
                                  : e.status === 'expired'
                                  ? 'rgba(239, 68, 68, 0.15)'
                                  : e.status === 'renewed'
                                  ? 'rgba(59, 130, 246, 0.15)'
                                  : 'rgba(107, 114, 128, 0.2)',
                              color:
                                e.status === 'active'
                                  ? '#10b981'
                                  : e.status === 'expired'
                                  ? '#ef4444'
                                  : e.status === 'renewed'
                                  ? '#3b82f6'
                                  : '#9ca3af',
                              border: `1px solid ${
                                e.status === 'active'
                                  ? 'rgba(16, 185, 129, 0.3)'
                                  : e.status === 'expired'
                                  ? 'rgba(239, 68, 68, 0.3)'
                                  : 'rgba(156, 163, 175, 0.2)'
                              }`
                            }}>
                              {e.status}
                            </span>
                          </td>
                          <td>
                            <span style={{ color: '#818cf8', fontWeight: 600 }}>{e.samples_count} templates</span>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <div style={{ display: 'flex', gap: '0.35rem', justifyContent: 'flex-end' }}>
                              {e.status !== 'active' && (
                                <button
                                  onClick={() => {
                                    setSelectedEnrollmentForRenew(e);
                                    setShowRenewModal(true);
                                  }}
                                  className="btn btn-secondary btn-sm"
                                  title="Renew enrollment for next academic year"
                                >
                                  <RefreshCw size={12} /> Renew
                                </button>
                              )}
                              {e.status === 'active' && (
                                <button
                                  onClick={() => handleRevokeEnrollment(e.id)}
                                  className="btn btn-sm"
                                  style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)' }}
                                  title="Revoke enrollment"
                                >
                                  <XCircle size={12} /> Revoke
                                </button>
                              )}
                              <button
                                onClick={() => handleDeleteEnrollment(e.id)}
                                className="btn btn-sm"
                                style={{ background: 'rgba(255, 255, 255, 0.05)', color: 'var(--text-muted)' }}
                                title="Delete enrollment record"
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── TAB: Weekly Timetables & Schedules ─────────────────────────────── */}
      {activeTab === 'timetable' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Top Controls Card */}
          <div className="card" style={{
            background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.08), rgba(16, 185, 129, 0.05))',
            border: '1px solid rgba(99, 102, 241, 0.25)',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            padding: '1.25rem 1.5rem'
          }}>
            <div>
              <div style={{ fontSize: '1.15rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <Clock size={20} color="#6366f1" /> Weekly Timetable Management
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                Manage weekly period slots, bulk import CSV/Excel schedules with conflict detection, and define academic holidays.
              </div>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
              <button
                type="button"
                onClick={() => academicService.downloadTimetableTemplate()}
                className="btn btn-secondary btn-sm"
                title="Download standard CSV template for timetable bulk import"
              >
                <Download size={15} /> Download Template
              </button>
              <button
                type="button"
                onClick={() => {
                  setImportPreview(null);
                  setPreviewRowsEditable([]);
                  setShowImportModal(true);
                }}
                className="btn btn-secondary btn-sm"
              >
                <Upload size={15} /> Import Timetable
              </button>
              <button
                type="button"
                onClick={() => setShowHolidayModal(true)}
                className="btn btn-secondary btn-sm"
              >
                <Calendar size={15} /> Add Holiday
              </button>
              <button
                type="button"
                onClick={() => setShowAddTimetableModal(true)}
                className="btn btn-primary btn-sm"
              >
                <Plus size={15} /> Add Class Slot
              </button>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="card" style={{ padding: '0.85rem 1.25rem', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Filters:</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Semester:</label>
              <select
                className="form-select"
                style={{ width: 'auto', padding: '0.35rem 0.75rem', fontSize: '0.85rem' }}
                value={selectedSemesterForTimetable}
                onChange={(e) => setSelectedSemesterForTimetable(e.target.value)}
              >
                <option value="all">All Semesters</option>
                {semesters.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Section:</label>
              <select
                className="form-select"
                style={{ width: 'auto', padding: '0.35rem 0.75rem', fontSize: '0.85rem' }}
                value={selectedSectionForTimetable}
                onChange={(e) => setSelectedSectionForTimetable(e.target.value)}
              >
                <option value="all">All Sections</option>
                {['CSE-A', 'CSE-B', 'CSE-C', 'IT-A', 'ECE-A'].map((sec) => (
                  <option key={sec} value={sec}>{sec}</option>
                ))}
              </select>
            </div>

            <div style={{ marginLeft: 'auto', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Showing <strong>{
                timetableEntries.filter(entry => {
                  if (selectedSemesterForTimetable !== 'all' && String(entry.semester_id) !== String(selectedSemesterForTimetable)) return false;
                  if (selectedSectionForTimetable !== 'all' && entry.section !== selectedSectionForTimetable) return false;
                  return true;
                }).length
              }</strong> of {timetableEntries.length} timetable entries
            </div>
          </div>

          {/* Timetable Entries Table */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 700 }}>Scheduled Classes</span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Mon–Sat schedule structure</span>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Day & Period</th>
                    <th>Time Window</th>
                    <th>Semester & Section</th>
                    <th>Subject</th>
                    <th>Assigned Faculty</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {timetableEntries
                    .filter(entry => {
                      if (selectedSemesterForTimetable !== 'all' && String(entry.semester_id) !== String(selectedSemesterForTimetable)) return false;
                      if (selectedSectionForTimetable !== 'all' && entry.section !== selectedSectionForTimetable) return false;
                      return true;
                    })
                    .sort((a, b) => {
                      if (a.day_of_week !== b.day_of_week) return a.day_of_week - b.day_of_week;
                      return a.period_number - b.period_number;
                    })
                    .map((entry) => {
                      const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
                      const dayName = days[entry.day_of_week] || `Day ${entry.day_of_week}`;
                      return (
                        <tr key={entry.id}>
                          <td>
                            <strong>{dayName}</strong>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Period #{entry.period_number}</div>
                          </td>
                          <td>
                            <code style={{ fontSize: '0.85rem' }}>{entry.start_time?.slice(0, 5)} - {entry.end_time?.slice(0, 5)}</code>
                          </td>
                          <td>
                            <div style={{ fontWeight: 600 }}>{entry.semester_name || `Sem #${entry.semester_id}`}</div>
                            <span style={{ fontSize: '0.75rem', padding: '0.15rem 0.45rem', borderRadius: '4px', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8' }}>
                              Section {entry.section}
                            </span>
                          </td>
                          <td>
                            <div style={{ fontWeight: 600 }}>{entry.subject_name || `Subject #${entry.subject_id}`}</div>
                            <code style={{ fontSize: '0.75rem', color: '#10b981' }}>{entry.subject_code}</code>
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <Users size={14} color="#818cf8" />
                              <span>{entry.teacher_name || entry.teacher_username || `Teacher #${entry.teacher_id}`}</span>
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>@{entry.teacher_username}</div>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <button
                              type="button"
                              onClick={() => handleDeleteTimetableEntry(entry.id)}
                              className="btn btn-sm"
                              style={{ background: 'transparent', color: '#ef4444' }}
                              title="Delete timetable slot"
                            >
                              <Trash2 size={13} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  {timetableEntries.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                        No timetable entries found. Click "+ Add Class Slot" or "Import Timetable" to populate weekly schedule.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Academic Calendar Holidays Section */}
          <div className="card">
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="card-title">
                <Calendar size={18} color="#f59e0b" /> Academic Holidays & Exceptions ({holidays.length})
              </span>
              <button
                type="button"
                onClick={() => setShowHolidayModal(true)}
                className="btn btn-secondary btn-sm"
              >
                <Plus size={14} /> Add Holiday
              </button>
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              Classes scheduled on registered holidays will automatically be flagged as closed during attendance lookup.
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Holiday Name</th>
                    <th>Description</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {holidays.map((h) => (
                    <tr key={h.id}>
                      <td><code style={{ color: '#f59e0b', fontWeight: 600 }}>{h.date}</code></td>
                      <td><strong>{h.name}</strong></td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{h.description || '—'}</td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          type="button"
                          onClick={() => handleDeleteHoliday(h.id, h.name)}
                          className="btn btn-sm"
                          style={{ background: 'transparent', color: '#ef4444' }}
                          title="Delete holiday"
                        >
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {holidays.length === 0 && (
                    <tr>
                      <td colSpan={4} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>
                        No holidays scheduled. Classes will run according to normal weekly timetable.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 2: Academic Years & Semesters ─────────────────────────────── */}
      {activeTab === 'calendar' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '2rem' }}>
          {/* Academic Years List & Form */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                <Calendar size={18} color="#6366f1" /> Academic Years ({academicYears.length})
              </span>
            </div>

            <form onSubmit={handleAddAcademicYear} style={{ marginBottom: '1.5rem', padding: '1rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
                Add Academic Year
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div>
                  <label className="form-label">Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. 2026-2027"
                    value={ayName}
                    onChange={(e) => setAyName(e.target.value)}
                    required
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', paddingTop: '1.25rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={ayIsCurrent}
                      onChange={(e) => setAyIsCurrent(e.target.checked)}
                    />
                    <span>Set as Current Year</span>
                  </label>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div>
                  <label className="form-label">Start Date *</label>
                  <input
                    type="date"
                    className="form-input"
                    value={ayStartDate}
                    onChange={(e) => setAyStartDate(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">End Date *</label>
                  <input
                    type="date"
                    className="form-input"
                    value={ayEndDate}
                    onChange={(e) => setAyEndDate(e.target.value)}
                    required
                  />
                </div>
              </div>
              <button type="submit" disabled={loading} className="btn btn-primary btn-sm" style={{ width: '100%' }}>
                <Plus size={14} /> Add Academic Year
              </button>
            </form>

            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Year Name</th>
                    <th>Date Span</th>
                    <th>Current</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {academicYears.map((ay) => (
                    <tr key={ay.id}>
                      <td><strong>{ay.name}</strong></td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {ay.start_date} → {ay.end_date}
                      </td>
                      <td>
                        {ay.is_current ? (
                          <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', fontWeight: 700 }}>
                            CURRENT
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>No</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          onClick={() => handleDeleteAcademicYear(ay.id, ay.name)}
                          className="btn btn-sm"
                          style={{ background: 'transparent', color: '#ef4444' }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Semesters List & Form */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                <BookOpen size={18} color="#10b981" /> Semesters ({semesters.length})
              </span>
            </div>

            <form onSubmit={handleAddSemester} style={{ marginBottom: '1.5rem', padding: '1rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
                Add Semester
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div>
                  <label className="form-label">Semester Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Semester 5"
                    value={semName}
                    onChange={(e) => setSemName(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">Academic Year *</label>
                  <select
                    className="form-select"
                    value={semAyId}
                    onChange={(e) => setSemAyId(e.target.value)}
                    required
                  >
                    <option value="">-- Select Year --</option>
                    {academicYears.map((ay) => (
                      <option key={ay.id} value={ay.id}>
                        {ay.name} {ay.is_current ? '(Current)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div>
                  <label className="form-label">Start Date *</label>
                  <input
                    type="date"
                    className="form-input"
                    value={semStartDate}
                    onChange={(e) => setSemStartDate(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">End Date *</label>
                  <input
                    type="date"
                    className="form-input"
                    value={semEndDate}
                    onChange={(e) => setSemEndDate(e.target.value)}
                    required
                  />
                </div>
              </div>
              <button type="submit" disabled={loading} className="btn btn-primary btn-sm" style={{ width: '100%' }}>
                <Plus size={14} /> Add Semester
              </button>
            </form>

            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Semester</th>
                    <th>Dates</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {semesters.map((s) => (
                    <tr key={s.id}>
                      <td><strong>{s.name}</strong></td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {s.start_date} → {s.end_date}
                      </td>
                      <td>
                        <span style={{ fontSize: '0.75rem', color: s.is_active ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                          {s.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          onClick={() => handleDeleteSemester(s.id, s.name)}
                          className="btn btn-sm"
                          style={{ background: 'transparent', color: '#ef4444' }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 3: Subjects & Sections ─────────────────────────────────────── */}
      {activeTab === 'subjects' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '2rem' }}>
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                <Plus size={18} color="#6366f1" /> Create Subject & Section Allocation
              </span>
            </div>

            <form onSubmit={handleAddSubject}>
              <div className="form-group">
                <label className="form-label">Subject Code *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. CS501"
                  value={subCode}
                  onChange={(e) => setSubCode(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Subject Name *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Computer Vision & Biometrics"
                  value={subName}
                  onChange={(e) => setSubName(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Semester *</label>
                  <select
                    className="form-select"
                    value={subSemId}
                    onChange={(e) => setSubSemId(e.target.value)}
                    required
                  >
                    <option value="">-- Select Semester --</option>
                    {semesters.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Section *</label>
                  <select
                    className="form-select"
                    value={subSection}
                    onChange={(e) => setSubSection(e.target.value)}
                    required
                  >
                    <option value="CSE-A">CSE-A</option>
                    <option value="CSE-B">CSE-B</option>
                    <option value="CSE-C">CSE-C</option>
                    <option value="IT-A">IT-A</option>
                    <option value="ECE-A">ECE-A</option>
                  </select>
                </div>
              </div>

              <button type="submit" disabled={loading} className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }}>
                <Plus size={16} /> Save Subject & Section
              </button>
            </form>
          </div>

          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-color)', fontWeight: 700 }}>
              Registered Subjects & Sections ({subjects.length})
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Name</th>
                    <th>Section</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {subjects.map((sub) => (
                    <tr key={sub.id}>
                      <td><code style={{ color: '#818cf8', fontWeight: 700 }}>{sub.code}</code></td>
                      <td>{sub.name}</td>
                      <td>
                        <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8' }}>
                          {sub.section}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          onClick={() => handleDeleteSubject(sub.id, sub.name)}
                          className="btn btn-sm"
                          style={{ background: 'transparent', color: '#ef4444' }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 4: Teachers & Faculty Management ───────────────────────────── */}
      {/* ─── TAB 4: Teachers & Faculty Management ───────────────────────────── */}
      {activeTab === 'teachers' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 380px) 1fr', gap: '2rem' }}>
          <div className="card">
            <div style={{ marginBottom: '1rem', padding: '0.65rem 0.85rem', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 'var(--radius-md)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong style={{ fontSize: '0.85rem', color: '#1e40af' }}>Dedicated Page Available</strong>
                <p style={{ fontSize: '0.75rem', color: '#3b82f6', margin: 0 }}>Full-page registration with live webcam face enrollment</p>
              </div>
              <Link to="/faculty/register" className="btn btn-primary btn-sm" style={{ textDecoration: 'none', whiteSpace: 'nowrap' }}>
                Open Register Page
              </Link>
            </div>

            <div className="card-header">
              <span className="card-title">
                <Users size={18} color="#243B64" /> Provision Faculty Account
              </span>
            </div>

            <form onSubmit={handleAddTeacher}>
              <div className="form-group">
                <label className="form-label">Faculty ID * (Unique)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. FAC-KV01"
                  value={facultyId}
                  onChange={(e) => setFacultyId(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Full Name *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Kavita Ma'am"
                  value={teacherFullName}
                  onChange={(e) => setTeacherFullName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Login Username *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. kavita_maam"
                  value={teacherUsername}
                  onChange={(e) => setTeacherUsername(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Official Email</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder="e.g. kavita@acasportal.edu"
                  value={teacherEmail}
                  onChange={(e) => setTeacherEmail(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Password * (Min 8 characters)</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="••••••••"
                  value={teacherPassword}
                  onChange={(e) => setTeacherPassword(e.target.value)}
                  required
                />
              </div>

              <button type="submit" disabled={loading} className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }}>
                <Plus size={16} /> Register Faculty Member
              </button>
            </form>
          </div>

          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>Authorized Faculty Directory ({teachers.length})</strong>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <Link to="/faculty/register" className="btn btn-primary btn-sm" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', textDecoration: 'none' }}>
                  <Plus size={14} /> Register New Faculty
                </Link>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Admin Authorized Only</span>
              </div>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Faculty Member</th>
                    <th>Faculty ID</th>
                    <th>Assigned Schedule</th>
                    <th>Face Biometrics</th>
                    <th>Account</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {teachers.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <strong>{t.full_name || t.username}</strong>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          <code>{t.username}</code> {t.email ? `· ${t.email}` : ''}
                        </div>
                      </td>
                      <td>
                        <span style={{
                          display: 'inline-block',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '4px',
                          background: '#f1f5f9',
                          fontWeight: 700,
                          fontSize: '0.8rem',
                          fontFamily: 'monospace',
                          color: '#0f172a'
                        }}>
                          {t.faculty_id || 'N/A'}
                        </span>
                      </td>
                      <td>
                        {t.assigned_subjects && t.assigned_subjects.length > 0 ? (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                            {t.assigned_subjects.map((sub, i) => (
                              <span key={i} style={{ fontSize: '0.72rem', background: '#e0e7ff', color: '#3730a3', padding: '0.15rem 0.4rem', borderRadius: '3px' }}>
                                {sub}
                              </span>
                            ))}
                            {t.assigned_sections && t.assigned_sections.length > 0 && (
                              <span style={{ fontSize: '0.72rem', background: '#fef3c7', color: '#92400e', padding: '0.15rem 0.4rem', borderRadius: '3px' }}>
                                Sec {t.assigned_sections.join(', ')}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>None assigned</span>
                        )}
                      </td>
                      <td>
                        {t.has_face_enrollment ? (
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.3rem',
                            fontSize: '0.75rem',
                            color: '#059669',
                            background: '#d1fae5',
                            padding: '0.2rem 0.5rem',
                            borderRadius: '12px',
                            fontWeight: 600
                          }}>
                            <CheckCircle2 size={12} /> Enrolled ({t.sample_count || 1} samples)
                          </span>
                        ) : (
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.3rem',
                            fontSize: '0.75rem',
                            color: '#b45309',
                            background: '#fef3c7',
                            padding: '0.2rem 0.5rem',
                            borderRadius: '12px',
                            fontWeight: 600
                          }}>
                            <AlertCircle size={12} /> Not Enrolled
                          </span>
                        )}
                      </td>
                      <td>
                        <span style={{ fontSize: '0.75rem', color: t.is_active ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                          {t.is_active ? 'Active' : 'Deactivated'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                          <button
                            onClick={() => handleOpenFacultyFaceEnroll(t)}
                            className="btn btn-primary btn-sm"
                            title={t.has_face_enrollment ? 'Re-enroll facial biometrics via webcam' : 'Enroll facial biometrics via webcam'}
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.6rem' }}
                          >
                            <Camera size={13} /> {t.has_face_enrollment ? 'Re-enroll' : 'Enroll Face'}
                          </button>
                          <button
                            onClick={() => handleToggleUserActive(t)}
                            className="btn btn-secondary btn-sm"
                            title={t.is_active ? 'Deactivate faculty account' : 'Activate faculty account'}
                          >
                            {t.is_active ? <UserX size={13} color="#f87171" /> : <UserCheck size={13} color="#34d399" />}
                          </button>
                          <button
                            onClick={() => handleDeleteUser(t.id, t.username)}
                            className="btn btn-sm"
                            style={{ background: 'transparent', color: '#ef4444' }}
                            title="Delete faculty account"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: Enroll New Face (Camera) ─────────────────────────────────── */}
      {showEnrollModal && (
        <Modal
          title="Biometric Face Enrollment (Camera Interface)"
          onClose={() => {
            setShowEnrollModal(false);
            setCapturedImages([]);
          }}
          maxWidth="680px"
        >
          <form onSubmit={handleRegisterFace}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              {/* Type Switcher */}
              <div>
                <label className="form-label">Person Type *</label>
                <select
                  className="form-select"
                  value={enrollPersonType}
                  onChange={(e) => {
                    setEnrollPersonType(e.target.value);
                    setEnrollTargetId('');
                  }}
                  required
                >
                  <option value="student">Student</option>
                  <option value="teacher">Teacher / Faculty</option>
                </select>
              </div>

              {/* Target Person Select */}
              <div>
                <label className="form-label">Select Person *</label>
                <select
                  className="form-select"
                  value={enrollTargetId}
                  onChange={(e) => setEnrollTargetId(e.target.value)}
                  required
                >
                  <option value="">-- Choose {enrollPersonType} --</option>
                  {enrollPersonType === 'student' ? (
                    students.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.roll_number} - {s.section})
                      </option>
                    ))
                  ) : (
                    teachers.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.full_name || t.username} ({t.username})
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Academic Year (Enforces 1-Year Validity) *</label>
              <select
                className="form-select"
                value={enrollAcademicYearId}
                onChange={(e) => setEnrollAcademicYearId(e.target.value)}
                required
              >
                <option value="">-- Choose Academic Year --</option>
                {academicYears.map((ay) => (
                  <option key={ay.id} value={ay.id}>
                    {ay.name} ({ay.start_date} to {ay.end_date}) {ay.is_current ? '★ CURRENT' : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Webcam Capture Component */}
            <div style={{ margin: '1rem 0' }}>
              <WebcamCapture
                onCaptureComplete={(imgs) => setCapturedImages(imgs)}
                maxImages={5}
                requiredImages={2}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Enrollment Notes / Verification Remarks</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Identity verified via institute ID card."
                value={enrollNotes}
                onChange={(e) => setEnrollNotes(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
              <button
                type="button"
                onClick={() => setShowEnrollModal(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || capturedImages.length < 1}
                className="btn btn-primary"
              >
                <CheckCircle2 size={16} />
                <span>{loading ? 'Validating Biometrics...' : 'Register Biometrics'}</span>
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ─── MODAL: Renew Face Enrollment ───────────────────────────────────── */}
      {showRenewModal && selectedEnrollmentForRenew && (
        <Modal
          title={`Renew Face Enrollment: ${selectedEnrollmentForRenew.person_name}`}
          onClose={() => {
            setShowRenewModal(false);
            setSelectedEnrollmentForRenew(null);
          }}
          maxWidth="500px"
        >
          <form onSubmit={handleRenewEnrollment}>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
              Renewing extends biometric validity for an additional academic year while preserving existing normalized templates.
            </p>

            <div className="form-group">
              <label className="form-label">Target Academic Year *</label>
              <select
                className="form-select"
                value={renewAcademicYearId}
                onChange={(e) => setRenewAcademicYearId(e.target.value)}
                required
              >
                <option value="">-- Choose Academic Year --</option>
                {academicYears.map((ay) => (
                  <option key={ay.id} value={ay.id}>
                    {ay.name} ({ay.start_date} to {ay.end_date})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
              <button
                type="button"
                onClick={() => setShowRenewModal(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !renewAcademicYearId}
                className="btn btn-primary"
              >
                <RefreshCw size={16} /> Confirm Renewal
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ─── MODAL: Add Timetable Entry ─────────────────────────────────────── */}
      {showAddTimetableModal && (
        <Modal
          title="Add Weekly Timetable Slot"
          onClose={() => setShowAddTimetableModal(false)}
          maxWidth="600px"
        >
          <form onSubmit={handleCreateTimetableEntry}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label className="form-label">Semester *</label>
                <select
                  className="form-select"
                  value={ttSemId}
                  onChange={(e) => {
                    setTtSemId(e.target.value);
                    setTtSubId('');
                  }}
                  required
                >
                  <option value="">-- Select Semester --</option>
                  {semesters.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="form-label">Section *</label>
                <select
                  className="form-select"
                  value={ttSection}
                  onChange={(e) => setTtSection(e.target.value)}
                  required
                >
                  <option value="CSE-A">CSE-A</option>
                  <option value="CSE-B">CSE-B</option>
                  <option value="CSE-C">CSE-C</option>
                  <option value="IT-A">IT-A</option>
                  <option value="ECE-A">ECE-A</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label className="form-label">Subject *</label>
                <select
                  className="form-select"
                  value={ttSubId}
                  onChange={(e) => setTtSubId(e.target.value)}
                  required
                >
                  <option value="">-- Select Subject --</option>
                  {subjects
                    .filter((sub) => !ttSemId || String(sub.semester_id) === String(ttSemId))
                    .map((sub) => (
                      <option key={sub.id} value={sub.id}>
                        {sub.code} - {sub.name} ({sub.section})
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="form-label">Assigned Teacher / Faculty *</label>
                <select
                  className="form-select"
                  value={ttTeacherId}
                  onChange={(e) => setTtTeacherId(e.target.value)}
                  required
                >
                  <option value="">-- Select Teacher --</option>
                  {teachers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.full_name || t.username} ({t.username})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label className="form-label">Day of Week *</label>
                <select
                  className="form-select"
                  value={ttDay}
                  onChange={(e) => setTtDay(Number(e.target.value))}
                  required
                >
                  <option value={0}>Monday</option>
                  <option value={1}>Tuesday</option>
                  <option value={2}>Wednesday</option>
                  <option value={3}>Thursday</option>
                  <option value={4}>Friday</option>
                  <option value={5}>Saturday</option>
                </select>
              </div>

              <div>
                <label className="form-label">Period Number *</label>
                <input
                  type="number"
                  min="1"
                  max="12"
                  className="form-input"
                  value={ttPeriod}
                  onChange={(e) => setTtPeriod(Number(e.target.value))}
                  required
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label className="form-label">Start Time *</label>
                <input
                  type="time"
                  className="form-input"
                  value={ttStartTime}
                  onChange={(e) => setTtStartTime(e.target.value)}
                  required
                />
              </div>

              <div>
                <label className="form-label">End Time *</label>
                <input
                  type="time"
                  className="form-input"
                  value={ttEndTime}
                  onChange={(e) => setTtEndTime(e.target.value)}
                  required
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
              <button
                type="button"
                onClick={() => setShowAddTimetableModal(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
              >
                <Plus size={16} /> Save Timetable Slot
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ─── MODAL: Import Timetable (CSV/Excel) ─────────────────────────────── */}
      {showImportModal && (
        <Modal
          title="Import Timetable (CSV / Excel)"
          onClose={() => {
            setShowImportModal(false);
            setImportPreview(null);
            setPreviewRowsEditable([]);
          }}
          maxWidth="900px"
        >
          <div>
            {!importPreview ? (
              <div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
                  Upload a spreadsheet file (.csv, .xlsx, .xls) containing weekly timetable schedule definitions.
                  The system validates column headers, checks teacher availability, verifies section periods, and detects conflicts before saving.
                </p>

                <div style={{
                  border: '2px dashed var(--border-color)',
                  borderRadius: 'var(--radius-lg)',
                  padding: '2.5rem',
                  textAlign: 'center',
                  background: 'rgba(15, 23, 42, 0.4)'
                }}>
                  <FileSpreadsheet size={40} color="#6366f1" style={{ margin: '0 auto 1rem auto' }} />
                  <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Select CSV or Excel Timetable File</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                    Supported formats: .csv, .xlsx, .xls
                  </div>
                  <input
                    type="file"
                    accept=".csv, .xlsx, .xls, text/csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
                    onChange={handleFileSelectForImport}
                    style={{ fontSize: '0.85rem' }}
                  />
                </div>

                <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <button
                    type="button"
                    onClick={() => academicService.downloadTimetableTemplate()}
                    className="btn btn-secondary btn-sm"
                  >
                    <Download size={14} /> Download Sample CSV Template
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowImportModal(false)}
                    className="btn btn-secondary"
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : (
              <div>
                {/* Preview Summary */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
                  <div style={{ padding: '0.5rem 1rem', borderRadius: '6px', background: 'rgba(255, 255, 255, 0.05)', fontSize: '0.85rem' }}>
                    Total Rows: <strong>{importPreview.total_rows}</strong>
                  </div>
                  <div style={{ padding: '0.5rem 1rem', borderRadius: '6px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontSize: '0.85rem' }}>
                    Valid: <strong>{importPreview.valid_count}</strong>
                  </div>
                  <div style={{ padding: '0.5rem 1rem', borderRadius: '6px', background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', fontSize: '0.85rem' }}>
                    Conflicts: <strong>{importPreview.conflict_count}</strong>
                  </div>
                  <div style={{ padding: '0.5rem 1rem', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', fontSize: '0.85rem' }}>
                    Errors: <strong>{importPreview.error_count}</strong>
                  </div>
                </div>

                {importPreview.conflict_count > 0 && (
                  <div style={{
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    background: 'rgba(245, 158, 11, 0.1)',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    marginBottom: '1rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem'
                  }}>
                    <AlertTriangle size={18} color="#f59e0b" />
                    <label style={{ fontSize: '0.85rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <input
                        type="checkbox"
                        checked={replaceConflicts}
                        onChange={(e) => setReplaceConflicts(e.target.checked)}
                      />
                      <span><strong>Overwrite existing database conflicts</strong> with rows from this import file</span>
                    </label>
                  </div>
                )}

                {/* Preview Table */}
                <div style={{ maxHeight: '360px', overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', marginBottom: '1.25rem' }}>
                  <table className="data-table" style={{ width: '100%', fontSize: '0.8rem' }}>
                    <thead style={{ position: 'sticky', top: 0, background: '#1e293b', zIndex: 1 }}>
                      <tr>
                        <th>Row</th>
                        <th>Status</th>
                        <th>Semester / Section</th>
                        <th>Day / Period / Time</th>
                        <th>Subject / Faculty</th>
                        <th>Issues / Validation Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importPreview.rows.map((r) => {
                        const isErr = r.status === 'error';
                        const isConflict = r.status === 'conflict';
                        const isValid = r.status === 'valid';
                        return (
                          <tr key={r.row_index} style={{ background: isErr ? 'rgba(239, 68, 68, 0.05)' : isConflict ? 'rgba(245, 158, 11, 0.05)' : 'transparent' }}>
                            <td>#{r.row_index}</td>
                            <td>
                              <span style={{
                                padding: '0.2rem 0.5rem',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                background: isValid ? 'rgba(16, 185, 129, 0.2)' : isConflict ? 'rgba(245, 158, 11, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                color: isValid ? '#10b981' : isConflict ? '#f59e0b' : '#ef4444'
                              }}>
                                {r.status.toUpperCase()}
                              </span>
                            </td>
                            <td>
                              <div>{r.raw_data.semester_name || '—'}</div>
                              <div style={{ color: 'var(--text-muted)' }}>Sec: {r.raw_data.section || '—'}</div>
                            </td>
                            <td>
                              <div>{r.raw_data.day || '—'}, P{r.raw_data.period_number || '—'}</div>
                              <div style={{ color: 'var(--text-muted)' }}>{r.raw_data.start_time} - {r.raw_data.end_time}</div>
                            </td>
                            <td>
                              <div>{r.raw_data.subject_code || r.raw_data.subject_name || '—'}</div>
                              <div style={{ color: 'var(--text-muted)' }}>{r.raw_data.teacher_username || r.raw_data.teacher_name || '—'}</div>
                            </td>
                            <td>
                              {r.errors && r.errors.length > 0 ? (
                                <ul style={{ margin: 0, paddingLeft: '1rem', color: '#ef4444' }}>
                                  {r.errors.map((err, i) => <li key={i}>{err}</li>)}
                                </ul>
                              ) : r.conflicts && r.conflicts.length > 0 ? (
                                <ul style={{ margin: 0, paddingLeft: '1rem', color: '#f59e0b' }}>
                                  {r.conflicts.map((conf, i) => <li key={i}>{conf}</li>)}
                                </ul>
                              ) : (
                                <span style={{ color: '#10b981' }}>Ready to import</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    onClick={() => {
                      setImportPreview(null);
                      setPreviewRowsEditable([]);
                    }}
                    className="btn btn-secondary"
                  >
                    Select Different File
                  </button>
                  <button
                    type="button"
                    onClick={handleCommitImport}
                    disabled={loading || (importPreview.valid_count === 0 && (!replaceConflicts || importPreview.conflict_count === 0))}
                    className="btn btn-primary"
                  >
                    <CheckCircle2 size={16} />
                    <span>{loading ? 'Saving Records...' : `Commit & Save Valid Rows (${importPreview.valid_count + (replaceConflicts ? importPreview.conflict_count : 0)})`}</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* ─── MODAL: Add Holiday ─────────────────────────────────────────────── */}
      {showHolidayModal && (
        <Modal
          title="Add Academic Holiday / Non-Instructional Day"
          onClose={() => setShowHolidayModal(false)}
          maxWidth="500px"
        >
          <form onSubmit={handleCreateHoliday}>
            <div className="form-group">
              <label className="form-label">Holiday Name *</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Gandhi Jayanti, Diwali Break"
                value={holidayName}
                onChange={(e) => setHolidayName(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Date *</label>
              <input
                type="date"
                className="form-input"
                value={holidayDate}
                onChange={(e) => setHolidayDate(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Description / Remarks (Optional)</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Gazetted holiday, institute closed"
                value={holidayDesc}
                onChange={(e) => setHolidayDesc(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
              <button
                type="button"
                onClick={() => setShowHolidayModal(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
              >
                <Plus size={16} /> Save Holiday
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
