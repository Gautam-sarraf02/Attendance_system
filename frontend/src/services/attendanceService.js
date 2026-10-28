import api from './api';

export const attendanceService = {
  // Sessions
  async startSession(subject, section) {
    const response = await api.post('/sessions', { subject, section });
    return response.data;
  },

  async startAuthorizedSession(payload) {
    const response = await api.post('/sessions/authorized-start', payload);
    return response.data;
  },

  async getTeacherAssignedSlots(date = null) {
    const params = date ? { target_date: date } : {};
    const response = await api.get('/sessions/teacher/assigned-slots', { params });
    return response.data;
  },

  async getActiveSession() {
    const response = await api.get('/sessions/active');
    return response.data;
  },

  async getSessionStatus(sessionId) {
    const response = await api.get(`/sessions/${sessionId}/status`);
    return response.data;
  },

  async stopSession(sessionId) {
    const response = await api.post(`/sessions/${sessionId}/stop`);
    return response.data;
  },

  async closeSession(sessionId, payload = {}) {
    const response = await api.post(`/sessions/${sessionId}/close`, payload);
    return response.data;
  },

  async flagSessionReview(sessionId, payload = {}) {
    const response = await api.post(`/sessions/${sessionId}/flag-review`, payload);
    return response.data;
  },

  async getSessions(params = {}) {
    const response = await api.get('/sessions', { params });
    return response.data;
  },

  // Live Recognition
  async recognizeFrame(imageBase64, sessionId = null, autoMark = true) {
    const response = await api.post('/attendance/recognize', {
      image_base64: imageBase64,
      session_id: sessionId,
      auto_mark: autoMark
    });
    return response.data;
  },

  // History & Manual
  async getHistory(params = {}) {
    const response = await api.get('/attendance/history', { params });
    return response.data;
  },

  async markManual(data) {
    const response = await api.post('/attendance/manual', data);
    return response.data;
  },

  async deleteRecord(attendanceId) {
    const response = await api.delete(`/attendance/${attendanceId}`);
    return response.data;
  },

  // Dashboard Stats
  async getDashboardStats() {
    const response = await api.get('/dashboard/stats');
    return response.data;
  },

  // Student Dashboard & Analytics
  async getStudentDashboard(studentId = null) {
    const params = studentId ? { student_id: studentId } : {};
    const response = await api.get('/dashboard/student', { params });
    return response.data;
  },

  // Attendance Corrections
  async getCorrections(params = {}) {
    const response = await api.get('/attendance/corrections', { params });
    return response.data;
  },

  async submitCorrection(data) {
    const response = await api.post('/attendance/corrections', data);
    return response.data;
  },

  async decideCorrection(correctionId, data) {
    const response = await api.put(`/attendance/corrections/${correctionId}/review`, data);
    return response.data;
  }
};


