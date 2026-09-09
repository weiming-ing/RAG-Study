import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '',
  timeout: 30000
})

request.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  response => {
    const res = response.data
    if (res.success === false) {
      ElMessage.error(res.error || res.message || '请求失败')
      return Promise.reject(new Error(res.error || res.message || '请求失败'))
    }
    return res
  },
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      window.location.href = '/login'
      return Promise.reject(error)
    }
    if (error.response?.status === 404) {
      ElMessage.error('请求的资源不存在 (404)')
      return Promise.reject(error)
    }
    if (error.code === 'ERR_NETWORK') {
      ElMessage.error('无法连接到后端服务，请确认服务已启动')
      return Promise.reject(error)
    }
    ElMessage.error(error.message || '网络错误')
    return Promise.reject(error)
  }
)

export default request