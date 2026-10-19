<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import MiniNav from '@/components/MiniNav.vue'

const router = useRouter()
const store = useSessionStore()
const loading = ref(true)
const error = ref('')

const primary = computed(() => store.triage?.recommended_depts?.[0] ?? null)
const others = computed(() => store.triage?.recommended_depts?.slice(1) ?? [])
const emergency = computed(() => store.triage?.emergency_guidance ?? null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    await store.loadTriage()
  } catch (e) {
    error.value = (e as Error).message || '获取分诊结果失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function pct(n: number) {
  return Math.round(Math.min(1, Math.max(0, n)) * 100) + '%'
}
</script>

<template>
  <div class="result">
    <MiniNav title="分诊结果" back />
    <template v-if="loading">
      <div class="loading" role="status">
        <span class="spinner" aria-hidden="true" />
        <p class="loading__title">正在生成分诊建议…</p>
        <p class="loading__hint">综合症状、伴随表现与科室专长</p>
        <div class="skeleton" aria-hidden="true">
          <span /><span /><span />
        </div>
      </div>
    </template>

    <template v-else-if="error">
      <div class="empty">
        <span class="empty__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" />
            <path d="M12 7.5v5M12 16v.2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          </svg>
        </span>
        <h2>暂时没能取到分诊结果</h2>
        <p>{{ error }}</p>
        <div class="empty__actions">
          <button class="primary-btn" type="button" @click="load">重试</button>
          <button class="ghost-btn" type="button" @click="router.push('/')">返回首页</button>
        </div>
      </div>
    </template>

    <template v-else-if="store.triage">
      <header class="head">
        <span class="badge" :class="{ 'badge--danger': emergency }" aria-hidden="true">
          <svg v-if="emergency" viewBox="0 0 24 24" fill="none">
            <path d="M12 4l8.5 15h-17L12 4z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
            <path d="M12 9.5v4M12 16.6v.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none">
            <path d="M5 12.5l4.5 4.5L19 7.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <p class="eyebrow">{{ emergency ? '危重症预警' : '分诊完成' }}</p>
        <h1>{{ emergency ? '请立即前往急诊' : '建议您就诊' }}</h1>
        <p class="lede">
          {{ emergency ? '您的描述触发了急危重症预警，请优先线下就医' : '根据您的描述，最匹配的科室是' }}
        </p>
        <p v-if="store.triage.history_used && !emergency" class="history-note">
          已结合您授权的既往病历，本次摘要会参考历史过敏史与既往史。
        </p>
      </header>

      <!-- 危重症引导：优先于科室推荐展示 -->
      <section v-if="emergency" class="emergency" role="alert">
        <span class="emergency__tag">需要立即处理</span>
        <p class="emergency__reason">{{ emergency.reason }}</p>
        <p class="emergency__advice">{{ emergency.advice }}</p>
        <p class="emergency__dept">建议直接前往：{{ emergency.recommended_dept }}</p>
      </section>

      <!-- 首选科室 -->
      <section v-if="primary && !emergency" class="primary">
        <span class="primary__glow" aria-hidden="true" />
        <div class="primary__top">
          <span class="tag">首选科室</span>
          <span class="match tnum">匹配度 {{ pct(primary.confidence) }}</span>
        </div>
        <h2 class="primary__name">{{ primary.dept_name }}</h2>
        <div class="meter" aria-hidden="true">
          <i :style="{ width: pct(primary.confidence) }" />
        </div>
        <p class="primary__hint">匹配度由症状、伴随表现与科室专长综合计算，仅供参考。</p>
      </section>

      <!-- 其他候选 -->
      <section v-if="others.length && !emergency" class="others">
        <h3 class="others__title">其他可能相关</h3>
        <ul class="list">
          <li v-for="(d, i) in others" :key="d.dept_code" class="item">
            <span class="rank tnum">{{ String(i + 2).padStart(2, '0') }}</span>
            <span class="item__name">{{ d.dept_name }}</span>
            <span class="item__meter" aria-hidden="true">
              <i :style="{ width: pct(d.confidence) }" />
            </span>
            <span class="item__num tnum">{{ pct(d.confidence) }}</span>
          </li>
        </ul>
      </section>

      <p class="disclaimer">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3l7 3v5.2c0 4.6-2.9 7.9-7 9.8-4.1-1.9-7-5.2-7-9.8V6l7-3z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
          <path d="M12 8.5v4M12 15.4v.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        </svg>
        {{ store.triage.disclaimer }}
      </p>

      <div class="actions">
        <template v-if="emergency">
          <a class="primary-btn primary-btn--danger" :href="`tel:${emergency.emergency_phone}`">
            拨打 {{ emergency.emergency_phone }} 急救电话
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M6.5 4.5h3l1.5 4-2 1.5a11 11 0 005 5l1.5-2 4 1.5v3a2 2 0 01-2.2 2A15.5 15.5 0 014.5 6.7a2 2 0 012-2.2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
            </svg>
          </a>
          <button class="ghost-btn" type="button" @click="router.push('/')">重新问诊</button>
        </template>
        <template v-else>
          <button
            v-if="primary"
            class="primary-btn"
            type="button"
            @click="router.push({ path: '/appointment', query: { dept: primary.dept_code, sessionId: store.sessionId } })"
          >
            预约挂号 · {{ primary.dept_name }}
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M6 4v3M18 4v3M4 9h16M5 6h14a1 1 0 011 1v13a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <button class="primary-btn primary-btn--book" type="button" @click="router.push('/emr')">
            查看预问诊病历
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M5 12h13M12.5 5.5L19 12l-6.5 6.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <button class="ghost-btn" type="button" @click="router.push('/')">重新问诊</button>
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped>
.result {
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  max-width: 560px;
  margin: 0 auto;
  padding: 0 14px calc(28px + env(safe-area-inset-bottom));
  box-sizing: border-box;
  background: transparent;
}

/* ---------- 加载 ---------- */
.loading {
  padding-top: 120px;
  text-align: center;
}

.spinner {
  display: inline-block;
  width: 26px;
  height: 26px;
  border: 2px solid var(--c-primary-line);
  border-top-color: var(--c-primary);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

.loading__title {
  margin-top: 14px;
  font-size: 15px;
  color: var(--c-ink-soft);
}

.loading__hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--c-muted);
}

.skeleton {
  margin: 34px auto 0;
  max-width: 340px;
  display: grid;
  gap: 12px;
}

.skeleton span {
  display: block;
  height: 54px;
  border-radius: 16px;
  background: linear-gradient(90deg, var(--c-surface-soft), #fff, var(--c-surface-soft));
  background-size: 200% 100%;
  border: 1px solid var(--c-line-soft);
  animation: shimmer 1.6s linear infinite;
}

.skeleton span:first-child {
  height: 120px;
}

/* ---------- 空/错误 ---------- */
.empty {
  padding-top: 96px;
  text-align: center;
}

.empty__icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: var(--c-surface);
  border: 1px solid var(--c-line);
  color: var(--c-muted);
}

.empty__icon svg {
  width: 24px;
  height: 24px;
}

.empty h2 {
  font-size: 20px;
}

.empty p {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--c-muted);
}

.empty__actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 320px;
  margin: 24px auto 0;
}

/* ---------- 标题 ---------- */
.head {
  margin-bottom: 24px;
  padding-top: 18px;
}

.badge {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin-bottom: 16px;
  border-radius: 50%;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  box-shadow: 0 0 0 6px rgba(227, 237, 233, 0.45);
}

.badge svg {
  width: 24px;
  height: 24px;
}

.badge--danger {
  background: rgba(180, 67, 47, 0.12);
  color: var(--c-danger);
  box-shadow: 0 0 0 6px rgba(180, 67, 47, 0.06);
}

/* ---------- 危重症引导 ---------- */
.emergency {
  margin-bottom: 16px;
  padding: 20px 20px 18px;
  border: 1px solid rgba(180, 67, 47, 0.32);
  border-radius: var(--r-lg);
  background:
    radial-gradient(120% 120% at 100% 0%, rgba(180, 67, 47, 0.12), transparent 60%),
    #fff6f2;
  box-shadow: 0 20px 40px -28px rgba(180, 67, 47, 0.55);
  animation: rise 0.55s var(--ease-out) both;
}

.emergency__tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: var(--r-pill);
  background: rgba(180, 67, 47, 0.12);
  color: var(--c-danger);
  font-size: 11px;
  letter-spacing: 0.12em;
}

.emergency__reason {
  margin-top: 12px;
  font-size: 15px;
  font-weight: 600;
  color: #7d2c1d;
}

.emergency__advice {
  margin-top: 6px;
  font-size: 13.5px;
  line-height: 1.75;
  color: #8a4030;
}

.emergency__dept {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed rgba(180, 67, 47, 0.25);
  font-size: 12.5px;
  color: #93503f;
}

.primary-btn.primary-btn--danger {
  background: linear-gradient(135deg, #c2503a, #a53a25);
  box-shadow: 0 2px 4px rgba(165, 58, 37, 0.16), 0 16px 30px -14px rgba(165, 58, 37, 0.55);
  text-decoration: none;
}

.primary-btn.primary-btn--book {
  background: var(--c-surface);
  color: var(--c-primary);
  border: 1px solid var(--c-primary-line);
  box-shadow: var(--shadow-xs);
}

.eyebrow {
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--c-accent-text);
  margin-bottom: 8px;
}

h1 {
  font-size: clamp(28px, 7vw, 34px);
  line-height: 1.22;
  letter-spacing: 0.01em;
}

.lede {
  margin-top: 10px;
  font-size: 14px;
  color: var(--c-muted);
}

.history-note {
  display: inline-flex;
  margin-top: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--c-primary-line);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 11.5px;
  line-height: 1.5;
}

/* ---------- 首选科室 ---------- */
.primary {
  position: relative;
  overflow: hidden;
  padding: 22px 22px 20px;
  border-radius: var(--r-lg);
  color: #fff;
  background:
    radial-gradient(120% 140% at 100% 0%, rgba(255, 255, 255, 0.16), transparent 55%),
    linear-gradient(145deg, #07c160, #06ad56);
  box-shadow: 0 24px 44px -26px rgba(12, 55, 52, 0.75);
  animation: rise 0.6s var(--ease-out) both;
}

.primary__glow {
  position: absolute;
  right: -60px;
  top: -70px;
  width: 190px;
  height: 190px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(191, 106, 52, 0.4), transparent 65%);
  pointer-events: none;
}

.primary__top {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.tag {
  font-size: 11px;
  letter-spacing: 0.16em;
  color: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: var(--r-pill);
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.08);
}

.match {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.82);
}

.primary__name {
  position: relative;
  margin: 14px 0 16px;
  font-size: 34px;
  line-height: 1.2;
  color: #fff;
  letter-spacing: 0.02em;
}

.meter {
  position: relative;
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  overflow: hidden;
}

.meter i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #95ec69, #07c160);
  animation: grow 0.9s var(--ease-out) 0.15s both;
  transform-origin: left;
}

.primary__hint {
  position: relative;
  margin-top: 12px;
  font-size: 11.5px;
  line-height: 1.65;
  color: rgba(255, 255, 255, 0.72);
}

/* ---------- 其他候选 ---------- */
.others {
  margin-top: 16px;
  padding: 16px 16px 8px;
  border: 1px solid var(--c-line);
  border-radius: 22px;
  background: var(--c-surface);
  box-shadow: var(--shadow-sm);
}

.others__title {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: var(--c-muted);
  margin-bottom: 6px;
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.item {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr) 64px 38px;
  align-items: center;
  gap: 10px;
  padding: 11px 0;
  border-bottom: 1px solid var(--c-line-soft);
}

.item:last-child {
  border-bottom: 0;
}

.rank {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: var(--c-surface-soft);
  border: 1px solid var(--c-line-soft);
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--c-muted);
}

.item__name {
  font-size: 15px;
  color: var(--c-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item__meter {
  height: 4px;
  border-radius: 999px;
  background: var(--c-surface-soft);
  overflow: hidden;
}

.item__meter i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--c-primary-line);
}

.item__num {
  text-align: right;
  font-size: 12px;
  color: var(--c-muted);
}

/* ---------- 免责声明 ---------- */
.disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 18px;
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

/* ---------- 操作 ---------- */
.actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 22px;
}

.primary-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 0;
  border-radius: var(--r-pill);
  padding: 16px;
  background: linear-gradient(135deg, #07c160, #06ad56);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  box-shadow: var(--shadow-accent);
  transition: transform var(--dur-fast) var(--ease-out), filter var(--dur-fast) var(--ease-out);
}

.primary-btn svg {
  width: 18px;
  height: 18px;
  transition: transform var(--dur) var(--ease-out);
}

.primary-btn:hover {
  transform: translateY(-1px);
  filter: brightness(1.03);
}

.primary-btn:hover svg {
  transform: translateX(3px);
}

.ghost-btn {
  border: 1px solid var(--c-line);
  border-radius: var(--r-pill);
  padding: 14px;
  background: transparent;
  color: var(--c-primary);
  font-size: 14px;
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

@keyframes shimmer {
  from {
    background-position: 200% 0;
  }
  to {
    background-position: -200% 0;
  }
}

@keyframes grow {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
