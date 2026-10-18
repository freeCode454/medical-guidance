import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/admin'
import { clearSession, getToken, setRefreshToken, setToken } from '@/api/client'

export interface AdminUser {
  user_id: string
  account: string
  real_name: string | null
  role: string
  tenant_name?: string
}

function storedUser(): AdminUser | null {
  try {
    const raw = localStorage.getItem('admin_user')
    return raw ? (JSON.parse(raw) as AdminUser) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AdminUser | null>(storedUser())
  const token = ref<string | null>(getToken())

  async function login(account: string, password: string) {
    const d = await api.login(account, password)
    setToken(d.access_token)
    setRefreshToken(d.refresh_token)
    token.value = d.access_token
    user.value = d.user as AdminUser
    localStorage.setItem('admin_user', JSON.stringify(d.user))
  }

  function logout() {
    clearSession()
    token.value = null
    user.value = null
  }

  return { user, token, login, logout }
})
