<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getTokenRole } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

interface MenuItem {
  path: string
  label: string
  roles: string[]
}

const allMenus: MenuItem[] = [
  { path: '/users', label: '用户管理', roles: ['ORG_ADMIN'] },
  { path: '/depts', label: '科室管理', roles: ['ORG_ADMIN'] },
  { path: '/kb', label: '知识库', roles: ['ORG_ADMIN', 'KB_ADMIN'] },
  { path: '/kg', label: '知识图谱', roles: ['ORG_ADMIN', 'KB_ADMIN'] },
  { path: '/audit', label: '审计日志', roles: ['ORG_ADMIN', 'KB_ADMIN'] },
  { path: '/settings', label: '系统设置', roles: ['ORG_ADMIN'] },
]

const role = computed(() => auth.user?.role ?? getTokenRole())
const menus = computed(() =>
  allMenus.filter((item) => !role.value || item.roles.includes(role.value)),
)

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div v-if="route.name === 'login'">
    <router-view />
  </div>

  <el-container v-else class="layout">
    <el-aside width="200px" class="aside">
      <div class="brand">
        <span class="logo">诊</span>
        <span class="name">医疗智能导诊</span>
      </div>
      <el-menu :default-active="route.path" router class="menu">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          {{ m.label }}
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="crumb">{{ menus.find((m) => m.path === route.path)?.label || '' }}</span>
        <span class="user">{{ auth.user?.real_name || auth.user?.account }}</span>
        <el-button text size="small" @click="logout">退出</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  min-height: 100vh;
}

.aside {
  background: var(--c-primary);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px;
  color: #fff;
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
}

.name {
  font-family: var(--font-display);
  font-size: 15px;
}

.menu {
  background: transparent;
  border-right: none;
}

.menu :deep(.el-menu-item) {
  color: #b8cfcc;
}

.menu :deep(.el-menu-item.is-active) {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.header {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-line);
}

.crumb {
  font-family: var(--font-display);
  font-size: 16px;
  color: var(--c-primary);
}

.user {
  margin-left: auto;
  color: var(--c-muted);
  font-size: 14px;
}

.main {
  padding: 20px 24px;
}
</style>
