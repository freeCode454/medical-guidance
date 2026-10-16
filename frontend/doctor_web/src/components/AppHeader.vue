<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <header class="app-header">
    <div class="left" @click="router.push('/')">
      <span class="logo">诊</span>
      <span class="brand">医疗智能导诊 · 医生工作台</span>
    </div>
    <div class="right">
      <el-button text @click="router.push('/takeover')">待接管队列</el-button>
      <el-dropdown>
        <span class="doctor">
          {{ auth.user?.real_name || auth.user?.account }}
          <span v-if="auth.user?.title" class="title">{{ auth.user.title }}</span>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 60px;
  background: var(--c-primary);
  color: #fff;
}

.left {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.logo {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--c-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 16px;
}

.brand {
  font-family: var(--font-display);
  font-size: 16px;
  letter-spacing: 0.02em;
}

.right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.right :deep(.el-button) {
  color: #d9e7e5;
}

.doctor {
  color: #fff;
  cursor: pointer;
  font-size: 14px;
}

.title {
  margin-left: 6px;
  font-size: 12px;
  color: #a6c3c1;
}
</style>
