const auth = require('../../utils/auth')

Page({
  data: {
    account: '',
    initial: '患'
  },

  onShow() {
    if (!auth.requireLogin()) return
    const account = wx.getStorageSync('mg_account') || '患者'
    this.setData({ account, initial: account.slice(0, 1) })
  },

  goChat() {
    wx.navigateTo({ url: '/pages/chat/index' })
  }
})
