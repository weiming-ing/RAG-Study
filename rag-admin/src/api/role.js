import request from './request'

export const getRoles = (params) => request.get('/api/admin/roles', { params })
export const createRole = (data) => request.post('/api/admin/roles', data)
export const updateRole = (id, data) => request.put(`/api/admin/roles/${id}`, data)
export const deleteRole = (id) => request.delete(`/api/admin/roles/${id}`)
export const getRoleMenus = (id) => request.get(`/api/admin/roles/${id}/menus`)
export const updateRoleMenus = (id, data) => request.put(`/api/admin/roles/${id}/menus`, data)