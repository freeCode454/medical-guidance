const { request } = require('./api')

function fallbackHex() {
  let out = ''
  for (let i = 0; i < 64; i += 1) out += Math.floor(Math.random() * 16).toString(16)
  return out
}

function randomHex() {
  return new Promise((resolve) => {
    if (!wx.getRandomValues) {
      resolve(fallbackHex())
      return
    }
    wx.getRandomValues({
      length: 32,
      success(res) {
        try {
          const bytes = new Uint8Array(res.randomValues)
          resolve(
            Array.from(bytes)
              .map((b) => b.toString(16).padStart(2, '0'))
              .join('')
          )
        } catch (e) {
          resolve(fallbackHex())
        }
      },
      fail() {
        resolve(fallbackHex())
      }
    })
  })
}

async function getDeviceId() {
  let deviceId = wx.getStorageSync('mg_device_id')
  if (!deviceId || deviceId.length < 32) {
    deviceId = await randomHex()
    wx.setStorageSync('mg_device_id', deviceId)
  }
  return deviceId
}

async function ensureAuth() {
  let token = wx.getStorageSync('mg_token')
  if (token) return token

  const deviceId = await getDeviceId()
  const data = await request('/auth/patient/session', {
    method: 'POST',
    auth: false,
    data: {
      device_id: deviceId,
      client_type: 'MINIPROGRAM',
      channel: 'WECHAT_MP'
    }
  })
  wx.setStorageSync('mg_token', data.access_token)
  return data.access_token
}

module.exports = { ensureAuth, getDeviceId }
