<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useSessionStore } from '@/stores/session'

const router = useRouter()
const store = useSessionStore()
const complaint = ref('')
const loading = ref(false)

async function start() {
  const text = complaint.value.trim()
  if (!text) {
    showToast('请先描述一下您的症状')
    return
  }
  loading.value = true
  try {
    await store.startSession(text)
    router.push('/chat')
  } catch (e) {
    showToast((e as Error).message || '启动问诊失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="home">
    <header class="hero">
      <p class="eyebrow">智能导诊 · 预问诊</p>
      <h1>哪里不舒服，<br />先告诉它</h1>
      <p class="sub">用您自己的话说清症状，它会像医生一样追问，帮您找到该挂的科室。</p>
    </header>

    <div class="complain-card">
      <textarea
        v-model="complaint"
        class="complain-input"
        placeholder="例如：肚子疼三天了，还有点拉肚子……"
        rows="5"
        maxlength="300"
      />
      <div class="card-foot">
        <span class="hint">描述越具体，判断越准确</span>
        <span class="count">{{ complaint.length }}/300</span>
      </div>
    </div>

    <button class="start-btn" :disabled="loading" @click="start">
      {{ loading ? '正在准备…' : '开始问诊' }}
    </button>

    <p class="disclaimer">本系统仅提供分诊建议，不构成医学诊断。急危重症请立即拨打 120。</p>
  </div>
</template>

<style scoped>
.home {
  padding: 40px 24px 24px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.hero {
  margin-bottom: 28px;
}

.eyebrow {
  color: var(--c-accent);
  font-size: 13px;
  letter-spacing: 0.04em;
  margin: 0 0 10px;
}

h1 {
  font-size: 30px;
  line-height: 1.3;
  margin-bottom: 12px;
}

.sub {
  color: var(--c-muted);
  font-size: 15px;
  margin: 0;
  max-width: 320px;
}

.complain-card {
  background: var(--c-surface);
  border: 1px solid var(--c-line);
  border-radius: var(--radius);
  padding: 16px;
  box-shadow: var(--shadow);
}

.complain-input {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-size: 16px;
  font-family: var(--font-body);
  color: var(--c-ink);
  line-height: 1.7;
  background: transparent;
}

.card-foot {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 12px;
  color: var(--c-muted);
}

.start-btn {
  margin-top: 24px;
  background: var(--c-accent);
  color: #fff;
  border: none;
  border-radius: 999px;
  padding: 16px;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
}

.start-btn:active {
  transform: scale(0.98);
}

.start-btn:disabled {
  opacity: 0.6;
}

.disclaimer {
  margin-top: auto;
  padding-top: 32px;
  font-size: 12px;
  color: var(--c-muted);
  text-align: center;
}
</style>
