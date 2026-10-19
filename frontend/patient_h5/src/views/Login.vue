<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthForm from '@/components/AuthForm.vue'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const router = useRouter()
const store = useSessionStore()
const loading = ref(false)
const error = ref('')

onMounted(() => {
  store.hydrateAuth()
  if (store.isAuthenticated) {
    router.replace('/')
  } else if (route.query.expired) {
    error.value = '登录已过期，请重新登录'
  }
})

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
    } else {
      await store.login(payload.account, payload.password)
    }
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (e) {
    error.value = (e as Error).message || '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-brand">
      <div class="brand-row">
        <span class="brand-mark" aria-hidden="true">诊</span>
        <div>
          <b>智能导诊</b>
          <em>患者端</em>
        </div>
      </div>
      <p class="eyebrow">预问诊 · 分诊建议 · 预约挂号</p>
      <h1>把症状说清楚，<br />再决定挂哪个科</h1>
      <p class="lede">
        登录后可查看自己的问诊记录、既往病历与预约；医生端和管理端使用同一套登录入口。
      </p>
      <ul class="points">
        <li><span>01</span>多轮追问，不是一次性问答</li>
        <li><span>02</span>授权后结合既往病历</li>
        <li><span>03</span>分诊后直接看医生与号源</li>
      </ul>
      <p class="foot">本系统仅提供分诊建议，不构成医学诊断。</p>
    </section>

    <section class="login-panel">
      <AuthForm
        portal="PATIENT"
        allow-register
        :loading="loading"
        :error="error"
        @submit="onSubmit"
      />
      <p class="portal-links">
        医生入口：<a href="http://127.0.0.1:5174/login">医生工作台</a>
        <span>·</span>
        管理员入口：<a href="http://127.0.0.1:5175/login">管理后台</a>
      </p>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  max-width: 1060px;
  margin: 0 auto;
  padding: 28px 18px calc(28px + env(safe-area-inset-bottom));
  box-sizing: border-box;
  display: grid;
  grid-template-columns: 1fr;
  align-content: center;
  gap: 22px;
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
  max-width: 420px;
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

.portal-links a {
  color: var(--c-primary);
  text-decoration: none;
}

.portal-links span {
  margin: 0 4px;
}

@media (min-width: 860px) {
  .login-page {
    grid-template-columns: 1.15fr 0.85fr;
    align-items: center;
    gap: 42px;
    padding: 40px 32px;
  }

  .login-panel {
    padding: 30px 26px;
  }
}
</style>
