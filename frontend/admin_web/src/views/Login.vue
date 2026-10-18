<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const account = ref('admin')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function doLogin() {
  error.value = ''
  if (!account.value.trim() || !password.value) {
    error.value = '请输入账号和密码'
    return
  }
  loading.value = true
  try {
    await auth.login(account.value.trim(), password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    const fallback = auth.user?.role === 'KB_ADMIN' ? '/kb' : '/users'
    router.push(redirect || fallback)
  } catch (e) {
    error.value = (e as Error).message || '登录失败，请检查账号或口令'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

function fillDemo() {
  account.value = 'admin'
  password.value = 'admin123'
}
</script>

<template>
  <div class="login-page">
    <section class="brand-panel">
      <div class="brand-panel__glow" aria-hidden="true" />
      <div class="brand">
        <span class="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M3 12h4l2.4-6 4.2 12 2.4-6H21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <span class="brand__text"><b>智能导诊</b><em>管理后台</em></span>
      </div>

      <div class="brand-copy">
        <p class="eyebrow">机构 · 知识 · 审计</p>
        <h1>让知识库与分诊规则，<br />始终处于可控状态</h1>
        <p class="lede">维护科室与账号、校验检索召回、发布知识版本；每一次敏感操作都能在审计日志里追溯。</p>
      </div>

      <ul class="feature-list">
        <li><span>01</span><div><b>组织与账号</b><p>医生、知识库管理员、机构管理员的权限分层</p></div></li>
        <li><span>02</span><div><b>知识发布</b><p>条目启用、检索测试、版本发布一套流程</p></div></li>
        <li><span>03</span><div><b>全程留痕</b><p>分诊确认/修正、病历读取、出域调用均写审计</p></div></li>
      </ul>

      <p class="footnote">仅限授权管理员访问 · 登录行为写入审计日志</p>
    </section>

    <section class="form-panel">
      <form class="login-card" novalidate @submit.prevent="doLogin">
        <p class="eyebrow form-eyebrow">管理员登录</p>
        <h2>管理控制台</h2>
        <p class="hint">使用机构管理员或知识库管理员账号登录。</p>

        <div v-if="error" class="error-box" role="alert">{{ error }}</div>

        <label class="field">
          <span class="field__label">账号</span>
          <el-input v-model="account" size="large" placeholder="请输入管理员账号" autocomplete="username" />
        </label>

        <label class="field">
          <span class="field__label">口令</span>
          <el-input
            v-model="password"
            type="password"
            size="large"
            show-password
            placeholder="请输入登录口令"
            autocomplete="current-password"
            @keyup.enter="doLogin"
          />
        </label>

        <el-button class="submit" type="primary" size="large" :loading="loading" native-type="submit">
          {{ loading ? '正在登录…' : '登录控制台' }}
        </el-button>

        <button class="demo" type="button" @click="fillDemo">
          <span class="demo__dot" aria-hidden="true" />
          演示账号 admin / admin123
          <em>点此填入</em>
        </button>

        <p class="secure">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="5" y="10" width="14" height="10" rx="3" stroke="currentColor" stroke-width="1.6" />
            <path d="M8.5 10V7.5a3.5 3.5 0 017 0V10" stroke="currentColor" stroke-width="1.6" />
          </svg>
          登录失败 5 次锁定 15 分钟；机构管理员与知识库管理员菜单不同
        </p>
      </form>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  background: var(--c-bg);
}

.brand-panel {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 40px 48px;
  color: #eaf3f1;
  background:
    radial-gradient(120% 120% at 100% 0%, rgba(191, 106, 52, 0.28), transparent 52%),
    linear-gradient(150deg, #17504e, #0d3533 70%);
}

.brand-panel__glow {
  position: absolute;
  right: -120px;
  bottom: -160px;
  width: 420px;
  height: 420px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(191, 106, 52, 0.22), transparent 65%);
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  position: relative;
}

.brand__mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: #f6d9c2;
}

.brand__mark svg {
  width: 22px;
  height: 22px;
}

.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.brand__text b {
  font-family: var(--font-display);
  font-size: 16px;
  letter-spacing: 0.06em;
}

.brand__text em {
  font-style: normal;
  font-size: 10.5px;
  color: #a9c6c2;
  letter-spacing: 0.12em;
}

.brand-copy {
  position: relative;
  margin-top: auto;
  padding-top: 64px;
}

.eyebrow {
  font-size: 11.5px;
  letter-spacing: 0.16em;
  color: #e2b28e;
}

.brand-copy h1 {
  margin-top: 14px;
  font-size: clamp(30px, 3.2vw, 42px);
  line-height: 1.3;
  color: #fff;
}

.lede {
  margin-top: 16px;
  max-width: 30em;
  font-size: 14px;
  line-height: 1.85;
  color: #b9d1cd;
}

.feature-list {
  position: relative;
  list-style: none;
  margin: 36px 0 0;
  padding: 0;
  display: grid;
  gap: 14px;
}

.feature-list li {
  display: grid;
  grid-template-columns: 30px 1fr;
  gap: 12px;
  align-items: start;
}

.feature-list li > span {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 10px;
  color: #a9c6c2;
}

.feature-list b {
  font-size: 13.5px;
  font-weight: 500;
  color: #f2f8f6;
}

.feature-list p {
  margin-top: 2px;
  font-size: 12px;
  color: #9dbab6;
}

.footnote {
  position: relative;
  margin-top: auto;
  padding-top: 36px;
  font-size: 11px;
  color: #7fa09b;
}

.form-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 28px;
  background:
    radial-gradient(600px 400px at 100% 0%, rgba(191, 106, 52, 0.07), transparent 60%),
    var(--c-bg);
}

.login-card {
  width: 100%;
  max-width: 360px;
}

.form-eyebrow {
  color: var(--c-accent-strong);
}

.login-card h2 {
  margin-top: 10px;
  font-size: 30px;
  line-height: 1.25;
}

.hint {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--c-muted);
}

.error-box {
  margin-top: 16px;
  padding: 9px 12px;
  border: 1px solid rgba(180, 67, 47, 0.24);
  border-radius: 10px;
  background: rgba(180, 67, 47, 0.07);
  color: var(--c-danger);
  font-size: 12.5px;
}

.field {
  display: block;
  margin-top: 18px;
}

.field__label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--c-muted);
}

.submit {
  width: 100%;
  margin-top: 22px;
  height: 48px;
  font-size: 15px;
  letter-spacing: 0.06em;
}

.demo {
  width: 100%;
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 9px 12px;
  border: 1px dashed var(--c-line);
  border-radius: 10px;
  background: transparent;
  color: var(--c-muted);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease;
}

.demo:hover {
  border-color: var(--c-primary-line);
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

.demo__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-success);
}

.demo em {
  font-style: normal;
  color: var(--c-faint);
}

.secure {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 18px;
  font-size: 11px;
  line-height: 1.65;
  color: var(--c-faint);
}

.secure svg {
  flex: none;
  width: 13px;
  height: 13px;
  margin-top: 2px;
  color: var(--c-primary);
  opacity: 0.7;
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
    padding: 32px 22px;
  }

  .login-card {
    max-width: 380px;
  }
}
</style>
