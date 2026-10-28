import React, { useRef, useState, useEffect } from 'react';
import { Camera, RefreshCw, CheckCircle2, AlertCircle, Trash2, VideoOff } from 'lucide-react';

export const WebcamCapture = ({ onCaptureComplete, maxImages = 5, requiredImages = 3 }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  const [streamActive, setStreamActive] = useState(false);
  const [permissionError, setPermissionError] = useState(null);
  const [capturedImages, setCapturedImages] = useState([]);
  const [isCapturing, setIsCapturing] = useState(false);

  // Initialize camera stream
  const startCamera = async () => {
    try {
      setPermissionError(null);
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
      setStreamActive(true);
    } catch (err) {
      console.error('Webcam access error:', err);
      setPermissionError('Unable to access webcam. Please check browser camera permissions.');
      setStreamActive(false);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setStreamActive(false);
  };

  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, []);

  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current || capturedImages.length >= maxImages) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const base64Data = canvas.toDataURL('image/jpeg', 0.92);
    const updated = [...capturedImages, base64Data];
    setCapturedImages(updated);

    if (onCaptureComplete) {
      onCaptureComplete(updated);
    }
  };

  const removePhoto = (index) => {
    const updated = capturedImages.filter((_, i) => i !== index);
    setCapturedImages(updated);
    if (onCaptureComplete) {
      onCaptureComplete(updated);
    }
  };

  const clearAllPhotos = () => {
    setCapturedImages([]);
    if (onCaptureComplete) {
      onCaptureComplete([]);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Video Viewport with Guide */}
      <div style={{
        position: 'relative',
        width: '100%',
        maxWidth: '520px',
        margin: '0 auto',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        background: '#030712',
        border: '2px solid var(--border-color)',
        aspectRatio: '4/3',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        {permissionError ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#f87171' }}>
            <VideoOff size={44} style={{ margin: '0 auto 1rem', opacity: 0.8 }} />
            <p style={{ fontWeight: 600 }}>{permissionError}</p>
            <button
              onClick={startCamera}
              className="btn btn-secondary btn-sm"
              style={{ marginTop: '1rem' }}
            >
              <RefreshCw size={14} /> Try Again
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
                objectFit: 'cover',
                transform: 'scaleX(-1)' // Mirror view for natural user perception
              }}
            />

            {/* Target Face Frame Overlay */}
            <div style={{
              position: 'absolute',
              width: '45%',
              height: '65%',
              border: '2px dashed rgba(99, 102, 241, 0.6)',
              borderRadius: '50%',
              boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.3)',
              pointerEvents: 'none'
            }} />

            <div style={{
              position: 'absolute',
              bottom: '12px',
              left: '12px',
              right: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: 'rgba(15, 23, 42, 0.75)',
              backdropFilter: 'blur(8px)',
              padding: '0.4rem 0.85rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.75rem',
              color: 'var(--text-secondary)'
            }}>
              <span>Align face inside the oval</span>
              <span style={{ color: capturedImages.length >= requiredImages ? '#10b981' : '#f59e0b', fontWeight: 600 }}>
                {capturedImages.length}/{maxImages} Captured
              </span>
            </div>
          </>
        )}
      </div>

      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {/* Capture Actions */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
        <button
          type="button"
          onClick={capturePhoto}
          disabled={!streamActive || capturedImages.length >= maxImages}
          className="btn btn-primary"
          style={{ padding: '0.75rem 1.75rem', fontSize: '0.95rem' }}
        >
          <Camera size={20} />
          <span>Capture Face ({capturedImages.length}/{maxImages})</span>
        </button>

        {capturedImages.length > 0 && (
          <button
            type="button"
            onClick={clearAllPhotos}
            className="btn btn-secondary btn-sm"
          >
            <Trash2 size={16} /> Clear All
          </button>
        )}
      </div>

      {/* Captured Thumbnails Strip */}
      {capturedImages.length > 0 && (
        <div style={{ marginTop: '0.5rem' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '0.5rem' }}>
            Captured Samples (Recommended: 3 to 5 distinct angles / expressions):
          </span>
          <div style={{ display: 'flex', gap: '0.75rem', overflowX: 'auto', paddingBottom: '0.5rem' }}>
            {capturedImages.map((imgSrc, idx) => (
              <div
                key={idx}
                style={{
                  position: 'relative',
                  width: '75px',
                  height: '75px',
                  borderRadius: 'var(--radius-md)',
                  overflow: 'hidden',
                  border: '2px solid #6366f1',
                  flexShrink: 0
                }}
              >
                <img
                  src={imgSrc}
                  alt={`Sample ${idx + 1}`}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
                <button
                  type="button"
                  onClick={() => removePhoto(idx)}
                  style={{
                    position: 'absolute',
                    top: 2,
                    right: 2,
                    background: 'rgba(239, 68, 68, 0.85)',
                    color: 'white',
                    borderRadius: '50%',
                    width: '18px',
                    height: '18px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '10px'
                  }}
                  title="Remove this photo"
                >
                  ✕
                </button>
                <div style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  right: 0,
                  background: 'rgba(0, 0, 0, 0.7)',
                  fontSize: '9px',
                  textAlign: 'center',
                  color: 'white',
                  fontWeight: 600
                }}>
                  #{idx + 1}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
