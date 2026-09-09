import request from './request'

export const getAuditLogs = (params) => request.get('/api/audit', { params })
export const getOperationStats = (days = 7) => request.get('/api/audit/stats/operations', { params: { days } })
export const getDailyStats = (days = 7) => request.get('/api/audit/stats/daily', { params: { days } })