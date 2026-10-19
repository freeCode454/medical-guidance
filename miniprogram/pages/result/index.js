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
    triage: null,
    primary: null,
    recommended: [],
    confidencePct: 0,
    routeLabel: '',
    emr: null
  },

  onLoad(options) {
    if (!auth.requireLogin()) return
    this.setData({ sessionId: options.sessionId || '' })
    this.load()
  },

  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const triage = await request(`/patient/sessions/${this.data.sessionId}/triage`)
      const recommended = (triage.recommended_depts || []).map((d) => ({
        ...d,
        pct: Math.round((d.confidence || 0) * 100)
      }))
      this.setData({
        triage,
        primary: recommended[0] || null,
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
  }
})
