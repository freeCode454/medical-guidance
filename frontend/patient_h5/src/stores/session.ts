// 会话状态：匿名 token、当前会话、消息列表、问诊状态
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/patient'
import { setToken } from '@/api/client'

function genDeviceId(): string {
  let id = localStorage.getItem('mg_device_id')
  if (!id) {
    id = 'dev_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
    localStorage.setItem('mg_device_id', id)
  }
  return id
}

export const useSessionStore = defineStore('session', () => {
  const deviceId = ref(genDeviceId())
  const patientId = ref('')
  const sessionId = ref('')
  const sessionNo = ref('')
  const messages = ref<api.ChatMessage[]>([])
  const route = ref<string | null>(null)
  const triage = ref<api.TriageResult | null>(null)
  const phase = ref<'idle' | 'chatting' | 'done'>('idle') // 空闲 / 问诊中 / 已出结论

  // 初始化匿名身份
  async function ensureAuth() {
    const d = await api.createAnonymousSession(deviceId.value)
    setToken(d.access_token)
    patientId.value = d.patient_id
  }

  // 开始一次问诊
  async function startSession(
    chiefComplaint: string,
    extra?: { gender?: '男' | '女'; age?: number },
  ) {
    await ensureAuth()
    const s = await api.createSession(chiefComplaint, deviceId.value, extra)
    sessionId.value = s.session_id
    sessionNo.value = s.session_no
    route.value = null
    triage.value = null
    messages.value = []
    phase.value = 'chatting'
  }

  // 发送患者消息（本地先上屏，后端异步处理）
  async function send(content: string) {
    messages.value.push({
      message_id: 'local_' + Date.now(),
      seq_no: messages.value.length + 1,
      role: 'PATIENT',
      content,
      msg_type: 'TEXT',
      extra: {},
      send_time: new Date().toISOString(),
    })
    await api.sendMessage(sessionId.value, content)
  }

  // 拉取完整消息（断线重建）
  async function refreshMessages() {
    const d = await api.listMessages(sessionId.value)
    messages.value = d.items
  }

  // AI 追问上屏（WS node_complete 触发）
  function appendAi(content: string) {
    messages.value.push({
      message_id: 'ai_' + Date.now(),
      seq_no: messages.value.length + 1,
      role: 'AI',
      content,
      msg_type: 'TEXT',
      extra: {},
      send_time: new Date().toISOString(),
    })
  }

  // 分诊完成
  async function loadTriage() {
    triage.value = await api.getTriage(sessionId.value)
    route.value = triage.value.route
    phase.value = 'done'
  }

  return {
    deviceId, patientId, sessionId, sessionNo, messages, route, triage, phase,
    ensureAuth, startSession, send, refreshMessages, appendAi, loadTriage,
  }
})
