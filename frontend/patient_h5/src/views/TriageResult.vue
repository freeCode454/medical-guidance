<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'

const router = useRouter()
const store = useSessionStore()
const loading = ref(true)

onMounted(async () => {
  try {
    await store.loadTriage()
  } finally {
    loading.value = false
  }
})

function pct(n: number) {
  return Math.round(n * 100) + '%'
}
</script>

<template>
  <div class="result">
    <template v-if="loading">
      <div class="loading">正在生成分诊建议…</div>
    </template>

    <template v-else-if="store.triage">
      <header class="head">
        <p class="eyebrow">分诊建议</p>
        <h1>建议您就诊</h1>
      </header>

      <!-- 首要推荐 -->
      <div v-if="store.triage.recommended_depts[0]" class="primary">
        <span class="dept-name">{{ store.triage.recommended_depts[0].dept_name }}</span>
        <span class="match">匹配度 {{ pct(store.triage.recommended_depts[0].confidence) }}</span>
      </div>

      <!-- 其他候选 -->
      <div v-if="store.triage.recommended_depts.length > 1" class="others">
        <div
          v-for="(d, i) in store.triage.recommended_depts.slice(1)"
          :key="d.dept_code"
          class="other"
        >
          <span class="o-name">{{ d.dept_name }}</span>
          <span class="o-match">{{ pct(d.confidence) }}</span>
        </div>
      </div>

      <p class="disclaimer">{{ store.triage.disclaimer }}</p>

      <div class="actions">
        <button class="primary-btn" @click="router.push('/emr')">查看预问诊病历</button>
        <button class="ghost-btn" @click="router.push('/')">重新问诊</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.result {
  padding: 40px 24px 24px;
  min-height: 100vh;
}

.loading {
  text-align: center;
  color: var(--c-muted);
  padding-top: 120px;
}

.head {
  margin-bottom: 24px;
}

.eyebrow {
  color: var(--c-accent);
  font-size: 13px;
  margin: 0 0 8px;
}

h1 {
  font-size: 28px;
}

.primary {
  background: var(--c-primary);
  color: #fff;
  border-radius: var(--radius);
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dept-name {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 600;
}

.match {
  font-size: 14px;
  opacity: 0.85;
}

.others {
  margin-top: 14px;
  background: var(--c-surface);
  border: 1px solid var(--c-line);
  border-radius: var(--radius);
  overflow: hidden;
}

.other {
  display: flex;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--c-line);
}
.other:last-child {
  border-bottom: none;
}

.o-name {
  font-size: 15px;
  color: var(--c-ink);
}

.o-match {
  font-size: 14px;
  color: var(--c-muted);
}

.disclaimer {
  margin-top: 20px;
  font-size: 12px;
  color: var(--c-muted);
  line-height: 1.6;
}

.actions {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.primary-btn {
  background: var(--c-accent);
  color: #fff;
  border: none;
  border-radius: 999px;
  padding: 15px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}

.ghost-btn {
  background: transparent;
  color: var(--c-primary);
  border: 1px solid var(--c-primary);
  border-radius: 999px;
  padding: 15px;
  font-size: 15px;
  cursor: pointer;
}
</style>
