<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const displayName = computed(() => auth.user?.real_name || auth.user?.account || '医生')
const initial = computed(() => displayName.value.slice(0, 1))

function logout() {
  auth.logout()
  window.location.assign('http://127.0.0.1:5173/login')
}
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <div class="brand" role="link" tabindex="0" @click="router.push('/')" @keyup.enter="router.push('/')">
        <span class="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path
              d="M3 12h4l2.4-6 4.2 12 2.4-6H21"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </span>
        <span class="brand__text">
          <b>智能导诊</b>
          <em>医生工作台</em>
        </span>
      </div>

      <nav class="nav" aria-label="主导航">
        <router-link to="/" class="nav__item" :class="{ 'is-active': route.name === 'encounters' }">
          今日接诊
        </router-link>
        <router-link
          to="/takeover"
          class="nav__item"
          :class="{ 'is-active': route.name === 'takeover' }"
        >
          待接管队列
        </router-link>
      </nav>

      <div class="right">
        <el-dropdown trigger="click">
          <button class="user" type="button">
            <span class="avatar" aria-hidden="true">{{ initial }}</span>
            <span class="user__text">
              <b>{{ displayName }}</b>
              <em>{{ auth.user?.title || '医师' }}</em>
            </span>
            <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M7 10l5 5 5-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>{{ auth.user?.dept_name || '未分配科室' }}</el-dropdown-item>
              <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: linear-gradient(120deg, #144b47, #0f3b39 70%);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.06) inset, 0 10px 30px -18px rgba(15, 59, 57, 0.7);
}

.header-inner {
  display: flex;
  align-items: center;
  gap: 28px;
  width: 100%;
  max-width: 1120px;
  height: 64px;
  margin: 0 auto;
  padding: 0 28px;
  color: #fff;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  flex: none;
  border-radius: 10px;
}

.brand__mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
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
  font-weight: 600;
  letter-spacing: 0.06em;
}

.brand__text em {
  font-style: normal;
  font-size: 10.5px;
  color: #a9c6c2;
  letter-spacing: 0.1em;
}

.nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.nav__item {
  padding: 8px 14px;
  border-radius: 9px;
  font-size: 13.5px;
  color: #c2d8d4;
  text-decoration: none;
  transition: background 0.18s ease, color 0.18s ease;
}

.nav__item:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.07);
}

.nav__item.is-active {
  color: #fff;
  background: rgba(255, 255, 255, 0.14);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.1) inset;
}

.right {
  flex: none;
}

.user {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 5px 8px 5px 5px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.18s ease;
}

.user:hover {
  background: rgba(255, 255, 255, 0.12);
}

.avatar {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #f3dcc8;
  color: #7d3f1c;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
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
}

.user__text em {
  font-style: normal;
  font-size: 10.5px;
  color: #a9c6c2;
}

.chev {
  width: 14px;
  height: 14px;
  color: #a9c6c2;
}

@media (max-width: 760px) {
  .header-inner {
    gap: 12px;
    padding: 0 14px;
  }

  .brand__text em,
  .user__text {
    display: none;
  }

  .nav__item {
    padding: 7px 9px;
    font-size: 12.5px;
  }
}
</style>
