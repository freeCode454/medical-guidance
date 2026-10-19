Page({
  data: {
    complaint: '',
    genders: ['未知', '男', '女'],
    genderIndex: 0,
    age: '',
    loading: false
  },

  onInput(e) {
    this.setData({ complaint: e.detail.value })
  },

  onAge(e) {
    this.setData({ age: e.detail.value })
  },

  onGender(e) {
    this.setData({ genderIndex: Number(e.detail.value) })
  },

  async onStart() {
    const complaint = this.data.complaint.trim()
    if (!complaint) {
      wx.showToast({ title: '请先描述不适', icon: 'none' })
      return
    }
    const ageNumber = this.data.age ? Number(this.data.age) : null
    if (ageNumber !== null && (!Number.isFinite(ageNumber) || ageNumber < 0 || ageNumber > 120)) {
      wx.showToast({ title: '年龄需在 0~120 之间', icon: 'none' })
      return
    }

    this.setData({ loading: true })
    wx.showLoading({ title: '正在建立问诊', mask: true })
    try {
      const { ensureAuth, getDeviceId } = require('../../utils/auth')
      const { request } = require('../../utils/api')
      await ensureAuth()
      const deviceId = await getDeviceId()
      const gender = this.data.genders[this.data.genderIndex]
      const session = await request('/patient/sessions', {
        method: 'POST',
        data: {
          chief_complaint: complaint,
          device_id: deviceId,
          input_type: 'TEXT',
          gender: gender === '未知' ? null : gender,
          age: ageNumber
        }
      })
      wx.navigateTo({ url: `/pages/chat/index?sessionId=${session.session_id}` })
    } catch (e) {
      wx.showToast({ title: e.message || '创建会话失败', icon: 'none', duration: 3000 })
    } finally {
      wx.hideLoading()
      this.setData({ loading: false })
    }
  }
})
