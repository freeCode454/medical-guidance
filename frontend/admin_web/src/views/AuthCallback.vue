<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { setRefreshToken, setToken } from '@/api/client'

const router = useRouter()

onMounted(() => {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const access = params.get('access_token')
  const refresh = params.get('refresh_token')
  const user = params.get('user')
  const role = params.get('role')
  if (!access || (role !== 'ORG_ADMIN' && role !== 'KB_ADMIN')) {
    router.replace('/login')
    return
  }
  setToken(access)
  if (refresh) setRefreshToken(refresh)
  if (user) localStorage.setItem('admin_user', user)
  window.history.replaceState(null, '', '/auth-callback')
  router.replace('/')
})
</script>

<template>
  <main class="callback">正在进入管理后台…</main>
</template>

<style scoped>
.callback {
  min-height: 100vh;
  display: grid;
  place-items: center;
  color: var(--c-muted);
  font-size: 13px;
}
</style>
