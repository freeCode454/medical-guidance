const { request } = require('../../utils/api')
const auth = require('../../utils/auth')

const ROUTE_LABELS = {
  DIRECT: '直接分诊',
  MDT: '多学科会诊',
  MANUAL: '转人工',
  EMERGENCY: '急诊'
}

Page({
  data: {
    sessionId: '',
    loading: true,
    error: '',
    isHistory: false,
    visitDate: '',
    triage: null,
    primary: null,
    recommended: [],
    confidencePct: 0,
    routeLabel: '',
    emr: null
  },

  onLoad(options) {
    if (!auth.requireLogin()) return
    const isHistory = options.from === 'history'
    this.setData({
      sessionId: options.sessionId || '',
      isHistory,
      visitDate: decodeURIComponent(options.date || '')
    })
    wx.setNavigationBarTitle({ title: isHistory ? '历史病历' : '分诊结果' })
    this.load()
  },

  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const triage = await request(`/patient/sessions/${this.data.sessionId}/triage`)
      const all = (triage.recommended_depts || []).map((d) => ({
        ...d,
        pct: Math.round((d.confidence || 0) * 100)
      }))
      const primary = all[0] || null
      const recommended = primary
        ? all.filter((d) => d.dept_code !== primary.dept_code)
        : all
      this.setData({
        triage,
        primary,
        recommended,
        confidencePct: Math.round((triage.confidence || 0) * 100),
        routeLabel: ROUTE_LABELS[triage.route] || triage.route
      })
      try {
        const emr = await request(`/patient/sessions/${this.data.sessionId}/emr`)
        this.setData({ emr })
      } catch (e) {
        // 病历可能还在生成，不阻塞结果页
      }
    } catch (e) {
      this.setData({ error: e.message || '分诊结果加载失败' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  goAppointment() {
    const primary = this.data.primary
    if (!primary) return
    const dept = encodeURIComponent(primary.dept_code || '')
    const deptName = encodeURIComponent(primary.dept_name || '')
    const sessionId = encodeURIComponent(this.data.sessionId || '')
    wx.navigateTo({
      url: `/pages/appointment/index?dept=${dept}&deptName=${deptName}&sessionId=${sessionId}`
    })
  }
})
