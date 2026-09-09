import request from './request'

export const getDashboard = () => request.get('/api/dashboard/overview')
export const getApiStats = (days = 7) => request.get('/api/dashboard/api-stats', { params: { days } })
export const getTokenStats = (days = 7) => request.get('/api/dashboard/token-stats', { params: { days } })
export const getHotDocs = (days = 7, limit = 10) => request.get('/api/dashboard/hot-docs', { params: { days, limit } })
export const getKbHotRank = (days = 7) => request.get('/api/dashboard/kb-hot-rank', { params: { days } })
export const getTaskStats = (days = 7) => request.get('/api/dashboard/task-stats', { params: { days } })
export const getAlerts = () => request.get('/api/dashboard/alerts')
export const resolveAlert = (id) => request.put(`/api/dashboard/alerts/${id}/resolve`)