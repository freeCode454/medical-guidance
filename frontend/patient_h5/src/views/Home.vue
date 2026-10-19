<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useSessionStore } from '@/stores/session'
import { getProfile, type PatientProfile } from '@/api/patient'

const router = useRouter()
const store = useSessionStore()

const complaint = ref('')
const profile = ref<PatientProfile | null>(null)
const loading = ref(false)
const focused = ref(false)
const shaking = ref(false)
const consent = ref(false)
const textareaEl = ref<HTMLTextAreaElement | null>(null)

const LIMIT = 300
const count = computed(() => complaint.value.length)
const nearLimit = computed(() => count.value >= LIMIT - 20)

onMounted(async () => {
  if (!store.hydrateAuth()) {
    router.replace('/login')
    return
  }
  try {
    profile.value = await getProfile()
  } catch {
    // 资料加载失败不阻断问诊；规则层会跳过人群过滤
  }
})

// 常见主诉：点一下填入一句完整描述，降低「不知道怎么写」的门槛
const chips = [
  { label: '头疼发热', text: '头疼两天了，还有点发烧' },
  { label: '肚子疼拉肚子', text: '肚子疼三天了，还有点拉肚子' },
  { label: '咳嗽有痰', text: '咳嗽一周了，有黄痰' },
  { label: '胸闷心慌', text: '胸口发闷，心慌' },
]

function fillChip(chip: (typeof chips)[number]) {
  if (!complaint.value.trim()) {
    complaint.value = chip.text
  } else if (!complaint.value.includes(chip.label)) {
    complaint.value = complaint.value.replace(/[，,。；;\s]+$/, '') + '，' + chip.label
  }
  void nextTick(() => {
    textareaEl.value?.focus()
    const len = textareaEl.value?.value.length ?? 0
    textareaEl.value?.setSelectionRange(len, len)
  })
}

function shake() {
  shaking.value = false
  void nextTick(() => {
    shaking.value = true
    window.setTimeout(() => (shaking.value = false), 480)
  })
}

async function start() {
  const text = complaint.value.trim()
  if (!text) {
    shake()
    textareaEl.value?.focus()
    showToast('请先描述一下您的症状')
    return
  }

  const profileGender =
    profile.value?.gender_label === '男'
      ? '男'
      : profile.value?.gender_label === '女'
        ? '女'
        : undefined
  const ageNum = profile.value?.age ?? undefined

  loading.value = true
  try {
    // 先授权再创建会话：后端创建会话时会读取已授权的既往病历并注入问诊上下文
    if (consent.value) {
      try {
        await store.ensureAuth()
        await store.grantEmrConsent()
      } catch {
        // 授权失败不阻断问诊，患者可在病历页再次授权
      }
    }
    await store.startSession(text, {
      gender: profileGender,
      age: ageNum,
    })
    router.push('/chat')
  } catch (e) {
    showToast((e as Error).message || '启动问诊失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
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
          <em>AI 预问诊 · 患者端</em>
        </span>
      </div>
      <router-link class="account" to="/profile" aria-label="个人中心">
        <span class="account__dot" aria-hidden="true" />
        我的
      </router-link>
    </header>

    <main class="layout">
      <!-- 左：品牌叙事（移动端收起） -->
      <section class="intro">
        <p class="eyebrow">
          <span class="dot" aria-hidden="true" />
          智能导诊 · 预问诊
        </p>
        <h1>哪里不舒服，<br /><span class="hl">先告诉它</span></h1>
        <p class="lede">
          用您自己的话说清症状，它会像医生一样逐层追问，帮您判断该挂哪个科室。
        </p>

        <ol class="steps">
          <li>
            <span class="num">01</span>
            <div class="step-body">
              <b>说清症状</b>
              <p>用平时的说法描述，不必懂医学术语</p>
            </div>
          </li>
          <li>
            <span class="num">02</span>
            <div class="step-body">
              <b>智能追问</b>
              <p>像门诊医生一样，逐层问清关键信息</p>
            </div>
          </li>
          <li>
            <span class="num">03</span>
            <div class="step-body">
              <b>分诊建议</b>
              <p>给出该挂的科室，并整理一份预问诊病历</p>
            </div>
          </li>
        </ol>

        <p class="intro-note">约 3 分钟<span aria-hidden="true">·</span>无需注册<span aria-hidden="true">·</span>可随时结束</p>
      </section>

      <!-- 右：问诊表单 -->
      <section class="panel">
        <form class="card" :class="{ 'is-shake': shaking }" novalidate @submit.prevent="start">
          <div class="card__head">
            <h2>描述您的不适</h2>
            <span class="req">必填</span>
          </div>

          <div class="area" :class="{ 'is-focus': focused }">
            <label class="sr-only" for="complaint">症状描述</label>
            <textarea
              id="complaint"
              ref="textareaEl"
              v-model="complaint"
              class="area__input"
              :maxlength="LIMIT"
              rows="4"
              placeholder="例如：肚子疼三天了，有点拉肚子"
              @focus="focused = true"
              @blur="focused = false"
            />
            <div class="area__foot">
              <span class="hint">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z"
                    stroke="currentColor"
                    stroke-width="1.4"
                    stroke-linejoin="round"
                  />
                  <path d="M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8z" fill="currentColor" opacity=".5" />
                </svg>
                描述越具体，判断越准确
              </span>
              <span class="count tnum" :class="{ 'is-near': nearLimit }" aria-live="polite">
                {{ count }}/{{ LIMIT }}
              </span>
            </div>
          </div>

          <div class="chips">
            <span class="chips__label">试试：</span>
            <button
              v-for="c in chips"
              :key="c.label"
              type="button"
              class="chip"
              @click="fillChip(c)"
            >
              {{ c.label }}
            </button>
          </div>

          <label class="consent">
            <input v-model="consent" type="checkbox" class="consent__box" />
            <span class="consent__text">
              允许接诊医生调阅我的历史预问诊病历
              <em>可随时撤回</em>
            </span>
          </label>

          <button class="cta" type="submit" :disabled="loading" :aria-busy="loading">
            <span v-if="!loading" class="cta__label">
              开始问诊
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M5 12h13M12.5 5.5L19 12l-6.5 6.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
            <span v-else class="cta__label">
              <span class="spinner" aria-hidden="true" />
              正在准备…
            </span>
          </button>

          <p class="cta-note">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 3l7 3v5.2c0 4.6-2.9 7.9-7 9.8-4.1-1.9-7-5.2-7-9.8V6l7-3z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
              <path d="M9 12l2.2 2.2L15.5 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            账号加密保护，信息仅用于本次分诊建议
          </p>
        </form>
      </section>
    </main>

    <footer class="foot">
      本系统仅提供分诊建议，不构成医学诊断。急危重症请立即拨打
      <a href="tel:120">120</a>。
    </footer>
  </div>
</template>

<style scoped>
/* ---------- 页面骨架 ---------- */
.page {
  position: relative;
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  padding: 0 20px;
  background:
    radial-gradient(880px 520px at 8% -12%, rgba(20, 75, 71, 0.1), transparent 62%),
    radial-gradient(720px 480px at 96% 4%, rgba(191, 106, 52, 0.11), transparent 60%),
    var(--c-bg);
}

.topbar {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding: 24px 0 0;
  padding-top: calc(24px + env(safe-area-inset-top));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
}

.brand__mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(145deg, var(--c-primary), var(--c-primary-strong));
  box-shadow: 0 6px 14px -6px rgba(20, 75, 71, 0.55);
}

.brand__mark svg {
  width: 22px;
  height: 22px;
}

.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.brand__text b {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  color: var(--c-primary);
  letter-spacing: 0.04em;
}

.brand__text em {
  font-style: normal;
  font-size: 11px;
  color: var(--c-muted);
  letter-spacing: 0.08em;
}

.account {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 13px;
  border: 1px solid var(--c-primary-line);
  border-radius: var(--r-pill);
  background: var(--c-primary-soft);
  font-size: 11.5px;
  font-weight: 500;
  color: var(--c-primary);
  text-decoration: none;
}

.account__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-primary);
}

/* ---------- 布局 ---------- */
.layout {
  flex: 1;
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding: 28px 0 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

/* 移动端：只留品牌叙事的最小版本，主行动保持在首屏 */
.intro {
  margin: 4px 0 20px;
}

.intro .eyebrow,
.intro .lede,
.intro .steps,
.intro .intro-note {
  display: none;
}

.panel {
  width: 100%;
  max-width: 460px;
  margin: 0 auto;
}

/* ---------- 左栏：品牌叙事 ---------- */
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--c-accent-text);
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-accent);
  box-shadow: 0 0 0 4px rgba(191, 106, 52, 0.14);
  animation: breathe 2.6s var(--ease-out) infinite;
}

h1 {
  font-size: 30px;
  line-height: 1.28;
  letter-spacing: 0.01em;
  margin: 14px 0 0;
}

.hl {
  position: relative;
  white-space: nowrap;
}

.hl::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0.1em;
  height: 0.16em;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(191, 106, 52, 0.42), rgba(191, 106, 52, 0.12));
}

.lede {
  font-size: 16px;
  line-height: 1.9;
  color: var(--c-ink-soft);
  max-width: 27em;
}

.steps {
  list-style: none;
  margin: 40px 0 0;
  padding: 0;
  display: grid;
  gap: 20px;
}

.steps li {
  position: relative;
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 14px;
  align-items: start;
}

.steps li:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 16.5px;
  top: 38px;
  bottom: -22px;
  width: 1px;
  background: linear-gradient(var(--c-line), transparent);
}

.num {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid var(--c-primary-line);
  border-radius: 50%;
  background: rgba(227, 237, 233, 0.7);
  color: var(--c-primary);
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.04em;
}

.step-body b {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: var(--c-ink);
  margin-bottom: 2px;
}

.step-body p {
  font-size: 13px;
  line-height: 1.65;
  color: var(--c-muted);
}

.intro-note {
  margin-top: 36px;
  font-size: 12px;
  color: var(--c-muted);
  letter-spacing: 0.02em;
}

.intro-note span {
  margin: 0 8px;
  color: var(--c-line);
}

/* ---------- 表单卡片 ---------- */
.card {
  position: relative;
  background: var(--c-surface);
  border: 1px solid rgba(230, 221, 205, 0.9);
  border-radius: var(--r-lg);
  padding: 24px 22px 20px;
  box-shadow: var(--shadow-lg);
}

.card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card__head h2 {
  font-size: 18px;
  letter-spacing: 0.04em;
}

.req {
  font-size: 11px;
  color: var(--c-muted);
  background: var(--c-surface-soft);
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-pill);
  padding: 3px 9px;
  letter-spacing: 0.06em;
}

.area {
  margin-top: 14px;
  background: var(--c-surface-soft);
  border: 1px solid var(--c-line);
  border-radius: 18px;
  padding: 14px 15px 9px;
  transition: border-color var(--dur) var(--ease-out), box-shadow var(--dur) var(--ease-out),
    background var(--dur) var(--ease-out);
}

.area.is-focus {
  background: #fff;
  border-color: var(--c-primary-line);
  box-shadow: var(--ring);
}

.area__input {
  display: block;
  width: 100%;
  min-height: 124px;
  border: 0;
  padding: 0;
  background: transparent;
  resize: none;
  outline: none;
  font-size: 16px;
  line-height: 1.75;
  color: var(--c-ink);
}

.area__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 6px;
}

.hint {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  color: var(--c-muted);
}

.hint svg {
  width: 14px;
  height: 14px;
  color: var(--c-accent);
  flex: none;
}

.count {
  font-size: 11.5px;
  color: var(--c-muted);
}

.count.is-near {
  color: var(--c-accent-text);
}

/* ---------- 快捷描述 ---------- */
.chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  margin-top: 12px;
}

.chips__label {
  font-size: 12px;
  color: var(--c-muted);
  margin-right: 1px;
}

.chip {
  border: 1px solid var(--c-line);
  background: var(--c-surface);
  color: var(--c-ink-soft);
  border-radius: var(--r-pill);
  padding: 5px 11px;
  font-size: 12.5px;
  line-height: 1.5;
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out);
}

.chip:hover {
  border-color: var(--c-primary-line);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  transform: translateY(-1px);
}

.chip:active {
  transform: translateY(0);
}

/* ---------- 性别 / 年龄 ---------- */
.meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 18px;
}

.meta__label {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  color: var(--c-muted);
  letter-spacing: 0.04em;
}

.meta__label em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--c-faint);
}

.seg {
  margin-top: 7px;
  display: flex;
  gap: 3px;
  padding: 4px;
  background: var(--c-surface-soft);
  border: 1px solid var(--c-line);
  border-radius: 14px;
}

.seg__btn {
  flex: 1;
  border: 0;
  background: transparent;
  border-radius: 10px;
  padding: 7px 0;
  font-size: 14px;
  color: var(--c-ink-soft);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
}

.seg__btn:hover {
  color: var(--c-primary);
}

.seg__btn.is-on {
  background: var(--c-primary);
  color: #fff;
  box-shadow: 0 4px 10px -4px rgba(20, 75, 71, 0.55);
}

.age {
  position: relative;
  margin-top: 7px;
}

.age__input {
  width: 100%;
  border: 1px solid var(--c-line);
  border-radius: 14px;
  background: var(--c-surface-soft);
  padding: 10px 38px 10px 13px;
  font-size: 14px;
  outline: none;
  transition: border-color var(--dur-fast) var(--ease-out), box-shadow var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
  appearance: textfield;
  -moz-appearance: textfield;
}

.age__input::-webkit-outer-spin-button,
.age__input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.age__input:focus {
  border-color: var(--c-primary-line);
  background: #fff;
  box-shadow: var(--ring);
}

.age__unit {
  position: absolute;
  right: 13px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: var(--c-faint);
  pointer-events: none;
}

/* ---------- 授权 ---------- */
.consent {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 14px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--c-muted);
  cursor: pointer;
}

.consent__box {
  flex: none;
  width: 15px;
  height: 15px;
  margin: 1px 0 0;
  accent-color: var(--c-primary);
  cursor: pointer;
}

.consent__text em {
  font-style: normal;
  color: var(--c-faint);
  margin-left: 4px;
}

/* ---------- 主行动 ---------- */
.cta {
  position: relative;
  overflow: hidden;
  width: 100%;
  margin-top: 22px;
  border: 0;
  border-radius: var(--r-pill);
  padding: 16px 20px;
  background: linear-gradient(135deg, #c9763c, #b15d2b);
  color: #fff;
  font-size: 16.5px;
  font-weight: 600;
  letter-spacing: 0.08em;
  cursor: pointer;
  box-shadow: var(--shadow-accent);
  transition: transform var(--dur-fast) var(--ease-out), box-shadow var(--dur) var(--ease-out),
    filter var(--dur-fast) var(--ease-out);
}

.cta::after {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 50%;
  background: linear-gradient(rgba(255, 255, 255, 0.16), transparent);
  pointer-events: none;
}

.cta:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.03);
  box-shadow: 0 4px 8px rgba(165, 87, 38, 0.16), 0 22px 38px -16px rgba(191, 106, 52, 0.6);
}

.cta:active:not(:disabled) {
  transform: translateY(0) scale(0.995);
}

.cta:disabled {
  cursor: progress;
  filter: saturate(0.75);
  box-shadow: none;
  opacity: 0.85;
}

.cta__label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.cta__label svg {
  width: 18px;
  height: 18px;
  transition: transform var(--dur) var(--ease-out);
}

.cta:hover:not(:disabled) .cta__label svg {
  transform: translateX(3px);
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.cta-note {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 11px;
  font-size: 11.5px;
  color: var(--c-muted);
}

.cta-note svg {
  width: 14px;
  height: 14px;
  color: var(--c-primary);
  opacity: 0.7;
}

/* ---------- 页脚 ---------- */
.foot {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding: 4px 0 26px;
  padding-bottom: calc(26px + env(safe-area-inset-bottom));
  text-align: center;
  font-size: 11.5px;
  line-height: 1.8;
  color: var(--c-muted);
}

.foot a {
  color: var(--c-accent-text);
  text-decoration: none;
  border-bottom: 1px dotted rgba(191, 106, 52, 0.5);
  padding-bottom: 1px;
}

/* ---------- 动效 ---------- */
@keyframes breathe {
  0%,
  100% {
    box-shadow: 0 0 0 3px rgba(191, 106, 52, 0.12);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(191, 106, 52, 0.04);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes shake {
  0%,
  100% {
    transform: translateX(0);
  }
  20% {
    transform: translateX(-6px);
  }
  40% {
    transform: translateX(5px);
  }
  60% {
    transform: translateX(-3px);
  }
  80% {
    transform: translateX(2px);
  }
}

.card.is-shake {
  animation: shake 0.42s var(--ease-out);
  border-color: rgba(180, 67, 47, 0.35);
}

/* ---------- 桌面 ---------- */
@media (min-width: 980px) {
  .page {
    padding: 0 48px;
  }

  .topbar {
    padding-top: 30px;
  }

  .layout {
    display: flex;
    flex-direction: column;
    max-width: 720px;
    gap: 20px;
    align-items: stretch;
    padding: 18px 0 24px;
  }

  .intro {
    display: block;
    max-width: 620px;
    margin: 0 auto;
    text-align: center;
  }

  .intro .eyebrow {
    display: inline-flex;
    justify-content: center;
  }

  .intro .lede {
    display: block;
    max-width: 500px;
    margin-left: auto;
    margin-right: auto;
  }

  .intro .steps,
  .intro .intro-note {
    display: none;
  }

  h1 {
    font-size: clamp(38px, 5.2vw, 56px);
    line-height: 1.22;
    margin: 16px 0 12px;
  }

  h1 br {
    display: block;
  }

  .panel {
    max-width: 560px;
    margin: 0 auto;
    animation: rise 0.75s var(--ease-out) 0.12s both;
  }

  .card {
    padding: 28px 26px 22px;
  }

  .area__input {
    min-height: 132px;
  }

  .foot {
    padding-bottom: 30px;
  }

  /* 入场：左栏逐条、右卡整体 */
  .intro > * {
    animation: rise 0.75s var(--ease-out) both;
  }

  .intro > :nth-child(1) {
    animation-delay: 0.04s;
  }
  .intro > :nth-child(2) {
    animation-delay: 0.1s;
  }
  .intro > :nth-child(3) {
    animation-delay: 0.16s;
  }
  .intro > :nth-child(4) {
    animation-delay: 0.22s;
  }
  .intro > :nth-child(5) {
    animation-delay: 0.3s;
  }
}
</style>
