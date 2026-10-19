const { request } = require('./api')

const TOKEN_KEY = 'mg_token'

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || ''
}

function isLoggedIn() {
  return Boolean(getToken() && wx.getStorageSync('mg_account'))
}

function saveAuth(data) {
  wx.setStorageSync(TOKEN_KEY, data.access_token)
  wx.setStorageSync('mg_patient_id', data.patient_id || '')
  wx.setStorageSync('mg_account', data.account || '')
}

function clearAuth() {
  wx.removeStorageSync(TOKEN_KEY)
  wx.removeStorageSync('mg_patient_id')
  wx.removeStorageSync('mg_account')
}

function requireLogin() {
  if (isLoggedIn()) return true
  // 清除旧版匿名 token，避免绕过账号登录
  if (getToken()) clearAuth()
  wx.reLaunch({ url: '/pages/login/index' })
  return false
}

async function login(account, password) {
  const data = await request('/auth/login', {
    method: 'POST',
    auth: false,
    data: { account, password }
  })
  if (data.role !== 'PATIENT') {
    throw new Error('该账号不是患者账号，请使用患者账号登录')
  }
  saveAuth(data)
  return data
}

async function register(account, password) {
  const data = await request('/auth/patient/register', {
    method: 'POST',
    auth: false,
    data: { account, password }
  })
  saveAuth(data)
  return data
}

function getProfile() {
  return request('/patient/profile')
}

module.exports = {
  getToken,
  isLoggedIn,
  saveAuth,
  clearAuth,
  requireLogin,
  login,
  register,
  getProfile
}
