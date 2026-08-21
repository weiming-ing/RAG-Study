import request from './request'

export const getKbs = (params) => request.get('/api/knowledge-bases', { params })
export const getKbById = (id) => request.get(`/api/knowledge-bases/${id}`)
export const createKb = (data) => request.post('/api/knowledge-bases', data)
export const updateKb = (id, data) => request.put(`/api/knowledge-bases/${id}`, data)
export const deleteKb = (id) => request.delete(`/api/knowledge-bases/${id}`)
export const getKbConfig = (id) => request.get(`/api/knowledge-bases/${id}/config`)
export const updateKbConfig = (id, data) => request.put(`/api/knowledge-bases/${id}/config`, data)