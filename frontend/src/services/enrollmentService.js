import api from './api';

export const enrollmentService = {
  async getEnrollments(params = {}) {
    const res = await api.get('/enrollments', { params });
    return res.data;
  },

  async createEnrollment(data) {
    const res = await api.post('/enrollments', data);
    return res.data;
  },

  async registerFaceCamera(payload) {
    const res = await api.post('/enrollments/register', payload);
    return res.data;
  },

  async renewEnrollment(id, data) {
    const res = await api.post(`/enrollments/${id}/renew`, data);
    return res.data;
  },

  async revokeEnrollment(id) {
    const res = await api.post(`/enrollments/${id}/revoke`);
    return res.data;
  },

  async updateEnrollment(id, data) {
    const res = await api.put(`/enrollments/${id}`, data);
    return res.data;
  },

  async deleteEnrollment(id) {
    const res = await api.delete(`/enrollments/${id}`);
    return res.data;
  }
};
