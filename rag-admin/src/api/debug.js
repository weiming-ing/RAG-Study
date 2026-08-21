import request from './request'

export const debugSearch = (data) => request.post('/api/debug/search', data)
export const getTestCases = (params) => request.get('/api/debug/test-cases', { params })
export const saveTestCase = (data) => request.post('/api/debug/test-cases', data)
export const deleteTestCase = (id) => request.delete(`/api/debug/test-cases/${id}`)
export const runAllTestCases = (data) => request.post('/api/debug/test-cases/run-all', data)