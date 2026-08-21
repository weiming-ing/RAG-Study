import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, getUserInfo as getUserInfoApi } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))

  const login = async (username, password) => {
    const res = await loginApi({ username, password })
    const t = res.data?.access_token || res.data?.token || res.data?.accessToken
    token.value = t
    localStorage.setItem('token', t)
    try {
      const infoRes = await getUserInfoApi()
      userInfo.value = infoRes.data
      localStorage.setItem('userInfo', JSON.stringify(infoRes.data))
    } catch (e) {
      console.warn('获取用户信息失败', e)
    }
    return res
  }

  const logout = () => {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }

  return { token, userInfo, login, logout }
})