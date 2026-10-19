const auth = require('../../utils/auth')
const { request } = require('../../utils/api')

function fmtDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}/${p(d.getMonth() + 1)}/${p(d.getDate())}`
}

Page({
  data: {
    deptCode: '',
    deptName: '',
    sessionId: '',
    loading: true,
    error: '',
    days: [],
    activeIndex: 0,
    activeDay: null,
    experts: [],
    others: [],
    appointments: [],
    selected: null,
    booking: false
  },

  onLoad(options) {
    if (!auth.requireLogin()) return
    const deptCode = decodeURIComponent(options.dept || '')
    this.setData({
      deptCode,
      deptName: decodeURIComponent(options.deptName || ''),
      sessionId: decodeURIComponent(options.sessionId || '')
    })
    this.load()
  },

  async load() {
    if (!this.data.deptCode) {
      this.setData({ loading: false, error: '缺少科室信息' })
      return
    }
    this.setData({ loading: true, error: '' })
    try {
      const [data, mine] = await Promise.all([
        request(`/patient/appointments/slots?dept_code=${encodeURIComponent(this.data.deptCode)}`),
        request('/patient/appointments')
      ])
      const days = (data.dates || []).map((day) => {
        const d = new Date(day.date)
        const p = (n) => String(n).padStart(2, '0')
        return {
          ...day,
          label: `${p(d.getMonth() + 1)}/${p(d.getDate())}`
        }
      })
      const appointments = (mine.items || []).map((item) => ({
        ...item,
        dateText: fmtDate(item.schedule_date)
      }))
      this.setData({
        deptName: data.dept_name || this.data.deptName,
        days,
        appointments,
        loading: false
      })
      this.selectDate(0)
    } catch (e) {
      this.setData({ loading: false, error: e.message || '号源加载失败' })
    }
  },

  selectDate(index) {
    const day = this.data.days[index]
    if (!day) return
    const doctors = (day.doctors || []).map((doctor) => ({
      ...doctor,
      initial: (doctor.doctor_name || '医').slice(0, 1)
    }))
    this.setData({
      activeIndex: index,
      activeDay: day,
      experts: doctors.filter((d) => d.is_expert),
      others: doctors.filter((d) => !d.is_expert),
      selected: null
    })
  },

  onDate(e) {
    this.selectDate(Number(e.currentTarget.dataset.index))
  },

  onSlot(e) {
    const di = Number(e.currentTarget.dataset.di)
    const si = Number(e.currentTarget.dataset.si)
    const group = e.currentTarget.dataset.group === 'expert' ? this.data.experts : this.data.others
    const doctor = group[di]
    const slot = doctor && doctor.slots[si]
    if (!slot || !slot.available) return
    this.setData({
      selected: {
        doctorId: doctor.doctor_id,
        doctorName: doctor.doctor_name,
        title: doctor.title,
        timeSlot: slot.time_slot,
        remaining: slot.remaining
      }
    })
  },

  async confirm() {
    const s = this.data.selected
    const day = this.data.activeDay
    if (!s || !day || this.data.booking) return
    this.setData({ booking: true })
    try {
      const item = await request('/patient/appointments', {
        method: 'POST',
        data: {
          session_id: this.data.sessionId || null,
          dept_code: this.data.deptCode,
          doctor_id: s.doctorId,
          schedule_date: day.date,
          time_slot: s.timeSlot
        }
      })
      wx.showToast({ title: `预约成功：${item.schedule_date} ${item.time_slot}`, icon: 'none', duration: 2500 })
      this.setData({ selected: null })
      await this.load()
    } catch (e) {
      wx.showToast({ title: e.message || '预约失败', icon: 'none' })
    } finally {
      this.setData({ booking: false })
    }
  },

  cancel(e) {
    const id = e.currentTarget.dataset.id
    const item = this.data.appointments.find((a) => a.appointment_id === id)
    if (!item) return
    wx.showModal({
      title: '取消预约',
      content: `取消 ${item.dateText} ${item.time_slot} 与 ${item.doctor_name} 的预约？`,
      confirmText: '确认取消',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await request(`/patient/appointments/${id}/cancel`, { method: 'POST' })
          wx.showToast({ title: '已取消预约', icon: 'none' })
          await this.load()
        } catch (err) {
          wx.showToast({ title: err.message || '取消失败', icon: 'none' })
        }
      }
    })
  }
})
