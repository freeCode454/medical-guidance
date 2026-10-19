const auth = require('../../utils/auth')
const { request } = require('../../utils/api')

const QUICK = [
  { label: '头疼发热', text: '头疼两天了，还有点发烧' },
  { label: '肚子疼', text: '肚子疼三天了，还拉肚子' },
  { label: '咳嗽有痰', text: '咳嗽一周了，有黄痰' },
  { label: '胸闷心慌', text: '胸口发闷，心慌' }
]

Page({
  data: {
    account: '',
    initial: '患',
    profile: null,
    complaint: '',
    quick: QUICK,
    consent: false,
    loading: false,
    focused: false
  },

  onShow() {
    if (!auth.requireLogin()) return
    this.setData({
      account: wx.getStorageSync('mg_account') || '患者',
      initial: (wx.getStorageSync('mg_account') || '患').slice(0, 1)
    })
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
    this.setData({ complaint: e.detail.value })
  },

  onFocus() {
    this.setData({ focused: true })
  },

  onBlur() {
    this.setData({ focused: false })
  },

  onQuick(e) {
    this.setData({ complaint: e.currentTarget.dataset.text })
  },

  toggleConsent() {
    this.setData({ consent: !this.data.consent })
  },

  async onStart() {
    const complaint = this.data.complaint.trim()
    if (!complaint) {
      wx.showToast({ title: '请先描述不舒服的地方', icon: 'none' })
      return
    }
    if (this.data.loading) return

    const profile = this.data.profile || {}
    const gender = profile.gender_label === '男' || profile.gender_label === '女'
      ? profile.gender_label
      : null

    this.setData({ loading: true })
    wx.showLoading({ title: '正在准备问诊', mask: true })
    try {
      if (this.data.consent) {
        try {
          await request('/patient/consents', {
            method: 'POST',
            data: { scope: 'EMR_READ', expire_days: 365 }
          })
        } catch (e) {
          // 授权失败不阻断问诊
        }
      }
      const session = await request('/patient/sessions', {
        method: 'POST',
        data: {
          chief_complaint: complaint,
          input_type: 'TEXT',
          gender,
          age: profile.age == null ? null : profile.age
        }
      })
      wx.hideLoading()
      wx.navigateTo({ url: `/pages/chat/index?sessionId=${session.session_id}` })
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: e.message || '创建问诊失败', icon: 'none', duration: 2500 })
    } finally {
      this.setData({ loading: false })
    }
  }
})
