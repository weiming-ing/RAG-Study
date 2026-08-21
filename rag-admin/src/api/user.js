import request from './request'

export const getUsers = (params) => request.get('/api/admin/users', { params })
export const createUser = (data) => request.post('/api/admin/users', data)
export const updateUser = (id, data) => request.put(`/api/admin/users/${id}`, data)
export const deleteUser = (id) => request.delete(`/api/admin/users/${id}`)
export const resetPassword = (id, data) => request.put(`/api/admin/users/${id}/reset-password`, data)