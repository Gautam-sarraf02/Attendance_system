import api from './api';

export const modelService = {
  async getStatus() {
    const response = await api.get('/model/status');
    return response.data;
  },

  async trainModel() {
    const response = await api.post('/model/train');
    return response.data;
  },

  async updateThreshold(threshold) {
    const response = await api.put('/model/threshold', { threshold });
    return response.data;
  }
};
