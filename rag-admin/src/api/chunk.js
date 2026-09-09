import request from './request'

export const getChunks = (params) => request.get('/api/chunks', { params })
export const updateChunk = (id, data) => request.put(`/api/chunks/${id}`, data)
export const splitChunk = (id, data) => request.post(`/api/chunks/${id}/split`, data)
export const mergeChunks = (data) => request.post('/api/chunks/merge', data)
export const rebuildKbVectors = (kbId) => request.post(`/api/chunks/rebuild/${kbId}`)