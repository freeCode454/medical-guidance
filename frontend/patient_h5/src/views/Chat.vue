<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { useSessionStore } from '@/stores/session'
import { connectWs } from '@/api/ws'

const router = useRouter()
const store = useSessionStore()
const input = ref('')
const typing = ref(false)
const focused = ref(false)
const scrollEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)
let closeWs: (() => void) | null = null

const answered = computed(
  () => store.messages.filter((m) => m.role === 'PATIENT').length,
)

function scrollBottom() {
  void nextTick(() => {
    if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
  })
}

function resizeInput() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 96) + 'px'
}

watch(input, () => void nextTick(resizeInput))
watch(() => store.messages.length, scrollBottom)
watch(typing, scrollBottom)

onMounted(async () => {
  // 先拉历史消息（可能已有 AI 追问），再连 WS 收后续事件
  try {
    await store.refreshMessages()
    scrollBottom()
  } catch {
    /* 忽略 */
  }

  closeWs = connectWs(store.sessionId, {
    // 首次连接与断线重连成功都会触发：补拉错过的消息（幂等）
    onConnected() {
      void store.refreshMessages().then(scrollBottom)
    },
    onNodeComplete(node, output) {
      if (node === 'INQUIRY' && output.content) {
        // AI 追问上屏
        typing.value = false
        store.appendAi(output.content)
        scrollBottom()
      }
    },
    onTaskComplete() {
      typing.value = false
      router.push('/result')
    },
    onEmergency(data) {
      typing.value = false
      showToast(data.message || '请立即前往急诊')
    },
    onServerError(_code, message) {
      typing.value = false
      showToast(message || '消息处理失败，请重试')
    },
    onError() {
      typing.value = false
    },
  })
})

onUnmounted(() => closeWs?.())

async function send() {
  const text = input.value.trim()
  if (!text || typing.value) return
  input.value = ''
  await nextTick(resizeInput)
  try {
    await store.send(text)
    typing.value = true
    scrollBottom()
  } catch (e) {
    typing.value = false
    showToast((e as Error).message || '发送失败')
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter' || e.shiftKey) return
  // 中文输入法组词中按 Enter 是选词，不能当作发送
  if (e.isComposing || e.keyCode === 229) return
  e.preventDefault()
  void send()
}

async function exit() {
  try {
    await showConfirmDialog({
      title: '退出本次问诊？',
      message: '对话会保留，但需要回到首页重新开始才能继续。',
      confirmButtonText: '退出',
      cancelButtonText: '继续问诊',
    })
    router.push('/')
  } catch {
    /* 用户选择继续问诊 */
  }
}
</script>

<template>
  <div class="chat">
    <header class="head">
      <button class="back" type="button" aria-label="返回首页" @click="exit">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M14.5 6l-6 6 6 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>

      <div class="identity">
        <span class="avatar" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M3 12h4l2.4-6 4.2 12 2.4-6H21" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <span class="identity__text">
          <b>智能预问诊</b>
          <span class="status"><i aria-hidden="true" />问诊中 · 已答 {{ answered }} 问</span>
        </span>
      </div>

      <span class="secure">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="5" y="10" width="14" height="10" rx="3" stroke="currentColor" stroke-width="1.6" />
          <path d="M8.5 10V7.5a3.5 3.5 0 017 0V10" stroke="currentColor" stroke-width="1.6" />
        </svg>
        加密
      </span>
    </header>

    <main ref="scrollEl" class="messages">
      <p class="notice">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" />
          <path d="M12 11v6M12 7.6v.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        </svg>
        请尽量具体地描述感受，比如「胀痛」「一阵一阵的」。AI 会像医生一样逐层追问。
      </p>

      <div
        v-for="m in store.messages"
        :key="m.message_id"
        class="row"
        :class="m.role === 'PATIENT' ? 'row--me' : 'row--ai'"
      >
        <span v-if="m.role !== 'PATIENT'" class="bubble-avatar" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M3 12h4l2.4-6 4.2 12 2.4-6H21" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <div class="bubble">{{ m.content }}</div>
      </div>

      <div v-if="typing" class="row row--ai">
        <span class="bubble-avatar" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M3 12h4l2.4-6 4.2 12 2.4-6H21" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <div class="bubble bubble--typing" role="status">
          <span class="dots" aria-hidden="true"><i /><i /><i /></span>
          正在整理追问…
        </div>
      </div>
    </main>

    <footer class="composer">
      <form class="composer__inner" @submit.prevent="send">
        <div class="field" :class="{ 'is-focus': focused }">
          <label class="sr-only" for="reply">回答</label>
          <textarea
            id="reply"
            ref="inputEl"
            v-model="input"
            rows="1"
            placeholder="说说您的感受…"
            @focus="focused = true"
            @blur="focused = false"
            @keydown="onKeydown"
          />
        </div>
        <button class="send" type="submit" :disabled="!input.trim() || typing" aria-label="发送">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 19V6M6.5 11.5L12 6l5.5 5.5" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </form>
      <p class="composer__hint">Enter 发送 · Shift + Enter 换行</p>
    </footer>
  </div>
</template>

<style scoped>
.chat {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  max-width: 760px;
  margin: 0 auto;
  background: transparent;
}

/* ---------- 顶部 ---------- */
.head {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 12px 14px;
  padding-top: calc(12px + env(safe-area-inset-top));
  background: rgba(255, 253, 249, 0.86);
  backdrop-filter: blur(14px) saturate(1.1);
  border-bottom: 1px solid var(--c-line-soft);
}

.back {
  flex: none;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid var(--c-line);
  border-radius: 11px;
  background: var(--c-surface);
  color: var(--c-primary);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out);
}

.back:hover {
  background: var(--c-primary-soft);
  border-color: var(--c-primary-line);
}

.back svg {
  width: 18px;
  height: 18px;
}

.identity {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.avatar {
  flex: none;
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(145deg, var(--c-primary), var(--c-primary-strong));
  box-shadow: 0 6px 14px -7px rgba(20, 75, 71, 0.6);
}

.avatar svg {
  width: 20px;
  height: 20px;
}

.identity__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.identity__text b {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--c-primary);
  line-height: 1.2;
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--c-muted);
  white-space: nowrap;
}

.status i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3f8a6f;
  box-shadow: 0 0 0 3px rgba(63, 138, 111, 0.14);
  animation: breathe 2.6s var(--ease-out) infinite;
}

.secure {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex: none;
  font-size: 11px;
  color: var(--c-muted);
}

.secure svg {
  width: 13px;
  height: 13px;
  color: var(--c-primary);
  opacity: 0.7;
}

/* ---------- 消息区 ---------- */
.messages {
  flex: 1;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 18px 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  scrollbar-width: thin;
  scrollbar-color: var(--c-line) transparent;
}

.notice {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 2px;
  padding: 10px 12px;
  border: 1px solid rgba(201, 219, 213, 0.75);
  border-radius: 14px;
  background: rgba(227, 237, 233, 0.55);
  font-size: 12px;
  line-height: 1.7;
  color: var(--c-ink-soft);
}

.notice svg {
  flex: none;
  width: 15px;
  height: 15px;
  margin-top: 2px;
  color: var(--c-primary);
  opacity: 0.75;
}

.row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  max-width: 100%;
  animation: rise 0.36s var(--ease-out) both;
}

.row--me {
  justify-content: flex-end;
}

.bubble-avatar {
  flex: none;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  margin-bottom: 0;
  border: 1px solid rgba(201, 219, 213, 0.9);
  border-radius: 10px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  margin-top: 2px;
}

.bubble-avatar svg {
  width: 16px;
  height: 16px;
}

.bubble {
  max-width: 78%;
  padding: 11px 14px;
  border-radius: 17px;
  font-size: 15px;
  line-height: 1.72;
  white-space: pre-wrap;
  word-break: break-word;
}

.row--ai .bubble {
  background: var(--c-surface);
  border: 1px solid var(--c-line-soft);
  border-bottom-left-radius: 5px;
  box-shadow: var(--shadow-xs);
  color: var(--c-ink);
}

.row--me .bubble {
  background: linear-gradient(135deg, #1a5a55, var(--c-primary));
  border-bottom-right-radius: 5px;
  color: #fff;
  box-shadow: 0 10px 20px -12px rgba(20, 75, 71, 0.6);
}

.bubble--typing {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 12px 14px;
  font-size: 12px;
  color: var(--c-muted);
}

.dots {
  display: inline-flex;
  gap: 4px;
}

.dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-muted);
  animation: blink 1.2s infinite;
}

.dots i:nth-child(2) {
  animation-delay: 0.18s;
}

.dots i:nth-child(3) {
  animation-delay: 0.36s;
}

/* ---------- 输入区 ---------- */
.composer {
  position: sticky;
  bottom: 0;
  padding: 10px 14px calc(9px + env(safe-area-inset-bottom));
  background: rgba(255, 253, 249, 0.92);
  backdrop-filter: blur(14px);
  border-top: 1px solid var(--c-line-soft);
}

.composer__inner {
  display: flex;
  align-items: flex-end;
  gap: 9px;
}

.field {
  flex: 1;
  padding: 9px 14px;
  border: 1px solid var(--c-line);
  border-radius: 22px;
  background: var(--c-surface-soft);
  transition: border-color var(--dur-fast) var(--ease-out), box-shadow var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
}

.field.is-focus {
  border-color: var(--c-primary-line);
  background: #fff;
  box-shadow: var(--ring);
}

.field textarea {
  display: block;
  width: 100%;
  max-height: 96px;
  border: 0;
  padding: 0;
  background: transparent;
  outline: none;
  resize: none;
  font-size: 15px;
  line-height: 1.65;
  color: var(--c-ink);
}

.send {
  flex: none;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, #c9763c, #b15d2b);
  color: #fff;
  cursor: pointer;
  box-shadow: var(--shadow-accent);
  transition: transform var(--dur-fast) var(--ease-out), opacity var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
}

.send svg {
  width: 20px;
  height: 20px;
}

.send:hover:not(:disabled) {
  transform: translateY(-1px);
}

.send:active:not(:disabled) {
  transform: scale(0.96);
}

.send:disabled {
  cursor: not-allowed;
  opacity: 0.42;
  box-shadow: none;
}

.composer__hint {
  display: none;
  margin-top: 7px;
  text-align: center;
  font-size: 11px;
  color: var(--c-muted);
}

@keyframes blink {
  0%,
  60%,
  100% {
    opacity: 0.25;
  }
  30% {
    opacity: 1;
  }
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes breathe {
  0%,
  100% {
    box-shadow: 0 0 0 3px rgba(63, 138, 111, 0.14);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(63, 138, 111, 0.04);
  }
}

@media (min-width: 768px) {
  .chat {
    border-left: 1px solid var(--c-line-soft);
    border-right: 1px solid var(--c-line-soft);
    box-shadow: 0 0 60px -30px rgba(29, 42, 40, 0.25);
  }

  .messages {
    padding: 24px 26px 14px;
  }

  .composer {
    padding-left: 26px;
    padding-right: 26px;
  }

  .composer__hint {
    display: block;
  }
}
</style>
