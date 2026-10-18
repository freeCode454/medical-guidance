import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/doctor'
import { clearSession, getToken, setRefreshToken, setToken } from '@/api/client'

function storedUser(): api.DoctorInfo | null {
  try {
    const raw = localStorage.getItem('doctor_user')
    return raw ? (JSON.parse(raw) as api.DoctorInfo) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<api.DoctorInfo | null>(storedUser())
  const token = ref<string | null>(getToken())

  async function login(account: string, password: string) {
    const d = await api.login(account, password)
    setToken(d.access_token)
    setRefreshToken(d.refresh_token)
    token.value = d.access_token
    user.value = d.user
    localStorage.setItem('doctor_user', JSON.stringify(d.user))
  }

  function logout() {
    clearSession()
    token.value = null
    user.value = null
  }

  return { user, token, login, logout }
})
