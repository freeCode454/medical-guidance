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
  icon: string
}

const groups: Array<{ label: string; items: MenuItem[] }> = [
  {
    label: '工作台',
    items: [
      {
        path: '/users',
        label: '用户管理',
        roles: ['ORG_ADMIN'],
        icon: 'M16 11a4 4 0 10-8 0 4 4 0 008 0zM4 20c0-3.4 3.6-5 8-5s8 1.6 8 5',
      },
      {
        path: '/depts',
        label: '科室管理',
        roles: ['ORG_ADMIN'],
        icon: 'M4 20V7l8-4 8 4v13M9 20v-5h6v5M8 9h2M14 9h2M8 12h2M14 12h2',
      },
    ],
  },
  {
    label: '知识与图谱',
    items: [
      {
        path: '/kb',
        label: '知识库',
        roles: ['ORG_ADMIN', 'KB_ADMIN'],
        icon: 'M5 5.5A2.5 2.5 0 017.5 3H19v18H7.5A2.5 2.5 0 015 18.5v-13zM9 7h6M9 11h6',
      },
      {
        path: '/kg',
        label: '知识图谱',
        roles: ['ORG_ADMIN', 'KB_ADMIN'],
        icon: 'M7 8a2 2 0 100-4 2 2 0 000 4zM17 13a2 2 0 100-4 2 2 0 000 4zM9 19a2 2 0 100-4 2 2 0 000 4zM8.5 7l6 3M8 15l1-5M11 17l4-3',
      },
    ],
  },
  {
    label: '系统',
    items: [
      {
        path: '/audit',
        label: '审计日志',
        roles: ['ORG_ADMIN', 'KB_ADMIN'],
        icon: 'M6 3h9l3 3v15H6zM14 3v4h4M9 12h6M9 16h4',
      },
      {
        path: '/settings',
        label: '系统设置',
        roles: ['ORG_ADMIN'],
        icon: 'M4 7h16M4 12h16M4 17h16M8 5v4M15 10v4M10 15v4',
      },
    ],
  },
]

const role = computed(() => auth.user?.role ?? getTokenRole())
const visibleGroups = computed(() =>
  groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !role.value || item.roles.includes(role.value)),
    }))
    .filter((group) => group.items.length),
)

const roleLabel = computed(() => {
  if (role.value === 'KB_ADMIN') return '知识库管理员'
  if (role.value === 'ORG_ADMIN') return '机构管理员'
  return role.value || '管理员'
})

const current = computed(() => {
  for (const group of visibleGroups.value) {
    const item = group.items.find((entry) => entry.path === route.path)
    if (item) return { group: group.label, label: item.label }
  }
  return { group: '', label: '' }
})

const displayName = computed(() => auth.user?.real_name || auth.user?.account || '管理员')
const initial = computed(() => displayName.value.slice(0, 1))

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <router-view v-if="route.name === 'login'" />

  <div v-else class="layout">
    <aside class="aside">
      <div class="brand">
        <span class="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M3 12h4l2.4-6 4.2 12 2.4-6H21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <span class="brand__text"><b>智能导诊</b><em>管理后台</em></span>
      </div>

      <nav class="nav" aria-label="主导航">
        <div v-for="group in visibleGroups" :key="group.label" class="nav__group">
          <p class="nav__label">{{ group.label }}</p>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="nav__item"
            :class="{ 'is-active': route.path === item.path }"
          >
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path :d="item.icon" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span>{{ item.label }}</span>
          </router-link>
        </div>
      </nav>

      <div class="aside-foot">
        <span class="env-dot" aria-hidden="true" />
        <span>开发环境</span>
        <em>v0.1.0</em>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="crumb">
          <span v-if="current.group" class="crumb__group">{{ current.group }}</span>
          <i v-if="current.group" aria-hidden="true">/</i>
          <b>{{ current.label }}</b>
        </div>

        <div class="topbar__right">
          <span class="role-badge">{{ roleLabel }}</span>
          <el-dropdown trigger="click">
            <button class="user" type="button">
              <span class="avatar">{{ initial }}</span>
              <span class="user__text">
                <b>{{ displayName }}</b>
                <em>{{ auth.user?.tenant_name || '演示机构' }}</em>
              </span>
              <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M7 10l5 5 5-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>{{ roleLabel }}</el-dropdown-item>
                <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 226px minmax(0, 1fr);
  min-height: 100vh;
  background:
    radial-gradient(1000px 520px at 88% -10%, rgba(191, 106, 52, 0.05), transparent 60%),
    var(--c-bg);
}

/* ---------- 侧栏 ---------- */
.aside {
  display: flex;
  flex-direction: column;
  padding: 20px 14px 16px;
  color: #dbe9e6;
  background:
    radial-gradient(120% 80% at 100% 0%, rgba(191, 106, 52, 0.18), transparent 55%),
    linear-gradient(160deg, #17504e, #0d3533 72%);
  position: sticky;
  top: 0;
  height: 100vh;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 20px;
}

.brand__mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.16);
  color: #f6d9c2;
}

.brand__mark svg {
  width: 20px;
  height: 20px;
}

.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.brand__text b {
  font-family: var(--font-display);
  font-size: 15px;
  color: #fff;
  letter-spacing: 0.06em;
}

.brand__text em {
  font-style: normal;
  font-size: 10.5px;
  color: #a9c6c2;
  letter-spacing: 0.12em;
}

.nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.nav__group {
  display: grid;
  gap: 3px;
}

.nav__label {
  padding: 0 10px;
  margin-bottom: 4px;
  font-size: 10.5px;
  letter-spacing: 0.12em;
  color: #7fa09b;
}

.nav__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 9px;
  color: #c2d8d4;
  text-decoration: none;
  font-size: 13.5px;
  transition: background 0.18s ease, color 0.18s ease;
}

.nav__item svg {
  width: 17px;
  height: 17px;
  flex: none;
  opacity: 0.9;
}

.nav__item:hover {
  background: rgba(255, 255, 255, 0.07);
  color: #fff;
}

.nav__item.is-active {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.1) inset;
}

.aside-foot {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 12px 10px 2px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 11px;
  color: #9dbab6;
}

.aside-foot em {
  margin-left: auto;
  font-style: normal;
  font-family: var(--font-mono);
  font-size: 10px;
  color: #7fa09b;
}

.env-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #e2b28e;
  box-shadow: 0 0 0 3px rgba(226, 178, 142, 0.16);
}

/* ---------- 工作区 ---------- */
.workspace {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 60px;
  padding: 0 26px;
  background: rgba(255, 253, 250, 0.86);
  backdrop-filter: blur(12px) saturate(1.1);
  border-bottom: 1px solid var(--c-line-soft);
}

.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--c-muted);
}

.crumb i {
  color: var(--c-line);
  font-style: normal;
}

.crumb b {
  color: var(--c-ink);
  font-weight: 600;
}

.topbar__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.role-badge {
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid var(--c-primary-line);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 11px;
}

.user {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 4px 4px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.18s ease, border-color 0.18s ease;
}

.user:hover {
  background: var(--c-surface-soft);
  border-color: var(--c-line-soft);
}

.avatar {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--c-primary);
  color: #f3dcc8;
  font-family: var(--font-display);
  font-size: 14px;
}

.user__text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.25;
}

.user__text b {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--c-ink);
}

.user__text em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--c-muted);
}

.chev {
  width: 14px;
  height: 14px;
  color: var(--c-faint);
}

.main {
  flex: 1;
  padding: 24px 26px 48px;
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 74px minmax(0, 1fr);
  }

  .aside {
    padding: 18px 9px 14px;
  }

  .brand {
    justify-content: center;
    padding: 4px 0 18px;
  }

  .brand__text,
  .nav__label,
  .nav__item span,
  .aside-foot span,
  .aside-foot em {
    display: none;
  }

  .nav__item {
    justify-content: center;
    padding: 10px 0;
  }

  .aside-foot {
    justify-content: center;
    padding: 12px 0 0;
  }

  .topbar {
    padding: 0 14px;
  }

  .role-badge,
  .user__text {
    display: none;
  }

  .main {
    padding: 16px 14px 40px;
  }
}
</style>
