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
    initial: '患'
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
