Component({
  properties: {
    active: {
      type: String,
      value: 'home'
    }
  },

  data: {
    homeIcon: '/assets/tab-home-on.png',
    userIcon: '/assets/tab-user.png'
  },

  observers: {
    active(value) {
      this.setData({
        homeIcon: value === 'home' ? '/assets/tab-home-on.png' : '/assets/tab-home.png',
        userIcon: value === 'profile' ? '/assets/tab-user-on.png' : '/assets/tab-user.png'
      })
    }
  },

  methods: {
    go(e) {
      const path = e.currentTarget.dataset.path
      if (!path) return
      wx.reLaunch({ url: path })
    }
  }
})
