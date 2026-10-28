import api from './api';

export const authService = {
  async login(username, password, role = null) {
    const payload = { username, password };
    if (role) payload.role = role;
    const response = await api.post('/auth/login', payload);
    if (response.data.access_token) {
      localStorage.setItem('attendance_token', response.data.access_token);
      localStorage.setItem('attendance_user', JSON.stringify(response.data.user));
    }
    return response.data;
  },

  async getCurrentUser() {
    const response = await api.get('/auth/me');
    return response.data;
  },

  logout() {
    localStorage.removeItem('attendance_token');
    localStorage.removeItem('attendance_user');
  },

  getStoredUser() {
    const userStr = localStorage.getItem('attendance_user');
    try {
      return userStr ? JSON.parse(userStr) : null;
    } catch {
      return null;
    }
  },

  isAuthenticated() {
    return !!localStorage.getItem('attendance_token');
  },

  async getUsers(params = {}) {
    const res = await api.get('/auth/users', { params });
    return res.data;
  },

  async createUser(data) {
    const res = await api.post('/auth/users', data);
    return res.data;
  },

  async updateUser(id, data) {
    const res = await api.put(`/auth/users/${id}`, data);
    return res.data;
  },

  async deleteUser(id) {
    const res = await api.delete(`/auth/users/${id}`);
    return res.data;
  },

  async getFaculty() {
    const res = await api.get('/auth/faculty');
    return res.data;
  },

  async createFaculty(data) {
    const res = await api.post('/auth/faculty', data);
    return res.data;
  },

  async updateFaculty(id, data) {
    const res = await api.put(`/auth/faculty/${id}`, data);
    return res.data;
  }
};

