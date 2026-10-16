<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { getEmr } from '@/api/patient'
import type { EmrView } from '@/api/patient'

const router = useRouter()
const store = useSessionStore()
const emr = ref<EmrView | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    emr.value = await getEmr(store.sessionId)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="emr">
    <header class="head">
      <p class="eyebrow">预问诊病历</p>
      <h1>就诊前，医生会看到这些</h1>
    </header>

    <div v-if="loading" class="loading">正在整理病历…</div>

    <template v-else-if="emr">
      <section class="section">
        <h2 class="sec-title">主观描述（S）</h2>
        <p class="sec-body">{{ emr.subjective.chief_complaint }}</p>
        <div v-if="emr.subjective.allergy.length" class="tag-row">
          <span v-for="a in emr.subjective.allergy" :key="a" class="tag warn">{{ a }}</span>
        </div>
      </section>

      <section class="section">
        <h2 class="sec-title">客观信息（O）</h2>
        <p class="sec-body">{{ emr.objective.note }}</p>
      </section>

      <section class="section">
        <h2 class="sec-title">就诊建议（P）</h2>
        <div v-if="emr.plan.recommended_depts.length" class="tag-row">
          <span v-for="d in emr.plan.recommended_depts" :key="d" class="tag">{{ d }}</span>
        </div>
        <p class="sec-body">{{ emr.plan.note }}</p>
      </section>

      <p class="disclaimer">{{ emr.disclaimer }}</p>

      <button class="back-btn" @click="router.push('/')">完成</button>
    </template>
  </div>
</template>

<style scoped>
.emr {
  padding: 32px 24px 40px;
  min-height: 100vh;
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
  font-size: 24px;
}

.loading {
  text-align: center;
  color: var(--c-muted);
  padding-top: 80px;
}

.section {
  background: var(--c-surface);
  border: 1px solid var(--c-line);
  border-radius: var(--radius);
  padding: 18px;
  margin-bottom: 14px;
}

.sec-title {
  font-size: 14px;
  color: var(--c-primary);
  font-weight: 600;
  margin-bottom: 10px;
}

.sec-body {
  font-size: 15px;
  color: var(--c-ink);
  margin: 0;
  line-height: 1.7;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.tag {
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 13px;
  padding: 4px 12px;
  border-radius: 999px;
}

.tag.warn {
  background: rgba(201, 123, 61, 0.12);
  color: var(--c-accent);
}

.disclaimer {
  font-size: 12px;
  color: var(--c-muted);
  line-height: 1.6;
  margin: 20px 0 24px;
}

.back-btn {
  width: 100%;
  background: var(--c-primary);
  color: #fff;
  border: none;
  border-radius: 999px;
  padding: 15px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}
</style>
