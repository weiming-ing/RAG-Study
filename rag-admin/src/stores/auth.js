import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, getUserInfo as getUserInfoApi } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))

  // 旧版本登录的会话里 userInfo 没有 roles 字段，静默刷新一次，
  // 让路由守卫的角色判断拿到数据（token 本身的角色由后端回退查库兼容）
  if (token.value && userInfo.value && userInfo.value.roles === undefined) {
    getUserInfoApi()
      .then(res => {
        userInfo.value = res.data
        localStorage.setItem('userInfo', JSON.stringify(res.data))
      })
      .catch(() => {})
  }

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