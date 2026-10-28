import api from './api';

export const reportService = {
  async getStudentReports(params = {}) {
    const response = await api.get('/reports/students', { params });
    return response.data;
  },

  async getSubjectReports() {
    const response = await api.get('/reports/subjects');
    return response.data;
  },

  async getDailyReports(limit = 30) {
    const response = await api.get('/reports/daily', { params: { limit } });
    return response.data;
  },

  async getMonthlyReports() {
    const response = await api.get('/reports/monthly');
    return response.data;
  },

  async downloadExport(format = 'excel', reportType = 'detailed', filterParams = {}) {
    const endpoint = `/reports/export/${format === 'csv' ? 'csv' : 'excel'}`;
    const response = await api.get(endpoint, {
      params: {
        report_type: reportType,
        ...filterParams,
      },
      responseType: 'blob',
    });

    // Create a download link
    const blob = new Blob([response.data], {
      type: format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const extension = format === 'csv' ? 'csv' : 'xlsx';
    link.setAttribute('download', `attendance_report_${reportType}_${new Date().toISOString().slice(0,10)}.${extension}`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
    window.URL.revokeObjectURL(url);
  }
};
