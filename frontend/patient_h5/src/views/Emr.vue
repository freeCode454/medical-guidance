<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { getEmr } from '@/api/patient'
import type { EmrView } from '@/api/patient'
import MiniNav from '@/components/MiniNav.vue'

const router = useRouter()
const store = useSessionStore()
const emr = ref<EmrView | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    emr.value = await getEmr(store.sessionId)
  } catch (e) {
    error.value = (e as Error).message || '获取病历失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="emr">
    <MiniNav title="预问诊病历" back />

    <section class="emr-intro">
      <p>以下内容由本次问诊自动整理，就诊时可直接出示给医生。</p>
      <p v-if="store.sessionNo" class="no">问诊号 <b class="tnum">{{ store.sessionNo }}</b></p>
    </section>

    <div v-if="loading" class="loading" role="status">
      <span class="spinner" aria-hidden="true" />
      <p>正在整理病历…</p>
    </div>

    <div v-else-if="error" class="loading" role="alert">
      <p>暂时没能取到病历</p>
      <p class="err">{{ error }}</p>
      <button class="ghost-btn retry" type="button" @click="load">重试</button>
    </div>

    <template v-else-if="emr">
      <section class="section">
        <header class="section__head">
          <span class="letter">S</span>
          <span class="section__title">
            <h2>主观描述</h2>
            <p>您自己说的情况</p>
          </span>
        </header>
        <p class="body">{{ emr.subjective.chief_complaint }}</p>
        <p v-if="emr.subjective.present_illness" class="body body--soft">
          {{ emr.subjective.present_illness }}
        </p>

        <div v-if="emr.subjective.allergy.length" class="tags">
          <span class="tags__label">过敏史</span>
          <span v-for="a in emr.subjective.allergy" :key="a" class="tag tag--warn">{{ a }}</span>
        </div>
        <div v-if="emr.subjective.past_history.length" class="tags">
          <span class="tags__label">既往史</span>
          <span v-for="h in emr.subjective.past_history" :key="h" class="tag">{{ h }}</span>
        </div>
      </section>

      <section class="section">
        <header class="section__head">
          <span class="letter letter--amber">O</span>
          <span class="section__title">
            <h2>客观信息</h2>
            <p>问诊中采集到的信息</p>
          </span>
        </header>
        <p class="body">{{ emr.objective.note || '本次问诊未采集额外客观信息。' }}</p>
      </section>

      <section class="section">
        <header class="section__head">
          <span class="letter">P</span>
          <span class="section__title">
            <h2>就诊建议</h2>
            <p>建议科室与准备事项</p>
          </span>
        </header>
        <div v-if="emr.plan.recommended_depts.length" class="tags">
          <span v-for="d in emr.plan.recommended_depts" :key="d" class="tag tag--dept">{{ d }}</span>
        </div>
        <p class="body">{{ emr.plan.note }}</p>
        <div v-if="emr.plan.suggested_workup.length" class="tags">
          <span class="tags__label">可能需要的检查</span>
          <span v-for="w in emr.plan.suggested_workup" :key="w" class="tag">{{ w }}</span>
        </div>
      </section>

      <p class="disclaimer">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3l7 3v5.2c0 4.6-2.9 7.9-7 9.8-4.1-1.9-7-5.2-7-9.8V6l7-3z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
          <path d="M12 8.5v4M12 15.4v.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        </svg>
        {{ emr.disclaimer }}
      </p>

      <div class="actions">
        <button class="primary-btn" type="button" @click="router.push('/')">完成</button>
        <button class="ghost-btn" type="button" @click="router.push('/result')">返回分诊建议</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.emr {
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  max-width: 600px;
  margin: 0 auto;
  padding: 14px 14px calc(28px + env(safe-area-inset-bottom));
  box-sizing: border-box;
  background: transparent;
}

.emr-intro {
  margin-top: 12px;
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--c-surface);
  color: var(--c-muted);
  font-size: 12px;
  line-height: 1.7;
}

.emr-intro .no {
  margin-top: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--c-faint);
  font-size: 11px;
}

/* ---------- 标题 ---------- */
.head {
  margin-bottom: 22px;
}

.eyebrow {
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--c-accent-text);
  margin-bottom: 8px;
}

h1 {
  font-size: clamp(26px, 6.6vw, 32px);
  line-height: 1.26;
  letter-spacing: 0.01em;
}

.lede {
  margin-top: 10px;
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--c-muted);
}

.no {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 4px 10px;
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-pill);
  background: rgba(255, 253, 249, 0.7);
  font-size: 11px;
  color: var(--c-muted);
}

.no b {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--c-ink-soft);
}

/* ---------- 加载 ---------- */
.loading {
  padding-top: 70px;
  text-align: center;
  color: var(--c-muted);
  font-size: 13px;
}

.loading .spinner {
  display: inline-block;
  width: 24px;
  height: 24px;
  border: 2px solid var(--c-primary-line);
  border-top-color: var(--c-primary);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

.loading p {
  margin-top: 12px;
}

.loading .err {
  margin-top: 6px;
  font-size: 12px;
  color: var(--c-muted);
}

.loading .retry {
  margin-top: 16px;
  padding: 9px 26px;
}

/* ---------- 病历分区 ---------- */
.section {
  margin-bottom: 14px;
  padding: 18px 18px 16px;
  border: 1px solid var(--c-line);
  border-radius: 22px;
  background: var(--c-surface);
  box-shadow: var(--shadow-sm);
  animation: rise 0.55s var(--ease-out) both;
}

.section:nth-of-type(2) {
  animation-delay: 0.06s;
}

.section:nth-of-type(3) {
  animation-delay: 0.12s;
}

.section__head {
  display: flex;
  align-items: center;
  gap: 11px;
  padding-bottom: 13px;
  margin-bottom: 13px;
  border-bottom: 1px dashed var(--c-line);
}

.letter {
  flex: none;
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: var(--c-primary-soft);
  border: 1px solid rgba(201, 219, 213, 0.8);
  color: var(--c-primary);
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
}

.letter--amber {
  background: var(--c-accent-soft);
  border-color: rgba(230, 205, 175, 0.9);
  color: var(--c-accent-strong);
}

.section__title h2 {
  font-family: var(--font-body);
  font-size: 14.5px;
  font-weight: 600;
  color: var(--c-ink);
  letter-spacing: 0.02em;
}

.section__title p {
  margin-top: 1px;
  font-size: 11px;
  color: var(--c-faint);
}

.body {
  font-size: 14.5px;
  line-height: 1.8;
  color: var(--c-ink);
}

.body + .body {
  margin-top: 8px;
}

.body--soft {
  color: var(--c-ink-soft);
}

/* ---------- 标签 ---------- */
.tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  margin-top: 12px;
}

.tags__label {
  font-size: 11px;
  color: var(--c-muted);
  margin-right: 1px;
}

.tag {
  padding: 4px 11px;
  border-radius: var(--r-pill);
  background: var(--c-surface-soft);
  border: 1px solid var(--c-line-soft);
  font-size: 12px;
  color: var(--c-ink-soft);
}

.tag--warn {
  background: rgba(191, 106, 52, 0.1);
  border-color: rgba(191, 106, 52, 0.22);
  color: var(--c-accent-strong);
}

.tag--dept {
  background: var(--c-primary-soft);
  border-color: var(--c-primary-line);
  color: var(--c-primary);
  font-size: 13px;
  padding: 5px 13px;
}

/* ---------- 免责与操作 ---------- */
.disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 18px 0 22px;
  padding: 11px 13px;
  border: 1px solid rgba(230, 205, 175, 0.7);
  border-radius: 14px;
  background: rgba(247, 231, 217, 0.5);
  font-size: 11.5px;
  line-height: 1.7;
  color: #7a5a3e;
}

.disclaimer svg {
  flex: none;
  width: 15px;
  height: 15px;
  margin-top: 2px;
  color: var(--c-accent);
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.primary-btn {
  border: 0;
  border-radius: var(--r-pill);
  padding: 15px;
  background: #07c160;
  color: #fff;
  font-size: 15.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  cursor: pointer;
  box-shadow: var(--shadow-accent);
  transition: transform var(--dur-fast) var(--ease-out), filter var(--dur-fast) var(--ease-out);
}

.primary-btn:hover {
  transform: translateY(-1px);
  filter: brightness(1.03);
}

.ghost-btn {
  border: 1px solid var(--c-line);
  border-radius: var(--r-pill);
  padding: 13px;
  background: transparent;
  color: var(--c-primary);
  font-size: 13.5px;
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out);
}

.ghost-btn:hover {
  background: rgba(227, 237, 233, 0.5);
  border-color: var(--c-primary-line);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
