<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const active = computed(() => (route.path === '/profile' ? 'profile' : 'home'))
</script>

<template>
  <nav class="mini-tabbar" aria-label="底部导航">
    <router-link to="/" class="mini-tabbar__item" :class="{ 'is-active': active === 'home' }">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M4 10.5L12 4l8 6.5V20a1 1 0 01-1 1h-5v-6h-4v6H5a1 1 0 01-1-1v-9.5z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
      </svg>
      <span>首页</span>
    </router-link>
    <router-link to="/profile" class="mini-tabbar__item" :class="{ 'is-active': active === 'profile' }">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="8" r="3.5" stroke="currentColor" stroke-width="1.7" />
        <path d="M4.5 20c0-3.6 3.4-5.5 7.5-5.5s7.5 1.9 7.5 5.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
      </svg>
      <span>我的</span>
    </router-link>
  </nav>
</template>

<style scoped>
.mini-tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 40;
  display: flex;
  height: calc(52px + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.98);
  border-top: 1px solid #ededed;
}

.mini-tabbar__item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: #999999;
  text-decoration: none;
  font-size: 10px;
}

.mini-tabbar__item svg {
  width: 22px;
  height: 22px;
}

.mini-tabbar__item.is-active {
  color: #07c160;
  font-weight: 500;
}

.mini-tabbar__item:active {
  background: #f7f7f7;
}
</style>
