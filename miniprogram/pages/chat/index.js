const { request } = require('../../utils/api')
const auth = require('../../utils/auth')

const ROLE_LABELS = {
  PATIENT: '我',
  AI: '智能助手',
  DOCTOR: '医生',
  SYSTEM: '系统'
}

Page({
  data: {
    sessionId: '',
    messages: [],
    input: '',
    hasTriage: false,
    status: '',
    rounds: 0,
    loading: true,
    sending: false,
    awaitingReply: false,
    scrollTop: 0
  },

  onLoad(options) {
    if (!auth.requireLogin()) return
    const sessionId = options.sessionId || ''
    this.setData({ sessionId, loading: Boolean(sessionId) })
    if (sessionId) this.loadAll()
  },

  onShow() {
    if (this.data.sessionId) this.startPolling()
  },

  onHide() {
    this.stopPolling()
  },

  onUnload() {
    this.stopPolling()
  },

  startPolling() {
    this.stopPolling()
    this.timer = setInterval(() => this.loadMessages(), 1500)
  },

  stopPolling() {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
  },

  async loadAll() {
    this.setData({ loading: true })
    try {
      const [session, list] = await Promise.all([
        request(`/patient/sessions/${this.data.sessionId}`),
        request(`/patient/sessions/${this.data.sessionId}/messages`)
      ])
      this.apply(session, list.items || [])
    } catch (e) {
      wx.showToast({ title: e.message || '会话加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  async loadMessages() {
    if (this.polling || !this.data.sessionId) return
    this.polling = true
    try {
      const [session, list] = await Promise.all([
        request(`/patient/sessions/${this.data.sessionId}`),
        request(`/patient/sessions/${this.data.sessionId}/messages`)
      ])
      this.apply(session, list.items || [])
    } catch (e) {
      // 轮询失败不打断页面，下一轮继续
    } finally {
      this.polling = false
    }
  },

  apply(session, items) {
    const messages = items.map((m) => ({
      ...m,
      roleLabel: ROLE_LABELS[m.role] || m.role,
      isPatient: m.role === 'PATIENT',
      isAi: m.role !== 'PATIENT'
    }))
    const last = messages.length ? messages[messages.length - 1] : null
    const awaitingReply = Boolean(last && last.isPatient && !session.has_triage)
    this.setData({
      messages,
      hasTriage: !!session.has_triage,
      status: session.status || '',
      rounds: session.inquiry_rounds || 0,
      awaitingReply,
      scrollTop: this.data.scrollTop + 10000
    })
  },

  onInput(e) {
    this.setData({ input: e.detail.value })
  },

  async onSend() {
    await this.sendContent(this.data.input)
  },

  async sendContent(raw) {
    const content = String(raw || '').trim()
    if (!content || this.data.sending) return
    this.setData({ sending: true, awaitingReply: true, input: '' })
    try {
      if (!this.data.sessionId) {
        let profile = null
        try {
          profile = await auth.getProfile()
        } catch (e) {
          // 资料读取失败不阻断首次问诊
        }
        const gender = profile && (profile.gender_label === '男' || profile.gender_label === '女')
          ? profile.gender_label
          : null
        const session = await request('/patient/sessions', {
          method: 'POST',
          data: {
            chief_complaint: content,
            input_type: 'TEXT',
            gender,
            age: profile && profile.age != null ? profile.age : null
          }
        })
        this.setData({ sessionId: session.session_id, loading: true })
        await this.loadAll()
        this.startPolling()
      } else {
        await request(`/patient/sessions/${this.data.sessionId}/messages`, {
          method: 'POST',
          data: { content, msg_type: 'TEXT' }
        })
        await this.loadMessages()
      }
    } catch (e) {
      this.setData({ input: content, awaitingReply: false })
      wx.showToast({ title: e.message || '发送失败', icon: 'none' })
    } finally {
      this.setData({ sending: false })
    }
  },

  onResult() {
    if (!this.data.hasTriage) {
      wx.showToast({ title: '分诊结果还没有生成', icon: 'none' })
      return
    }
    wx.navigateTo({ url: `/pages/result/index?sessionId=${this.data.sessionId}` })
  }
})
