import request from './request'

export const getDocs = (kbId, params) => request.get(`/api/knowledge/${kbId}/documents`, { params })
export const getDocsAll = (params) => request.get('/api/knowledge/documents', { params })
export const getDocById = (kbId, id) => request.get(`/api/knowledge/${kbId}/documents/${id}`)
export const uploadDoc = (kbId, formData) => request.post(`/api/knowledge/${kbId}/documents/upload`, formData, { headers: { 'Content-Type': 'multipart/form-data' } })
export const deleteDoc = (kbId, id) => request.delete(`/api/knowledge/${kbId}/documents/${id}`)
export const reparseDoc = (kbId, id) => request.post(`/api/knowledge/${kbId}/documents/${id}/reparse`)
export const getDocContent = (kbId, id) => request.get(`/api/knowledge/${kbId}/documents/${id}/content`)