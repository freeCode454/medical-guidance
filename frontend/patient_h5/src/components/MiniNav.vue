<script setup lang="ts">
import { useRouter } from 'vue-router'

withDefaults(
  defineProps<{
    title?: string
    back?: boolean
  }>(),
  { title: '', back: false },
)

const router = useRouter()

function goBack() {
  if (window.history.length > 1) router.back()
  else router.replace('/')
}
</script>

<template>
  <header class="mini-nav">
    <button v-if="back" class="mini-nav__back" type="button" aria-label="返回" @click="goBack">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M14.5 5.5L8 12l6.5 6.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>
    <span v-else class="mini-nav__placeholder" aria-hidden="true" />
    <h1>{{ title }}</h1>
    <div class="mini-nav__right">
      <slot name="right" />
    </div>
  </header>
</template>

<style scoped>
.mini-nav {
  position: sticky;
  top: 0;
  z-index: 30;
  height: calc(44px + env(safe-area-inset-top));
  padding: env(safe-area-inset-top) 12px 0;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) 56px;
  align-items: center;
  background: rgba(255, 253, 249, 0.96);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--c-line);
}

.mini-nav h1 {
  font-family: var(--font-body);
  font-size: 16px;
  font-weight: 600;
  color: var(--c-ink);
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-nav__back {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--c-ink);
  cursor: pointer;
}

.mini-nav__back:active {
  background: var(--c-surface-soft);
}

.mini-nav__back svg {
  width: 22px;
  height: 22px;
}

.mini-nav__placeholder {
  width: 36px;
}

.mini-nav__right {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}
</style>
