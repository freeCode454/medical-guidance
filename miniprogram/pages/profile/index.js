const auth = require('../../utils/auth')
const { request } = require('../../utils/api')

function fmtDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 10).replace(/-/g, '/')
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}/${p(d.getMonth() + 1)}/${p(d.getDate())}`
}

function fmtDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const p = (n) => String(n).padStart(2, '0')
  return `${fmtDate(value)} ${p(d.getHours())}:${p(d.getMinutes())}`
}

Page({
  data: {
    loading: true,
    error: '',
    profile: null,
    appointments: [],
    records: [],
    initial: '患',
    editing: false,
    saving: false,
    genderOptions: ['男', '女'],
    editGenderIndex: 0,
    editAge: '',
    detail: null,
    cancelling: false
  },

  onShow() {
    if (!auth.requireLogin()) return
    this.load()
  },

  async onPullDownRefresh() {
    await this.load()
    wx.stopPullDownRefresh()
  },

  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const [profile, appointments, records] = await Promise.all([
        auth.getProfile(),
        request('/patient/appointments'),
        request('/patient/records?limit=20')
      ])
      const rows = (appointments.items || []).map((item) => ({
        ...item,
        dateText: fmtDate(item.schedule_date),
        isDone: item.status !== 'BOOKED'
      }))
      const recs = (records.items || []).map((item) => ({
        ...item,
        dateText: fmtDate(item.visit_time)
      }))
      this.setData({
        profile,
        appointments: rows,
        records: recs,
        initial: (profile.account || '患').slice(0, 1),
        createdText: fmtDate(profile.created_at),
        ageText: profile.age == null ? '未填写' : `${profile.age} 岁`,
        loading: false
      })
    } catch (e) {
      this.setData({ loading: false, error: e.message || '加载失败' })
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  openEdit() {
    const profile = this.data.profile || {}
    const index = this.data.genderOptions.indexOf(profile.gender_label)
    this.setData({
      editing: true,
      editGenderIndex: index >= 0 ? index : 0,
      editAge: profile.age == null ? '' : String(profile.age)
    })
  },

  closeEdit() {
    this.setData({ editing: false })
  },

  onEditGender(e) {
    this.setData({ editGenderIndex: Number(e.currentTarget.dataset.index) })
  },

  onEditAge(e) {
    this.setData({ editAge: e.detail.value })
  },

  async saveProfile() {
    if (this.data.saving) return
    const ageNumber = Number(this.data.editAge)
    if (this.data.editAge === '' || !Number.isFinite(ageNumber) || ageNumber < 0 || ageNumber > 120) {
      wx.showToast({ title: '请输入 0~120 之间的年龄', icon: 'none' })
      return
    }
    this.setData({ saving: true })
    try {
      const profile = await request('/patient/profile', {
        method: 'PATCH',
        data: {
          gender: this.data.genderOptions[this.data.editGenderIndex],
          age: ageNumber
        }
      })
      this.setData({
        profile,
        ageText: profile.age == null ? '未填写' : `${profile.age} 岁`,
        editing: false
      })
      wx.showToast({ title: '资料已更新', icon: 'none' })
    } catch (e) {
      wx.showToast({ title: e.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },

  onAppointment(e) {
    const id = e.currentTarget.dataset.id
    const item = this.data.appointments.find((a) => a.appointment_id === id)
    if (!item) return
    this.setData({
      detail: {
        ...item,
        createText: fmtDateTime(item.create_time)
      }
    })
  },

  closeDetail() {
    this.setData({ detail: null })
  },

  cancelAppointment() {
    const detail = this.data.detail
    if (!detail || !detail.can_cancel || this.data.cancelling) return
    wx.showModal({
      title: '取消预约',
      content: `取消 ${detail.dateText} ${detail.time_slot} 与 ${detail.doctor_name} 的预约？`,
      confirmText: '确认取消',
      success: async (res) => {
        if (!res.confirm) return
        this.setData({ cancelling: true })
        try {
          await request(`/patient/appointments/${detail.appointment_id}/cancel`, { method: 'POST' })
          this.setData({ detail: null })
          wx.showToast({ title: '已取消预约', icon: 'none' })
          await this.load()
        } catch (err) {
          wx.showToast({ title: err.message || '取消失败', icon: 'none' })
        } finally {
          this.setData({ cancelling: false })
        }
      }
    })
  },

  noop() {},

  onRecord(e) {
    const id = e.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: `/pages/result/index?sessionId=${id}` })
  },

  goHome() {
    wx.reLaunch({ url: '/pages/home/index' })
  },

  logout() {
    wx.showModal({
      title: '退出登录',
      content: '退出后需要重新输入账号密码。',
      confirmText: '退出',
      success: (res) => {
        if (!res.confirm) return
        auth.clearAuth()
        wx.reLaunch({ url: '/pages/login/index' })
      }
    })
  }
})
