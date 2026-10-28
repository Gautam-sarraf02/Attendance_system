import api from './api';

export const studentService = {
  async getStudents(params = {}) {
    const response = await api.get('/students', { params });
    return response.data;
  },

  async getStudent(id) {
    const response = await api.get(`/students/${id}`);
    return response.data;
  },

  async createStudent(data) {
    const response = await api.post('/students', data);
    return response.data;
  },

  async updateStudent(id, data) {
    const response = await api.put(`/students/${id}`, data);
    return response.data;
  },

  async deleteStudent(id) {
    const response = await api.delete(`/students/${id}`);
    return response.data;
  },

  async uploadFaceSamplesBase64(studentId, imagesBase64) {
    const response = await api.post(`/students/${studentId}/samples/base64`, {
      images: imagesBase64
    });
    return response.data;
  },

  async uploadFaceSamplesFiles(studentId, formData) {
    const response = await api.post(`/students/${studentId}/samples/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      }
    });
    return response.data;
  },

  async clearStudentSamples(studentId) {
    const response = await api.delete(`/students/${studentId}/samples`);
    return response.data;
  }
};
