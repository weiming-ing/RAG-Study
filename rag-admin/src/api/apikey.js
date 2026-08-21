import request from './request'

export const getApiKeys = (params) => request.get('/api/api-keys', { params })
export const getApiKeyById = (id) => request.get(`/api/api-keys/${id}`)
export const generateApiKey = (data) => request.post('/api/api-keys', data)
export const updateApiKey = (id, data) => request.put(`/api/api-keys/${id}`, data)
export const deleteApiKey = (id) => request.delete(`/api/api-keys/${id}`)