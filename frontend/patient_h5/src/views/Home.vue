<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useSessionStore } from '@/stores/session'
import { getProfile, type PatientProfile } from '@/api/patient'
import MiniNav from '@/components/MiniNav.vue'
import MiniTabBar from '@/components/MiniTabBar.vue'

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
const initial = computed(() => (profile.value?.account || store.account || '患').slice(0, 1))

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
  <div class="m-page">
    <MiniNav title="智能导诊">
      <template #right>
        <router-link class="m-nav-link" to="/profile">我的</router-link>
      </template>
    </MiniNav>

    <main class="m-main">
      <section class="m-hello">
        <div class="m-hello__text">
          <p>AI 预问诊</p>
          <h2>你好，{{ profile?.account || store.account || '患者' }}</h2>
          <span>哪里不舒服？描述症状，AI 会像医生一样逐层追问。</span>
        </div>
        <span class="m-avatar" aria-hidden="true">{{ initial }}</span>
      </section>

      <section class="m-card">
        <div class="m-card__head">
          <h3>描述不适</h3>
          <span>必填</span>
        </div>

        <div class="m-textarea" :class="{ 'is-focus': focused, 'is-shake': shaking }">
          <label class="sr-only" for="complaint">症状描述</label>
          <textarea
            id="complaint"
            ref="textareaEl"
            v-model="complaint"
            :maxlength="LIMIT"
            rows="4"
            placeholder="例如：肚子疼三天了，有点拉肚子"
            @focus="focused = true"
            @blur="focused = false"
          />
          <div class="m-textarea__foot">
            <span>描述越具体，判断越准确</span>
            <span class="tnum" :class="{ 'is-near': nearLimit }">{{ count }}/{{ LIMIT }}</span>
          </div>
        </div>

        <div class="m-chips">
          <span>常用症状</span>
          <button
            v-for="c in chips"
            :key="c.label"
            type="button"
            class="m-chip"
            @click="fillChip(c)"
          >
            {{ c.label }}
          </button>
        </div>

        <label class="m-consent">
          <input v-model="consent" type="checkbox" />
          <span>允许接诊医生调阅我的历史预问诊病历</span>
        </label>

        <button class="m-btn" type="button" :disabled="loading" @click="start">
          <span v-if="!loading">开始问诊</span>
          <span v-else>正在准备…</span>
        </button>
      </section>

      <section class="m-services">
        <router-link to="/profile" class="m-service">
          <span class="m-service__icon m-service__icon--green">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <rect x="4" y="5" width="16" height="15" rx="3" stroke="currentColor" stroke-width="1.7" />
              <path d="M8 3v4M16 3v4M4 10h16M9 14h6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
            </svg>
          </span>
          <span class="m-service__text"><b>预约记录</b><em>查看挂号与就诊时间</em></span>
          <span class="m-service__arrow">›</span>
        </router-link>
        <router-link to="/profile" class="m-service">
          <span class="m-service__icon m-service__icon--blue">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M6 3h9l3 3v15H6z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
              <path d="M14 3v4h4M9 12h6M9 16h4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
            </svg>
          </span>
          <span class="m-service__text"><b>历史病历</b><em>查看既往预问诊记录</em></span>
          <span class="m-service__arrow">›</span>
        </router-link>
        <router-link to="/profile" class="m-service">
          <span class="m-service__icon m-service__icon--orange">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="8" r="3.5" stroke="currentColor" stroke-width="1.7" />
              <path d="M5 20c0-3.6 3.2-5.5 7-5.5s7 1.9 7 5.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
            </svg>
          </span>
          <span class="m-service__text"><b>个人资料</b><em>年龄、性别与账号信息</em></span>
          <span class="m-service__arrow">›</span>
        </router-link>
      </section>

      <p class="m-tip">
        本系统仅提供分诊建议，不构成医学诊断。急危重症请立即拨打
        <a href="tel:120">120</a>。
      </p>
    </main>

    <MiniTabBar />
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
  color: var(--c-surface);
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
  background: var(--c-surface);
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
  color: var(--c-surface);
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
  background: var(--c-surface);
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
  color: var(--c-surface);
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
  border-top-color: var(--c-surface);
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
.m-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--c-bg);
  padding-bottom: calc(72px + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

.m-nav-link {
  font-size: 13px;
  color: var(--c-primary);
  text-decoration: none;
  padding: 6px;
}

.m-main {
  width: 100%;
  max-width: 560px;
  margin: 0 auto;
  padding: 14px 14px 24px;
  box-sizing: border-box;
}

.m-hello {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 4px 16px;
}

.m-hello__text {
  flex: 1;
  min-width: 0;
}

.m-hello__text p {
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--c-accent-text);
}

.m-hello__text h2 {
  margin-top: 3px;
  font-size: 22px;
  line-height: 1.3;
  color: var(--c-ink);
}

.m-hello__text span {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--c-muted);
}

.m-avatar {
  width: 46px;
  height: 46px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 18px;
  font-weight: 600;
}

.m-card {
  padding: 16px;
  border-radius: 12px;
  background: var(--c-surface);
}

.m-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.m-card__head h3 {
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 600;
  color: var(--c-ink);
}

.m-card__head span {
  padding: 2px 7px;
  border-radius: 4px;
  background: var(--c-line-soft);
  color: var(--c-faint);
  font-size: 10px;
}

.m-textarea {
  padding: 12px;
  border-radius: 8px;
  background: var(--c-surface-soft);
  border: 1px solid transparent;
  transition: border-color 0.2s ease;
}

.m-textarea.is-focus {
  border-color: var(--c-primary);
  background: var(--c-surface);
}

.m-textarea.is-shake {
  animation: m-shake 0.4s ease;
}

.m-textarea textarea {
  width: 100%;
  min-height: 104px;
  padding: 0;
  border: 0;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--c-ink);
  font-family: var(--font-body);
  font-size: 15px;
  line-height: 1.7;
}

.m-textarea__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 8px;
  color: var(--c-faint);
  font-size: 10.5px;
}

.m-textarea__foot .is-near {
  color: #fa5151;
}

.m-chips {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 12px;
}

.m-chips > span {
  color: var(--c-faint);
  font-size: 11px;
}

.m-chip {
  padding: 5px 10px;
  border: 1px solid var(--c-line);
  border-radius: 999px;
  background: var(--c-surface);
  color: #555;
  font-size: 11px;
}

.m-chip:active {
  background: var(--c-line-soft);
}

.m-consent {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-top: 14px;
  color: var(--c-muted);
  font-size: 11px;
  line-height: 1.6;
}

.m-consent input {
  margin-top: 2px;
  accent-color: var(--c-primary);
}

.m-btn {
  width: 100%;
  height: 44px;
  margin-top: 16px;
  border: 0;
  border-radius: 8px;
  background: var(--c-accent);
  color: var(--c-surface);
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
}

.m-btn:active {
  background: var(--c-accent-strong);
}

.m-btn:disabled {
  opacity: 0.6;
}

.m-services {
  margin-top: 10px;
  border-radius: 12px;
  background: var(--c-surface);
  overflow: hidden;
}

.m-service {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 13px 14px;
  color: inherit;
  text-decoration: none;
  border-bottom: 1px solid var(--c-line-soft);
}

.m-service:last-child {
  border-bottom: 0;
}

.m-service:active {
  background: var(--c-surface-soft);
}

.m-service__icon {
  width: 32px;
  height: 32px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 8px;
}

.m-service__icon svg {
  width: 18px;
  height: 18px;
}

.m-service__icon--green {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

.m-service__icon--blue {
  background: #e8f1ff;
  color: #3b82f6;
}

.m-service__icon--orange {
  background: var(--c-accent-soft);
  color: var(--c-accent-strong);
}

.m-service__text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.m-service__text b {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--c-ink);
}

.m-service__text em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--c-faint);
}

.m-service__arrow {
  color: var(--c-faint);
  font-size: 20px;
}

.m-tip {
  margin-top: 16px;
  padding: 0 4px;
  text-align: center;
  color: var(--c-faint);
  font-size: 10px;
  line-height: 1.7;
}

.m-tip a {
  color: var(--c-primary);
  text-decoration: none;
}

@keyframes m-shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}
</style>
