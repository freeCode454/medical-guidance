const { BASE_URL } = require('../config')

function currentPath() {
  const pages = getCurrentPages()
  return pages.length ? pages[pages.length - 1].route : ''
}

function clearAuth() {
  wx.removeStorageSync('mg_token')
  wx.removeStorageSync('mg_patient_id')
  wx.removeStorageSync('mg_account')
}

/**
 * 统一请求：解包 { code, message, data }，自动带患者 token。
 */
function request(path, { method = 'GET', data, auth = true } = {}) {
  return new Promise((resolve, reject) => {
    const header = { 'Content-Type': 'application/json' }
    const token = wx.getStorageSync('mg_token')
    if (auth && token) header.Authorization = `Bearer ${token}`

    wx.request({
      url: BASE_URL + path,
      method,
      data,
      header,
      timeout: 30000,
      success(res) {
        const body = res.data
        if (!body || typeof body.code === 'undefined') {
          reject(new Error(`请求失败（HTTP ${res.statusCode}）`))
          return
        }
        if (body.code === 200) {
          resolve(body.data)
          return
        }

        if ([10003, 10004, 10005].includes(body.code)) {
          clearAuth()
          if (currentPath() !== 'pages/login/index') {
            wx.reLaunch({ url: '/pages/login/index' })
          }
        }
        const err = new Error(body.message || `请求失败（${body.code}）`)
        err.code = body.code
        reject(err)
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络异常，请确认后端已启动'))
      }
    })
  })
}

module.exports = { request }
