import request from './request'

export function getConfigs(params) {
  return request.get('/api/system/configs', { params })
}

export function getConfigsGrouped() {
  return request.get('/api/system/configs/grouped')
}

export function getConfigByGroup(group) {
  return request.get(`/api/system/configs/group/${group}`)
}

export function getConfigById(id) {
  return request.get(`/api/system/configs/${id}`)
}

export function saveConfig(data) {
  return request.post('/api/system/configs', data)
}

export function updateConfig(id, data) {
  return request.put(`/api/system/configs/${id}`, data)
}

export function batchUpdateConfigs(data) {
  return request.put('/api/system/configs/batch', data)
}

export function deleteConfig(id) {
  return request.delete(`/api/system/configs/${id}`)
}

export function getConfigStats() {
  return request.get('/api/system/configs/stats')
}

export function getLogs(params) {
  return request.get('/api/system/logs', { params })
}

export function getLogStats() {
  return request.get('/api/system/logs/stats')
}

export function getLogById(id) {
  return request.get(`/api/system/logs/${id}`)
}

export function cleanExpiredLogs(days = 90) {
  return request.delete(`/api/system/logs/clean`, { params: { days } })
}