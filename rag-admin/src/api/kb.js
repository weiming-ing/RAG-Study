import request from './request'

export const getKbs = (params) => request.get('/api/knowledge-bases', { params })
export const getKbById = (id) => request.get(`/api/knowledge-bases/${id}`)
export const createKb = (data) => request.post('/api/knowledge-bases', data)
export const updateKb = (id, data) => request.put(`/api/knowledge-bases/${id}`, data)
export const deleteKb = (id) => request.delete(`/api/knowledge-bases/${id}`)
export const getKbConfig = (id) => request.get(`/api/knowledge-bases/${id}/config`)
export const updateKbConfig = (id, data) => request.put(`/api/knowledge-bases/${id}/config`, data)
export const getAuthorizedUsers = (kbId) => request.get(`/api/knowledge-bases/${kbId}/users`)
export const grantAccess = (kbId, data) => request.post(`/api/knowledge-bases/${kbId}/users`, data)
export const revokeAccess = (kbId, userId) => request.delete(`/api/knowledge-bases/${kbId}/users/${userId}`)
export const getAvailableUsers = () => request.get('/api/admin/users/list')