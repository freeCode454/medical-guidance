const auth = require('../../utils/auth')
const { request } = require('../../utils/api')

Page({
  data: {
    account: '',
    initial: '患',
    profile: null,
    input: '',
    loading: false
  },

  onShow() {
    if (!auth.requireLogin()) return
    const account = wx.getStorageSync('mg_account') || '患者'
    this.setData({ account, initial: account.slice(0, 1) })
    this.loadProfile()
  },

  async loadProfile() {
    try {
      const profile = await auth.getProfile()
      if (profile && profile.account) {
        this.setData({
          profile,
          account: profile.account,
          initial: profile.account.slice(0, 1)
        })
      }
    } catch (e) {
      // 资料加载失败不阻断问诊
    }
  },

  onInput(e) {
    this.setData({ input: e.detail.value })
  },

  async onSend() {
    const content = String(this.data.input || '').trim()
    if (!content || this.data.loading) return
    const profile = this.data.profile || {}
    const gender = profile.gender_label === '男' || profile.gender_label === '女'
      ? profile.gender_label
      : null

    this.setData({ loading: true, input: '' })
    try {
      const session = await request('/patient/sessions', {
        method: 'POST',
        data: {
          chief_complaint: content,
          input_type: 'TEXT',
          gender,
          age: profile.age == null ? null : profile.age
        }
      })
      wx.navigateTo({ url: `/pages/chat/index?sessionId=${session.session_id}` })
    } catch (e) {
      this.setData({ input: content })
      wx.showToast({ title: e.message || '发起问诊失败', icon: 'none', duration: 2500 })
    } finally {
      this.setData({ loading: false })
    }
  }
})
