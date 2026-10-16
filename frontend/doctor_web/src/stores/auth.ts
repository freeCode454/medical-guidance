import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/doctor'
import { setToken, getToken } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<api.DoctorInfo | null>(null)
  const token = ref<string | null>(getToken())

  async function login(account: string, password: string) {
    const d = await api.login(account, password)
    setToken(d.access_token)
    token.value = d.access_token
    user.value = d.user
  }

  function logout() {
    setToken(null)
    token.value = null
    user.value = null
  }

  return { user, token, login, logout }
})
