const { request } = require('../../utils/api')

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
    loading: true,
    sending: false,
    scrollId: ''
  },

  onLoad(options) {
    this.setData({ sessionId: options.sessionId || '' })
    this.loadAll()
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
    this.timer = setInterval(() => this.loadMessages(), 2500)
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
    const last = messages.length ? `m${messages.length - 1}` : ''
    this.setData({
      messages,
      hasTriage: !!session.has_triage,
      status: session.status || '',
      scrollId: last
    })
  },

  onInput(e) {
    this.setData({ input: e.detail.value })
  },

  async onSend() {
    const content = this.data.input.trim()
    if (!content || this.data.sending) return
    this.setData({ sending: true, input: '' })
    try {
      await request(`/patient/sessions/${this.data.sessionId}/messages`, {
        method: 'POST',
        data: { content, msg_type: 'TEXT' }
      })
      await this.loadMessages()
    } catch (e) {
      this.setData({ input: content })
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
