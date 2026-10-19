<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthForm from '@/components/AuthForm.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const loading = ref(false)
const error = ref('')

async function onSubmit(payload: { account: string; password: string }) {
  loading.value = true
  error.value = ''
  try {
    await auth.login(payload.account, payload.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    router.push(redirect || '/')
  } catch (e) {
    error.value = (e as Error).message || '登录失败，请检查账号或口令'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="brand-panel">
      <div class="brand-panel__glow" aria-hidden="true" />
      <div class="brand">
        <span class="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M3 12h4l2.4-6 4.2 12 2.4-6H21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <span class="brand__text"><b>智能导诊</b><em>医生工作台</em></span>
      </div>

      <div class="brand-copy">
        <p class="eyebrow">AI 预问诊 · 分诊协同</p>
        <h1>把问诊前的那段空白，<br />交给系统先填好</h1>
        <p class="lede">患者的主诉、追问记录、分诊结论与 SOAP 病历已经在工作台里，接诊时直接看结论。</p>
      </div>

      <ul class="feature-list">
        <li><span>01</span><div><b>待接管队列</b><p>按风险与等待时长排序，认领即接管</p></div></li>
        <li><span>02</span><div><b>分诊结论与依据</b><p>候选科室、知识图谱路径、指南推荐</p></div></li>
        <li><span>03</span><div><b>确认与修正留痕</b><p>修正进入评测样本，全程审计</p></div></li>
      </ul>

      <p class="footnote">本系统仅提供分诊建议，不构成医学诊断</p>
    </section>

    <section class="form-panel">
      <AuthForm
        portal="DOCTOR"
        :loading="loading"
        :error="error"
        demo-account="doctor01"
        demo-password="admin123"
        @submit="onSubmit"
      />
      <p class="switch-portal">
        患者入口：<a href="http://127.0.0.1:5173/login">患者端</a>
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
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(420px, 0.95fr);
  background: var(--c-bg);
}

.brand-panel {
  position: relative;
  overflow: hidden;
  padding: 46px 54px;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(900px 520px at 12% 8%, rgba(42, 104, 96, 0.4), transparent 60%),
    linear-gradient(155deg, #103d3b 0%, #0b2c2b 68%, #092322 100%);
  color: #e9f1ed;
}

.brand-panel__glow {
  position: absolute;
  right: -160px;
  bottom: -190px;
  width: 480px;
  height: 480px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(201, 118, 60, 0.3), transparent 66%);
  pointer-events: none;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
}

.brand__mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  border: 1px solid rgba(233, 241, 237, 0.22);
  background: rgba(233, 241, 237, 0.08);
}

.brand__mark svg {
  width: 19px;
  height: 19px;
}

.brand__text b {
  display: block;
  font-family: var(--font-display);
  font-size: 17px;
}

.brand__text em {
  display: block;
  margin-top: 1px;
  font-style: normal;
  font-size: 10px;
  letter-spacing: 0.16em;
  color: rgba(233, 241, 237, 0.55);
}

.brand-copy {
  margin-top: auto;
  padding-top: 70px;
  position: relative;
}

.eyebrow {
  font-size: 11px;
  letter-spacing: 0.16em;
  color: rgba(242, 201, 164, 0.82);
}

.brand-copy h1 {
  margin-top: 12px;
  font-family: var(--font-display);
  font-size: clamp(34px, 4.6vw, 48px);
  line-height: 1.3;
  letter-spacing: -0.02em;
}

.lede {
  margin-top: 16px;
  max-width: 440px;
  color: rgba(233, 241, 237, 0.68);
  font-size: 13px;
  line-height: 1.85;
}

.feature-list {
  position: relative;
  margin: 38px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 16px;
}

.feature-list li {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.feature-list li > span {
  width: 26px;
  height: 26px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid rgba(233, 241, 237, 0.18);
  color: rgba(242, 201, 164, 0.85);
  font-family: var(--font-mono);
  font-size: 9px;
}

.feature-list b {
  display: block;
  font-size: 12.5px;
  font-weight: 500;
}

.feature-list p {
  margin: 3px 0 0;
  color: rgba(233, 241, 237, 0.5);
  font-size: 11px;
  line-height: 1.65;
}

.footnote {
  position: relative;
  margin-top: 34px;
  color: rgba(233, 241, 237, 0.36);
  font-size: 10.5px;
}

.form-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 44px 42px;
  background: var(--c-surface);
}

.switch-portal {
  margin-top: 22px;
  text-align: center;
  font-size: 10.5px;
  color: var(--c-faint);
}

.switch-portal a {
  color: var(--c-primary);
  text-decoration: none;
}

.switch-portal span {
  margin: 0 4px;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .brand-panel {
    display: none;
  }

  .form-panel {
    min-height: 100vh;
    min-height: 100dvh;
    padding: 34px 22px;
  }
}
</style>
