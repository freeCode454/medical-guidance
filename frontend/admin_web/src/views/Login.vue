<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const account = ref('admin')
const password = ref('')
const loading = ref(false)

async function doLogin() {
  if (!account.value || !password.value) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(account.value, password.value)
    router.push('/users')
  } catch (e) {
    ElMessage.error((e as Error).message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="login-card">
      <h1 class="brand">医疗智能导诊</h1>
      <p class="sub">管理后台</p>
      <el-input v-model="account" placeholder="账号" size="large" class="mb" />
      <el-input v-model="password" type="password" placeholder="密码" size="large" show-password class="mb" @keyup.enter="doLogin" />
      <el-button type="primary" size="large" class="submit" :loading="loading" @click="doLogin">登录</el-button>
      <p class="hint">演示账号 admin / admin123</p>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, var(--c-primary) 0%, #123c3a 100%);
}

.login-card {
  width: 360px;
  background: var(--c-surface);
  border-radius: 16px;
  padding: 40px 36px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.brand { font-size: 24px; text-align: center; }
.sub { text-align: center; color: var(--c-muted); margin: 8px 0 28px; }
.mb { margin-bottom: 16px; }
.submit { width: 100%; }
.hint { margin-top: 20px; text-align: center; font-size: 12px; color: var(--c-muted); }
</style>
