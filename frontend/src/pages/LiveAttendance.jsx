import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Video,
  VideoOff,
  Play,
  Square,
  Users,
  UserCheck,
  Clock,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  BookOpen,
  Volume2,
  VolumeX,
  ShieldCheck,
  ShieldAlert,
  Camera,
  Calendar,
  Flag,
  Info,
  Lock
} from 'lucide-react';
import { attendanceService } from '../services/attendanceService';
import { modelService } from '../services/modelService';
import { useAuth } from '../context/AuthContext';
import { Modal } from '../components/Modal';
import { NotificationToast } from '../components/NotificationToast';

export const LiveAttendance = () => {
  const { user } = useAuth();

  // Video and Canvas Refs
  const videoRef = useRef(null);
  const overlayCanvasRef = useRef(null);
  const hiddenCanvasRef = useRef(null);
  const streamRef = useRef(null);
  const processingRef = useRef(false);
  const timerRef = useRef(null);
  const countdownIntervalRef = useRef(null);

  // Verification Modal Camera Refs
  const verifyVideoRef = useRef(null);
  const verifyCanvasRef = useRef(null);
  const verifyStreamRef = useRef(null);

  // Active Session State
  const [activeSession, setActiveSession] = useState(null);
  const [sessionDeadlineSeconds, setSessionDeadlineSeconds] = useState(null);
  const [isDeadlineExpired, setIsDeadlineExpired] = useState(false);

  // Teacher Slot Selection
  const [assignedSlots, setAssignedSlots] = useState([]);
  const [selectedSlotId, setSelectedSlotId] = useState('');
  const [isLoadingSlots, setIsLoadingSlots] = useState(false);
  const [manualSubject, setManualSubject] = useState('Computer Vision');
  const [manualSection, setManualSection] = useState('CSE-A');

  // Verification Modal State
  const [isVerifyModalOpen, setIsVerifyModalOpen] = useState(false);
  const [isVerifyingFace, setIsVerifyingFace] = useState(false);
  const [verifyError, setVerifyError] = useState(null);
  const [verifyCameraActive, setVerifyCameraActive] = useState(false);

  // Session Closure / Review Modal State
  const [isCloseModalOpen, setIsCloseModalOpen] = useState(false);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [closeReason, setCloseReason] = useState('Class concluded normally');
  const [reviewReason, setReviewReason] = useState('Attendance anomalies / biometric review required');
  const [isSubmittingClose, setIsSubmittingClose] = useState(false);

  // Classroom Camera & Recognition State
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [modelStatus, setModelStatus] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processIntervalMs] = useState(1200);
  const [soundEnabled, setSoundEnabled] = useState(true);

  // Live Attendance Roster State
  const [presentStudents, setPresentStudents] = useState([]);
  const [lastDetections, setLastDetections] = useState([]);
  const [liveToast, setLiveToast] = useState(null);

  // Fetch Teacher Assigned Slots
  const fetchAssignedSlots = async () => {
    try {
      setIsLoadingSlots(true);
      const slots = await attendanceService.getTeacherAssignedSlots();
      setAssignedSlots(slots || []);
      if (slots && slots.length > 0) {
        // Default to first slot that can start now or first slot
        const readySlot = slots.find((s) => s.can_start_now);
        setSelectedSlotId(readySlot ? String(readySlot.timetable_entry_id) : String(slots[0].timetable_entry_id));
      }
    } catch (err) {
      console.warn('Could not load assigned slots for teacher:', err);
    } finally {
      setIsLoadingSlots(false);
    }
  };

  // Load initial session & model status
  const initializeSession = async () => {
    try {
      const [currSession, mStatus] = await Promise.all([
        attendanceService.getActiveSession(),
        modelService.getStatus()
      ]);
      setActiveSession(currSession);
      setModelStatus(mStatus);

      if (currSession) {
        const history = await attendanceService.getHistory({ session_id: currSession.id });
        setPresentStudents(history.records || []);
      }
    } catch (err) {
      console.error('Initialization error:', err);
    }
  };

  useEffect(() => {
    initializeSession();
    fetchAssignedSlots();
  }, []);

  // Update 15-minute countdown clock
  useEffect(() => {
    if (!activeSession) {
      setSessionDeadlineSeconds(null);
      setIsDeadlineExpired(false);
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
      return;
    }

    const updateCountdown = () => {
      if (!activeSession.recognition_window_end) {
        setSessionDeadlineSeconds(null);
        return;
      }
      const endMs = new Date(activeSession.recognition_window_end).getTime();
      const nowMs = Date.now();
      const diffSec = Math.floor((endMs - nowMs) / 1000);

      if (diffSec <= 0) {
        setSessionDeadlineSeconds(0);
        setIsDeadlineExpired(true);
      } else {
        setSessionDeadlineSeconds(diffSec);
        setIsDeadlineExpired(false);
      }
    };

    updateCountdown();
    countdownIntervalRef.current = setInterval(updateCountdown, 1000);

    return () => {
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    };
  }, [activeSession]);

  // Web Audio chime for successful attendance mark
  const playAttendanceChime = () => {
    if (!soundEnabled) return;
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.3);
    } catch (e) {
      // quiet fail
    }
  };

  // Start Classroom Camera Stream
  const startCamera = async () => {
    try {
      setCameraError(null);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: 'user'
        },
        audio: false
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setCameraActive(true);
    } catch (err) {
      console.error('Camera access error:', err);
      setCameraError('Unable to access classroom webcam. Please check browser permissions.');
      setCameraActive(false);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  };

  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Verification Camera Stream Management
  const startVerifyCamera = async () => {
    try {
      setVerifyError(null);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: 'user'
        },
        audio: false
      });
      verifyStreamRef.current = stream;
      if (verifyVideoRef.current) {
        verifyVideoRef.current.srcObject = stream;
        verifyVideoRef.current.play();
      }
      setVerifyCameraActive(true);
    } catch (err) {
      console.error('Teacher verification camera error:', err);
      setVerifyError('Camera access failed. Please ensure camera permissions are granted.');
      setVerifyCameraActive(false);
    }
  };

  const stopVerifyCamera = () => {
    if (verifyStreamRef.current) {
      verifyStreamRef.current.getTracks().forEach((track) => track.stop());
      verifyStreamRef.current = null;
    }
    setVerifyCameraActive(false);
  };

  const openVerifyModal = () => {
    setIsVerifyModalOpen(true);
    setVerifyError(null);
    setTimeout(() => {
      startVerifyCamera();
    }, 150);
  };

  const closeVerifyModal = () => {
    stopVerifyCamera();
    setIsVerifyModalOpen(false);
    setVerifyError(null);
  };

  // Perform Teacher Face Verification and Start Session
  const handleVerifyAndStartSession = async () => {
    if (!verifyVideoRef.current || !verifyCanvasRef.current) {
      setVerifyError('Camera is not ready. Please wait a moment and try again.');
      return;
    }

    try {
      setIsVerifyingFace(true);
      setVerifyError(null);

      const video = verifyVideoRef.current;
      const canvas = verifyCanvasRef.current;
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;

      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const base64Image = canvas.toDataURL('image/jpeg', 0.9);

      // Determine payload based on selected slot or manual entry
      const payload = {
        face_image: base64Image,
        client_timestamp: new Date().toISOString()
      };

      if (selectedSlotId) {
        payload.timetable_entry_id = parseInt(selectedSlotId, 10);
      } else {
        payload.subject = manualSubject;
        payload.section = manualSection;
      }

      // Call Backend Phase 5 Authorized Start API
      const newSession = await attendanceService.startAuthorizedSession(payload);

      setActiveSession(newSession);
      setPresentStudents([]);
      setLastDetections([]);
      closeVerifyModal();

      setLiveToast({
        message: `Biometric verification successful! Attendance session started for ${newSession.subject} (${newSession.section}).`,
        type: 'success'
      });
    } catch (err) {
      console.error('Session start verification error:', err);
      const detail = err.response?.data?.detail;
      setVerifyError(detail || 'Biometric verification failed. Please align your face and try again.');
    } finally {
      setIsVerifyingFace(false);
    }
  };

  // Close Session
  const handleConfirmClose = async () => {
    if (!activeSession) return;
    try {
      setIsSubmittingClose(true);
      await attendanceService.closeSession(activeSession.id, {
        reason: closeReason,
        require_review: false
      });
      setIsCloseModalOpen(false);
      setActiveSession(null);
      setLiveToast({
        message: `Attendance session concluded successfully. Total ${presentStudents.length} students marked.`,
        type: 'info'
      });
    } catch (err) {
      setLiveToast({
        message: err.response?.data?.detail || 'Failed to close session.',
        type: 'error'
      });
    } finally {
      setIsSubmittingClose(false);
    }
  };

  // Flag Session for Review
  const handleConfirmReview = async () => {
    if (!activeSession) return;
    try {
      setIsSubmittingClose(true);
      const updated = await attendanceService.flagSessionReview(activeSession.id, {
        reason: reviewReason
      });
      setIsReviewModalOpen(false);
      setActiveSession(updated);
      setLiveToast({
        message: `Session flagged for administrative audit review: "${reviewReason}"`,
        type: 'warning'
      });
    } catch (err) {
      setLiveToast({
        message: err.response?.data?.detail || 'Failed to flag session.',
        type: 'error'
      });
    } finally {
      setIsSubmittingClose(false);
    }
  };

  // Draw Bounding Boxes on Overlay Canvas
  const drawBoundingBoxes = (detections, videoWidth, videoHeight) => {
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;

    canvas.width = videoWidth;
    canvas.height = videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    detections.forEach((det) => {
      const { box, is_known, name, roll_number, confidence, status_message, attendance_marked } = det;
      const { x, y, width, height } = box;

      const isRecognized = is_known && name !== 'Unknown';
      let strokeColor = '#f59e0b';
      let bgColor = 'rgba(245, 158, 11, 0.88)';

      if (isRecognized) {
        if (attendance_marked || status_message.includes('Marked Present')) {
          strokeColor = '#10b981';
          bgColor = 'rgba(16, 185, 129, 0.90)';
        } else if (
          status_message.includes('Wrong Section') ||
          status_message.includes('Expired') ||
          status_message.includes('Invalid') ||
          status_message.includes('Failed')
        ) {
          strokeColor = '#ef4444';
          bgColor = 'rgba(239, 68, 68, 0.90)';
        } else {
          strokeColor = '#6366f1';
          bgColor = 'rgba(99, 102, 241, 0.90)';
        }
      }

      ctx.lineWidth = 3;
      ctx.strokeStyle = strokeColor;
      ctx.strokeRect(x, y, width, height);

      const cornerLen = Math.min(width, height) * 0.2;
      ctx.lineWidth = 5;
      ctx.strokeStyle = strokeColor;
      ctx.beginPath();
      ctx.moveTo(x, y + cornerLen);
      ctx.lineTo(x, y);
      ctx.lineTo(x + cornerLen, y);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(x + width - cornerLen, y);
      ctx.lineTo(x + width, y);
      ctx.lineTo(x + width, y + cornerLen);
      ctx.stroke();

      const labelText = isRecognized ? `${name} (${roll_number})` : 'Unknown Student';
      const subText = isRecognized
        ? `${status_message} (Dist: ${confidence})`
        : `Unregistered Face (Dist: ${confidence})`;

      ctx.font = 'bold 13px Plus Jakarta Sans, sans-serif';
      const textWidth = Math.max(ctx.measureText(labelText).width, ctx.measureText(subText).width) + 16;
      const bannerHeight = 38;

      ctx.fillStyle = bgColor;
      ctx.fillRect(x, Math.max(0, y - bannerHeight), textWidth, bannerHeight);

      ctx.fillStyle = '#ffffff';
      ctx.fillText(labelText, x + 8, Math.max(0, y - bannerHeight) + 16);
      ctx.font = '11px Plus Jakarta Sans, sans-serif';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.92)';
      ctx.fillText(subText, x + 8, Math.max(0, y - bannerHeight) + 32);
    });
  };

  // Continuous frame processing loop
  const processFrame = useCallback(async () => {
    if (processingRef.current || !cameraActive || !videoRef.current) return;

    const video = videoRef.current;
    if (video.readyState !== 4) return;

    try {
      processingRef.current = true;
      setIsProcessing(true);

      const hiddenCanvas = hiddenCanvasRef.current;
      hiddenCanvas.width = video.videoWidth || 640;
      hiddenCanvas.height = video.videoHeight || 480;

      const ctx = hiddenCanvas.getContext('2d');
      ctx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);

      const base64Image = hiddenCanvas.toDataURL('image/jpeg', 0.85);

      const response = await attendanceService.recognizeFrame(
        base64Image,
        activeSession ? activeSession.id : null,
        true
      );

      setLastDetections(response.detections || []);
      drawBoundingBoxes(response.detections || [], hiddenCanvas.width, hiddenCanvas.height);

      const newMarks = (response.detections || []).filter((d) => d.attendance_marked);
      if (newMarks.length > 0) {
        newMarks.forEach((m) => {
          playAttendanceChime();
          setLiveToast({
            message: `✓ Marked Present: ${m.name} (${m.roll_number})`,
            type: 'success'
          });

          setPresentStudents((prev) => {
            if (prev.some((p) => p.student_id === m.student_id)) return prev;
            return [
              {
                id: Date.now(),
                student_id: m.student_id,
                student_name: m.name,
                roll_number: m.roll_number,
                section: m.section,
                time: new Date().toLocaleTimeString(),
                confidence_score: m.confidence
              },
              ...prev
            ];
          });
        });
      }
    } catch (err) {
      console.error('Frame recognition error:', err);
    } finally {
      processingRef.current = false;
      setIsProcessing(false);
    }
  }, [cameraActive, activeSession, soundEnabled]);

  useEffect(() => {
    if (cameraActive) {
      timerRef.current = setInterval(processFrame, processIntervalMs);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [cameraActive, processFrame, processIntervalMs]);

  // Format seconds to MM:SS
  const formatTime = (totalSec) => {
    if (totalSec === null || totalSec === undefined) return '--:--';
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const selectedSlot = assignedSlots.find((s) => String(s.timetable_entry_id) === String(selectedSlotId));

  return (
    <div className="page-body">
      {liveToast && (
        <NotificationToast
          message={liveToast.message}
          type={liveToast.type}
          onClose={() => setLiveToast(null)}
        />
      )}

      {/* Header */}
      <div style={{
        marginBottom: '1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Teacher Attendance Terminal</h1>
            {activeSession ? (
              activeSession.status === 'review-required' ? (
                <span className="badge badge-warning" style={{ background: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.4)' }}>
                  <ShieldAlert size={14} style={{ marginRight: '4px' }} /> Review Required
                </span>
              ) : (
                <span className="badge badge-success">
                  <span className="pulse-indicator pulse-green" style={{ width: '6px', height: '6px' }} />
                  Session Active
                </span>
              )
            ) : (
              <span className="badge badge-warning">Standby Mode</span>
            )}
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
            Phase 5 Teacher Biometric Verification & Authorized Timetable Session Management.
          </p>
        </div>

        {/* Audio & Refresh Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className="btn btn-secondary btn-sm"
            title={soundEnabled ? 'Mute Chime' : 'Enable Chime'}
          >
            {soundEnabled ? <Volume2 size={16} color="#10b981" /> : <VolumeX size={16} color="#ef4444" />}
            <span>{soundEnabled ? 'Chime ON' : 'Chime Muted'}</span>
          </button>
        </div>
      </div>

      {/* Active Session Management Banner */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1.25rem' }}>
        {activeSession ? (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                    Active Subject
                  </span>
                  <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                    {activeSession.subject}
                  </div>
                </div>

                <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: '1.5rem' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                    Section
                  </span>
                  <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#818cf8' }}>
                    {activeSession.section}
                  </div>
                </div>

                <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: '1.5rem' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                    Instructor
                  </span>
                  <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                    {activeSession.teacher_name || user?.name || 'Authorized Faculty'}
                  </div>
                </div>

                <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: '1.5rem' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                    Started At
                  </span>
                  <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    {new Date(activeSession.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <button
                  type="button"
                  onClick={() => setIsReviewModalOpen(true)}
                  className="btn btn-secondary btn-sm"
                  style={{ borderColor: 'rgba(245, 158, 11, 0.4)', color: '#f59e0b' }}
                >
                  <Flag size={14} />
                  <span>Flag Review</span>
                </button>

                <button
                  type="button"
                  onClick={() => setIsCloseModalOpen(true)}
                  className="btn btn-danger"
                  style={{ padding: '0.65rem 1.4rem' }}
                >
                  <Square size={16} />
                  <span>Close Session</span>
                </button>
              </div>
            </div>

            {/* 15-Minute Deadline Countdown Bar */}
            <div style={{
              marginTop: '1.25rem',
              padding: '0.9rem 1.2rem',
              borderRadius: 'var(--radius-md)',
              background: isDeadlineExpired
                ? 'rgba(239, 68, 68, 0.12)'
                : sessionDeadlineSeconds < 300
                ? 'rgba(245, 158, 11, 0.12)'
                : 'rgba(16, 185, 129, 0.08)',
              border: `1px solid ${
                isDeadlineExpired
                  ? 'rgba(239, 68, 68, 0.35)'
                  : sessionDeadlineSeconds < 300
                  ? 'rgba(245, 158, 11, 0.35)'
                  : 'rgba(16, 185, 129, 0.25)'
              }`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '1rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Clock
                  size={20}
                  color={isDeadlineExpired ? '#ef4444' : sessionDeadlineSeconds < 300 ? '#f59e0b' : '#10b981'}
                />
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.9rem', color: isDeadlineExpired ? '#ef4444' : 'var(--text-primary)' }}>
                    {isDeadlineExpired ? '15-Minute Attendance Deadline Expired' : 'Attendance Window Countdown'}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {isDeadlineExpired
                      ? 'Attendance logging has closed for this lecture slot.'
                      : 'Students must verify within the initial 15-minute window.'}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{
                  fontSize: '1.5rem',
                  fontWeight: 900,
                  fontFamily: 'monospace',
                  letterSpacing: '1px',
                  color: isDeadlineExpired ? '#ef4444' : sessionDeadlineSeconds < 300 ? '#f59e0b' : '#10b981'
                }}>
                  {formatTime(sessionDeadlineSeconds)}
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Teacher Slot Selector & Biometric Start */
          <div>
            <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ShieldCheck size={18} color="#6366f1" />
                  Select Assigned Timetable Class to Authorize
                </h3>
                <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  Sessions require backend timetable slot verification and teacher biometric facial confirmation.
                </p>
              </div>

              <button
                type="button"
                onClick={fetchAssignedSlots}
                className="btn btn-secondary btn-sm"
                disabled={isLoadingSlots}
              >
                <RefreshCw size={13} className={isLoadingSlots ? 'spin' : ''} />
                <span>Refresh Schedule</span>
              </button>
            </div>

            {assignedSlots.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem' }}>
                {assignedSlots.map((slot) => {
                  const isSelected = String(slot.timetable_entry_id) === String(selectedSlotId);
                  return (
                    <div
                      key={slot.timetable_entry_id}
                      onClick={() => setSelectedSlotId(String(slot.timetable_entry_id))}
                      style={{
                        padding: '1rem',
                        borderRadius: 'var(--radius-md)',
                        background: isSelected ? 'var(--primary-light)' : '#ffffff',
                        border: `2px solid ${isSelected ? 'var(--primary)' : 'var(--border-color)'}`,
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                        <span style={{ fontWeight: 800, fontSize: '0.95rem', color: isSelected ? 'var(--primary)' : 'var(--text-primary)' }}>
                          {slot.subject_name}
                        </span>
                        <span className="badge badge-primary" style={{ fontSize: '0.7rem' }}>
                          Period {slot.period_number}
                        </span>
                      </div>

                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                        <span>Code: <code>{slot.subject_code}</code></span> • <span>Section: <strong>{slot.section}</strong></span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                        <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <Clock size={12} /> {slot.start_time} - {slot.end_time}
                        </span>
                        {slot.can_start_now ? (
                          <span style={{ color: '#10b981', fontWeight: 600 }}>● Available Now</span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>{slot.time_status || 'Scheduled'}</span>
                        )}
                      </div>

                      {slot.is_substitute && (
                        <div style={{ marginTop: '0.5rem', fontSize: '0.72rem', color: '#f59e0b' }}>
                          ★ Authorized Substitute Assignment
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{
                padding: '1.25rem',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px dashed var(--border-color)',
                marginBottom: '1rem',
                textAlign: 'center'
              }}>
                <Calendar size={28} style={{ margin: '0 auto 0.5rem', opacity: 0.5, color: '#818cf8' }} />
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  No scheduled timetable entries found for you today.
                </p>
                {user?.role === 'admin' && (
                  <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', justifyContent: 'center', flexWrap: 'wrap' }}>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Subject (Admin Override)"
                      value={manualSubject}
                      onChange={(e) => setManualSubject(e.target.value)}
                      style={{ maxWidth: '200px' }}
                    />
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Section"
                      value={manualSection}
                      onChange={(e) => setManualSection(e.target.value)}
                      style={{ maxWidth: '120px' }}
                    />
                  </div>
                )}
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '1rem' }}>
              <button
                type="button"
                onClick={openVerifyModal}
                disabled={assignedSlots.length > 0 && !selectedSlotId}
                className="btn btn-primary"
                style={{ padding: '0.75rem 1.6rem', fontSize: '0.95rem' }}
              >
                <Camera size={18} />
                <span>Verify Face & Start Class Session</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Main Split Layout: Camera Viewport (Left) vs Live Attendance Roster (Right) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '1.5rem' }}>
        {/* Left: Video & Bounding Box Viewport */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header">
            <span className="card-title">
              <Video size={18} color="#6366f1" />
              Classroom Camera Feed
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {isProcessing && (
                <span style={{ fontSize: '0.75rem', color: '#818cf8', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <RefreshCw size={12} className="spin" /> Analyzing...
                </span>
              )}
              <span className="badge badge-primary">{lastDetections.length} Faces Detected</span>
            </div>
          </div>

          {/* Camera Viewport Container */}
          <div style={{
            position: 'relative',
            width: '100%',
            background: '#030712',
            borderRadius: 'var(--radius-md)',
            overflow: 'hidden',
            aspectRatio: '4/3',
            border: '2px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {cameraError ? (
              <div style={{ textAlign: 'center', color: '#f87171', padding: '2rem' }}>
                <VideoOff size={44} style={{ margin: '0 auto 1rem', opacity: 0.8 }} />
                <p>{cameraError}</p>
                <button onClick={startCamera} className="btn btn-secondary btn-sm" style={{ marginTop: '1rem' }}>
                  <RefreshCw size={14} /> Retry Camera
                </button>
              </div>
            ) : (
              <>
                <video
                  ref={videoRef}
                  playsInline
                  muted
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain'
                  }}
                />

                <canvas
                  ref={overlayCanvasRef}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    pointerEvents: 'none'
                  }}
                />

                {isDeadlineExpired && (
                  <div style={{
                    position: 'absolute',
                    top: 12,
                    left: 12,
                    right: 12,
                    background: 'rgba(239, 68, 68, 0.9)',
                    backdropFilter: 'blur(4px)',
                    color: 'white',
                    padding: '0.5rem 1rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.5rem'
                  }}>
                    <Lock size={15} /> Attendance Window Closed (15m Expired)
                  </div>
                )}
              </>
            )}
          </div>

          <canvas ref={hiddenCanvasRef} style={{ display: 'none' }} />

          {/* Model Status Warning */}
          {modelStatus && !modelStatus.is_trained && (
            <div style={{
              marginTop: '1rem',
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(245, 158, 11, 0.15)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              color: '#f59e0b',
              fontSize: '0.825rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem'
            }}>
              <AlertTriangle size={16} />
              <span>Face recognition model is not trained yet. Faces will be detected but marked Unknown.</span>
            </div>
          )}
        </div>

        {/* Right: Today's Live Attendance Register */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div className="card-header">
            <span className="card-title">
              <UserCheck size={18} color="#10b981" />
              Session Attendance Roster
            </span>
            <span className="badge badge-success">
              {presentStudents.length} Present
            </span>
          </div>

          {/* Real-time Attendees List */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            maxHeight: '440px',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-input)',
            padding: '0.5rem'
          }}>
            {presentStudents.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                <Users size={32} style={{ margin: '0 auto 0.75rem', opacity: 0.4 }} />
                <span>No attendance marks recorded yet in this session.</span>
                <span style={{ display: 'block', marginTop: '0.25rem', fontSize: '0.75rem' }}>
                  {isDeadlineExpired ? 'Session attendance window is locked.' : 'Student faces within 15-minute window are recorded.'}
                </span>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                {presentStudents.map((stud) => (
                  <div
                    key={stud.id || stud.student_id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.65rem 0.85rem',
                      background: 'rgba(255, 255, 255, 0.03)',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid rgba(255, 255, 255, 0.05)'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <CheckCircle2 size={16} color="#10b981" />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                          {stud.student_name || stud.name}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          <code>{stud.roll_number}</code> {stud.section && `• ${stud.section}`}
                        </div>
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <span className="badge badge-success" style={{ fontSize: '0.65rem' }}>
                        Present
                      </span>
                      {stud.time && (
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                          {stud.time}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Sparkles size={13} color="#6366f1" />
            <span>Server-enforced session rules: Timetable match, 15m deadline & duplicate prevention.</span>
          </div>
        </div>
      </div>

      {/* Teacher Face Verification Modal */}
      <Modal
        isOpen={isVerifyModalOpen}
        onClose={closeVerifyModal}
        title="Teacher Biometric Verification"
        maxWidth="580px"
      >
        <div>
          <div style={{ marginBottom: '1rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            To activate this attendance session, your face will be verified against your registered faculty biometric template.
          </div>

          {selectedSlot && (
            <div style={{
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(99, 102, 241, 0.08)',
              border: '1px solid rgba(99, 102, 241, 0.2)',
              marginBottom: '1rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div>
                <strong style={{ color: '#818cf8' }}>{selectedSlot.subject_name}</strong>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Period {selectedSlot.period_number} • Section {selectedSlot.section} ({selectedSlot.start_time} - {selectedSlot.end_time})
                </div>
              </div>
              <span className="badge badge-primary">Authorized Slot</span>
            </div>
          )}

          {verifyError && (
            <div style={{
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#f87171',
              fontSize: '0.85rem',
              marginBottom: '1rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem'
            }}>
              <AlertTriangle size={18} />
              <span>{verifyError}</span>
            </div>
          )}

          {/* Verification Viewport */}
          <div style={{
            position: 'relative',
            width: '100%',
            aspectRatio: '4/3',
            background: '#030712',
            borderRadius: 'var(--radius-md)',
            overflow: 'hidden',
            border: '2px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '1.25rem'
          }}>
            <video
              ref={verifyVideoRef}
              playsInline
              muted
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                transform: 'scaleX(-1)'
              }}
            />

            {/* Oval Guide */}
            <div style={{
              position: 'absolute',
              width: '45%',
              height: '65%',
              border: '2px dashed #818cf8',
              borderRadius: '50%',
              boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.35)',
              pointerEvents: 'none'
            }} />

            <div style={{
              position: 'absolute',
              bottom: '10px',
              background: 'rgba(15, 23, 42, 0.8)',
              padding: '0.35rem 0.85rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.75rem',
              color: 'var(--text-secondary)'
            }}>
              Position your face clearly within the oval
            </div>
          </div>

          <canvas ref={verifyCanvasRef} style={{ display: 'none' }} />

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="button"
              onClick={closeVerifyModal}
              className="btn btn-secondary"
              disabled={isVerifyingFace}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleVerifyAndStartSession}
              disabled={isVerifyingFace}
              className="btn btn-primary"
              style={{ padding: '0.75rem 1.5rem' }}
            >
              {isVerifyingFace ? (
                <>
                  <RefreshCw size={16} className="spin" />
                  <span>Verifying Biometrics...</span>
                </>
              ) : (
                <>
                  <ShieldCheck size={16} />
                  <span>Confirm Face & Start Class</span>
                </>
              )}
            </button>
          </div>
        </div>
      </Modal>

      {/* Close Session Confirmation Modal */}
      <Modal
        isOpen={isCloseModalOpen}
        onClose={() => setIsCloseModalOpen(false)}
        title="Close Attendance Session"
        maxWidth="500px"
      >
        <div>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            Are you sure you want to end this attendance session? All {presentStudents.length} recorded attendances will be locked.
          </p>

          <div style={{ marginBottom: '1.25rem' }}>
            <label className="form-label">Closure Reason / Notes</label>
            <input
              type="text"
              className="form-input"
              value={closeReason}
              onChange={(e) => setCloseReason(e.target.value)}
              placeholder="e.g. Lecture completed on schedule"
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="button"
              onClick={() => setIsCloseModalOpen(false)}
              className="btn btn-secondary"
              disabled={isSubmittingClose}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirmClose}
              disabled={isSubmittingClose}
              className="btn btn-danger"
            >
              {isSubmittingClose ? 'Closing...' : 'Confirm Closure'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Flag Review Modal */}
      <Modal
        isOpen={isReviewModalOpen}
        onClose={() => setIsReviewModalOpen(false)}
        title="Flag Session for Audit Review"
        maxWidth="500px"
      >
        <div>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            Flagging this session marks it as <code>review-required</code> for department heads or admins to inspect attendance discrepancies.
          </p>

          <div style={{ marginBottom: '1.25rem' }}>
            <label className="form-label">Reason for Review</label>
            <textarea
              className="form-input"
              rows={3}
              value={reviewReason}
              onChange={(e) => setReviewReason(e.target.value)}
              placeholder="Describe the discrepancy, camera glitch, or proxy suspicion..."
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="button"
              onClick={() => setIsReviewModalOpen(false)}
              className="btn btn-secondary"
              disabled={isSubmittingClose}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirmReview}
              disabled={isSubmittingClose}
              className="btn btn-primary"
              style={{ background: '#f59e0b', borderColor: '#f59e0b' }}
            >
              {isSubmittingClose ? 'Flagging...' : 'Submit Review Flag'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
export default LiveAttendance;
