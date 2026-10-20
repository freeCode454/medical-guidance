<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthForm from '@/components/AuthForm.vue'
import { useSessionStore } from '@/stores/session'
import type { UnifiedAuth } from '@/api/patient'

const route = useRoute()
const router = useRouter()
const store = useSessionStore()
const loading = ref(false)
const error = ref('')

const DOCTOR_URL = import.meta.env.VITE_DOCTOR_URL || 'http://127.0.0.1:5174'
const ADMIN_URL = import.meta.env.VITE_ADMIN_URL || 'http://127.0.0.1:5175'

onMounted(() => {
  store.hydrateAuth()
  if (store.isAuthenticated) router.replace('/')
  else if (route.query.expired) error.value = '登录已过期，请重新登录'
})

function handoff(data: UnifiedAuth) {
  const target = data.role === 'DOCTOR' ? DOCTOR_URL : ADMIN_URL
  const params = new URLSearchParams({
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    role: data.role,
    user: JSON.stringify(data.user || {}),
  })
  // 令牌放 fragment，不进入服务端访问日志
  window.location.assign(`${target}/auth-callback#${params.toString()}`)
}

async function onSubmit(payload: {
  mode: 'login' | 'register'
  account: string
  password: string
}) {
  loading.value = true
  error.value = ''
  try {
    if (payload.mode === 'register') {
      await store.register(payload.account, payload.password)
      const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
      router.replace(redirect)
      return
    }
    const data = await store.loginUnified(payload.account, payload.password)
    if (data.role === 'PATIENT') {
      const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
      router.replace(redirect)
      return
    }
    handoff(data)
  } catch (e) {
    error.value = (e as Error).message || '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <AuthForm
        allow-register
        :loading="loading"
        :error="error"
        @submit="onSubmit"
      />
      <p class="portal-links">患者、医生、管理员共用此登录/注册页</p>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  padding: 24px 18px calc(24px + env(safe-area-inset-bottom));
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-brand {
  padding: 8px 4px;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  background: var(--c-primary);
  color: #f3dcc8;
  font-family: var(--font-display);
  font-size: 20px;
  box-shadow: var(--shadow-accent);
}

.brand-row b {
  display: block;
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--c-primary);
}

.brand-row em {
  display: block;
  margin-top: 1px;
  font-style: normal;
  font-size: 10.5px;
  letter-spacing: 0.16em;
  color: var(--c-faint);
}

.eyebrow {
  margin-top: 30px;
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--c-accent-text);
}

h1 {
  margin-top: 9px;
  font-family: var(--font-display);
  font-size: clamp(34px, 7vw, 48px);
  line-height: 1.28;
  color: var(--c-primary);
  letter-spacing: -0.02em;
}

.lede {
  margin-top: 14px;
  max-width: 430px;
  font-size: 13px;
  line-height: 1.85;
  color: var(--c-muted);
}

.points {
  margin-top: 26px;
  display: grid;
  gap: 12px;
  padding: 0;
  list-style: none;
}

.points li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12.5px;
  color: var(--c-ink);
}

.points span {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid var(--c-primary-line);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-family: var(--font-mono);
  font-size: 9px;
}

.foot {
  margin-top: 26px;
  font-size: 10.5px;
  color: var(--c-faint);
}

.login-panel {
  width: 100%;
  max-width: 480px;
  padding: 26px 20px;
  border: 1px solid var(--c-line);
  border-radius: 22px;
  background: var(--c-surface);
  box-shadow: var(--shadow-sm);
}

.portal-links {
  margin-top: 22px;
  text-align: center;
  color: var(--c-faint);
  font-size: 10.5px;
}

@media (min-width: 860px) {
  .login-page {
    padding: 40px 32px;
  }

  .login-panel {
    padding: 32px 30px;
  }
}
</style>
