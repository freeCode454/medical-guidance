const auth = require('../../utils/auth')

Page({
  data: {
    mode: 'login',
    account: '',
    password: '',
    confirm: '',
    showPassword: false,
    loading: false
  },

  onLoad() {
    if (auth.isLoggedIn()) {
      wx.reLaunch({ url: '/pages/home/index' })
    }
  },

  switchMode(e) {
    const mode = e.currentTarget.dataset.mode
    this.setData({ mode, password: '', confirm: '' })
  },

  onAccount(e) {
    this.setData({ account: e.detail.value })
  },

  onPassword(e) {
    this.setData({ password: e.detail.value })
  },

  onConfirm(e) {
    this.setData({ confirm: e.detail.value })
  },

  togglePassword() {
    this.setData({ showPassword: !this.data.showPassword })
  },

  async submit() {
    const account = this.data.account.trim()
    const password = this.data.password
    if (account.length < 4) {
      wx.showToast({ title: '账号至少 4 位', icon: 'none' })
      return
    }
    if (password.length < 8) {
      wx.showToast({ title: '密码至少 8 位', icon: 'none' })
      return
    }
    if (this.data.mode === 'register' && password !== this.data.confirm) {
      wx.showToast({ title: '两次密码不一致', icon: 'none' })
      return
    }

    this.setData({ loading: true })
    try {
      if (this.data.mode === 'register') {
        await auth.register(account, password)
      } else {
        await auth.login(account, password)
      }
      wx.reLaunch({ url: '/pages/home/index' })
    } catch (e) {
      wx.showToast({ title: e.message || '登录失败，请重试', icon: 'none', duration: 2500 })
    } finally {
      this.setData({ loading: false })
    }
  }
})
