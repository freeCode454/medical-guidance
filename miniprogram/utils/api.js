const { BASE_URL } = require('../config')

/**
 * 统一请求：解包 { code, message, data }，带患者 token。
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
        if (body.code !== 200) {
          if (body.code === 401) wx.removeStorageSync('mg_token')
          const err = new Error(body.message || `请求失败（${body.code}）`)
          err.code = body.code
          reject(err)
          return
        }
        resolve(body.data)
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络异常，请确认后端已启动'))
      }
    })
  })
}

module.exports = { request }
