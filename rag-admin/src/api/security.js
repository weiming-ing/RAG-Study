import request from './request'

export const getSensitiveWords = (params) => request.get('/api/security/sensitive-words', { params })
export const saveSensitiveWord = (data) => request.post('/api/security/sensitive-words', data)
export const deleteSensitiveWord = (id) => request.delete(`/api/security/sensitive-words/${id}`)
export const batchImportWords = (data) => request.post('/api/security/sensitive-words/batch', data)
export const checkSensitive = (data) => request.post('/api/security/sensitive-words/check', data)

export const getRateLimits = (params) => request.get('/api/security/rate-limits', { params })
export const saveRateLimit = (data) => request.post('/api/security/rate-limits', data)
export const deleteRateLimit = (id) => request.delete(`/api/security/rate-limits/${id}`)

export const getAccessControls = (params) => request.get('/api/security/access-controls', { params })
export const saveAccessControl = (data) => request.post('/api/security/access-controls', data)
export const deleteAccessControl = (id) => request.delete(`/api/security/access-controls/${id}`)