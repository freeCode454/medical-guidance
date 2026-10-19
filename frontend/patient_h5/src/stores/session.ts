// 会话状态：患者账号 token、当前会话、消息列表、问诊状态
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/api/patient'
import { getToken, setToken } from '@/api/client'

// 设备密钥：等价于匿名身份凭证，必须是高熵随机串（服务端只存指纹）。
// 旧版本生成了可猜测的 dev_xxx，检测到长度不足时直接换成新的。
const DEVICE_KEY_MIN_LENGTH = 32

function genDeviceId(): string {
  const existing = localStorage.getItem('mg_device_id')
  if (existing && existing.length >= DEVICE_KEY_MIN_LENGTH) return existing

  const bytes = new Uint8Array(32)
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes)
  } else {
    // 极老浏览器兜底；现代浏览器都会走 getRandomValues
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256)
  }
  const id = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  localStorage.setItem('mg_device_id', id)
  return id
}

export const useSessionStore = defineStore('session', () => {
  const deviceId = ref(genDeviceId())
  const patientId = ref('')
  const account = ref('')
  const sessionId = ref('')
  const sessionNo = ref('')
  const messages = ref<api.ChatMessage[]>([])
  const route = ref<string | null>(null)
  const triage = ref<api.TriageResult | null>(null)
  const phase = ref<'idle' | 'chatting' | 'done'>('idle') // 空闲 / 问诊中 / 已出结论
  const isAuthenticated = computed(() => Boolean(getToken() && patientId.value))

  function saveAuth(d: api.PatientAuth) {
    setToken(d.access_token)
    patientId.value = d.patient_id
    account.value = d.account
    localStorage.setItem('mg_patient_id', d.patient_id)
    localStorage.setItem('mg_patient_account', d.account)
  }

  // 从本地恢复登录态；令牌与患者 ID 必须同时存在
  function hydrateAuth() {
    const token = getToken()
    const pid = localStorage.getItem('mg_patient_id') || ''
    const acc = localStorage.getItem('mg_patient_account') || ''
    if (!token || !pid) {
      if (token && !pid) setToken(null)
      patientId.value = ''
      account.value = ''
      return false
    }
    patientId.value = pid
    account.value = acc
    return true
  }

  async function login(accountValue: string, password: string) {
    const d = await api.patientLogin(accountValue, password)
    saveAuth(d)
  }

  async function register(accountValue: string, password: string) {
    const d = await api.patientRegister(accountValue, password)
    saveAuth(d)
  }

  function logout() {
    setToken(null)
    patientId.value = ''
    account.value = ''
    sessionId.value = ''
    messages.value = []
    triage.value = null
    route.value = null
    phase.value = 'idle'
    localStorage.removeItem('mg_patient_id')
    localStorage.removeItem('mg_patient_account')
  }

  // 登录后才能发起问诊
  async function ensureAuth() {
    if (!hydrateAuth()) throw new Error('请先登录患者账号')
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

  // 病史调阅授权（默认不授权，由患者在首页显式勾选）
  async function grantEmrConsent() {
    await api.grantConsent(sessionId.value || undefined)
  }

  return {
    deviceId, patientId, account, isAuthenticated, sessionId, sessionNo, messages, route, triage, phase,
    hydrateAuth, login, register, logout, ensureAuth,
    startSession, send, refreshMessages, appendAi, loadTriage, grantEmrConsent,
  }
})
