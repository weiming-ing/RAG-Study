import request from './request'

export const getMenus = () => request.get('/api/admin/menus/tree')
export const createMenu = (data) => request.post('/api/admin/menus', data)
export const updateMenu = (id, data) => request.put(`/api/admin/menus/${id}`, data)
export const deleteMenu = (id) => request.delete(`/api/admin/menus/${id}`)