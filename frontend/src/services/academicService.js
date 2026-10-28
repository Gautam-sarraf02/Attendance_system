import api from './api';

export const academicService = {
  // Academic Years
  async getAcademicYears() {
    const res = await api.get('/timetable/academic-years');
    return res.data;
  },

  async createAcademicYear(data) {
    const res = await api.post('/timetable/academic-years', data);
    return res.data;
  },

  async updateAcademicYear(id, data) {
    const res = await api.put(`/timetable/academic-years/${id}`, data);
    return res.data;
  },

  async deleteAcademicYear(id) {
    const res = await api.delete(`/timetable/academic-years/${id}`);
    return res.data;
  },

  // Semesters
  async getSemesters(academicYearId = null) {
    const params = academicYearId ? { academic_year_id: academicYearId } : {};
    const res = await api.get('/timetable/semesters', { params });
    return res.data;
  },

  async createSemester(data) {
    const res = await api.post('/timetable/semesters', data);
    return res.data;
  },

  async updateSemester(id, data) {
    const res = await api.put(`/timetable/semesters/${id}`, data);
    return res.data;
  },

  async deleteSemester(id) {
    const res = await api.delete(`/timetable/semesters/${id}`);
    return res.data;
  },

  // Subjects
  async getSubjects(semesterId = null, section = null) {
    const params = {};
    if (semesterId) params.semester_id = semesterId;
    if (section) params.section = section;
    const res = await api.get('/timetable/subjects', { params });
    return res.data;
  },

  async createSubject(data) {
    const res = await api.post('/timetable/subjects', data);
    return res.data;
  },

  async updateSubject(id, data) {
    const res = await api.put(`/timetable/subjects/${id}`, data);
    return res.data;
  },

  async deleteSubject(id) {
    const res = await api.delete(`/timetable/subjects/${id}`);
    return res.data;
  },

  // Timetable Entries
  async getTimetableEntries(params = {}) {
    const res = await api.get('/timetable/entries', { params });
    return res.data;
  },

  async createTimetableEntry(data) {
    const res = await api.post('/timetable/entries', data);
    return res.data;
  },

  async updateTimetableEntry(id, data) {
    const res = await api.put(`/timetable/entries/${id}`, data);
    return res.data;
  },

  async deleteTimetableEntry(id) {
    const res = await api.delete(`/timetable/entries/${id}`);
    return res.data;
  },

  // Timetable Import & Validation
  async previewTimetableImport(formDataOrPayload) {
    let res;
    if (formDataOrPayload instanceof FormData) {
      res = await api.post('/timetable/import/preview', formDataOrPayload, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    } else {
      res = await api.post('/timetable/import/preview', formDataOrPayload);
    }
    return res.data;
  },

  async commitTimetableImport(data) {
    const res = await api.post('/timetable/import/commit', data);
    return res.data;
  },

  async downloadTimetableTemplate() {
    const res = await api.get('/timetable/template/csv', { responseType: 'blob' });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'timetable_template.csv');
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  // Scheduled Class Lookup
  async lookupScheduledClass(params = {}) {
    const res = await api.get('/timetable/lookup', { params });
    return res.data;
  },

  // Holidays
  async getHolidays(academicYearId = null) {
    const params = academicYearId ? { academic_year_id: academicYearId } : {};
    const res = await api.get('/timetable/holidays', { params });
    return res.data;
  },

  async createHoliday(data) {
    const res = await api.post('/timetable/holidays', data);
    return res.data;
  },

  async deleteHoliday(id) {
    const res = await api.delete(`/timetable/holidays/${id}`);
    return res.data;
  }
};
