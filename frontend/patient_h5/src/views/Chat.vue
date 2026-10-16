<script setup lang="ts">
import { onMounted, onUnmounted, ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useSessionStore } from '@/stores/session'
import { connectWs } from '@/api/ws'

const router = useRouter()
const store = useSessionStore()
const input = ref('')
const typing = ref(false)
const scrollEl = ref<HTMLElement | null>(null)
let closeWs: (() => void) | null = null

function scrollBottom() {
  nextTick(() => {
    if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
  })
}

onMounted(async () => {
  // 先拉历史消息（可能已有 AI 追问），再连 WS 收后续事件
  try {
    await store.refreshMessages()
    scrollBottom()
  } catch {
    /* 忽略 */
  }

  closeWs = connectWs(store.sessionId, {
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
  try {
    await store.send(text)
    typing.value = true
    scrollBottom()
  } catch (e) {
    typing.value = false
    showToast((e as Error).message || '发送失败')
  }
}
</script>

<template>
  <div class="chat">
    <header class="bar">
      <span class="title">智能预问诊</span>
      <span class="status">问诊中</span>
    </header>

    <main class="messages" ref="scrollEl">
      <div v-for="m in store.messages" :key="m.message_id" class="msg" :class="m.role === 'PATIENT' ? 'mine' : 'ai'">
        <div class="bubble">{{ m.content }}</div>
      </div>

      <div v-if="typing" class="msg ai">
        <div class="bubble typing"><span class="dot" /><span class="dot" /><span class="dot" /></div>
      </div>
    </main>

    <footer class="input-bar">
      <input
        v-model="input"
        class="input"
        placeholder="描述您的症状…"
        @keyup.enter="send"
      />
      <button class="send" :disabled="!input.trim() || typing" @click="send">发送</button>
    </footer>
  </div>
</template>

<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--c-bg);
}

.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-line);
  position: sticky;
  top: 0;
}

.title {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  color: var(--c-primary);
}

.status {
  font-size: 12px;
  color: var(--c-accent);
  background: rgba(201, 123, 61, 0.1);
  padding: 3px 10px;
  border-radius: 999px;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 16px;
}

.msg {
  margin-bottom: 14px;
  display: flex;
}

.msg.mine {
  justify-content: flex-end;
}

.bubble {
  max-width: 78%;
  padding: 12px 15px;
  border-radius: 16px;
  font-size: 15px;
  line-height: 1.6;
  word-break: break-word;
}

.mine .bubble {
  background: var(--c-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.ai .bubble {
  background: var(--c-surface);
  border: 1px solid var(--c-line);
  border-bottom-left-radius: 4px;
}

.typing {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 14px 16px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-muted);
  animation: blink 1.2s infinite;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
  0%, 60%, 100% { opacity: 0.25; }
  30% { opacity: 1; }
}

.input-bar {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  background: var(--c-surface);
  border-top: 1px solid var(--c-line);
}

.input {
  flex: 1;
  border: 1px solid var(--c-line);
  border-radius: 999px;
  padding: 11px 16px;
  font-size: 15px;
  outline: none;
  background: var(--c-bg);
}

.input:focus {
  border-color: var(--c-primary);
}

.send {
  background: var(--c-accent);
  color: #fff;
  border: none;
  border-radius: 999px;
  padding: 0 22px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.send:disabled {
  opacity: 0.5;
}
</style>
