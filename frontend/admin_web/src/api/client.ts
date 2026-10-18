const BASE = '/api/v1'

export interface ApiEnvelope<T = unknown> {
  code: number
  message: string
  data: T
}

/** 需要重新登录的业务码：10004 过期 / 10005 无效 */
const AUTH_CODES = new Set([401, 10004, 10005])

let token: string | null = localStorage.getItem('admin_token')
let refreshToken: string | null = localStorage.getItem('admin_refresh_token')
let refreshing: Promise<boolean> | null = null

export function setToken(t: string | null) {
  token = t
  if (t) localStorage.setItem('admin_token', t)
  else localStorage.removeItem('admin_token')
}

export function getToken() {
  return token
}

/** 本地解码 JWT 的 role（仅用于菜单/路由展示，权限仍由后端判定） */
export function getTokenRole(): string | null {
  if (!token) return null
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const decoded = JSON.parse(atob(payload)) as { role?: string }
    return decoded.role ?? null
  } catch {
    return null
  }
}

export function setRefreshToken(t: string | null) {
  refreshToken = t
  if (t) localStorage.setItem('admin_refresh_token', t)
  else localStorage.removeItem('admin_refresh_token')
}

export function clearSession() {
  setToken(null)
  setRefreshToken(null)
  localStorage.removeItem('admin_user')
}

function redirectToLogin() {
  if (window.location.pathname === '/login') return
  const redirect = encodeURIComponent(window.location.pathname + window.location.search)
  window.location.assign(`/login?redirect=${redirect}`)
}

async function refreshSession(): Promise<boolean> {
  if (!refreshToken) return false
  if (refreshing) return refreshing

  refreshing = (async () => {
    try {
      const res = await fetch(`${BASE}/auth/staff/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      const json = (await res.json()) as ApiEnvelope<{
        access_token: string
        refresh_token: string
        user: unknown
      }>
      if (json.code !== 200 || !json.data?.access_token) return false
      setToken(json.data.access_token)
      setRefreshToken(json.data.refresh_token)
      if (json.data.user) localStorage.setItem('admin_user', JSON.stringify(json.data.user))
      return true
    } catch {
      return false
    }
  })().finally(() => {
    refreshing = null
  })

  return refreshing
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  allowRetry = true,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  let json: ApiEnvelope<T>
  try {
    json = (await res.json()) as ApiEnvelope<T>
  } catch {
    throw new Error(`请求失败（HTTP ${res.status}）`)
  }

  if (json.code !== 200) {
    const isAuthError = AUTH_CODES.has(json.code)
    const isAuthPath = path.startsWith('/auth/')
    if (isAuthError && allowRetry && !isAuthPath && (await refreshSession())) {
      return request<T>(method, path, body, false)
    }
    if (isAuthError && !isAuthPath) {
      clearSession()
      redirectToLogin()
    }
    const err = new Error(json.message || `请求失败（${json.code}）`) as Error & {
      code: number
      fields?: Array<{ field: string; message: string }>
    }
    err.code = json.code
    const details = (json.data as { errors?: Array<{ field: string; message: string }> } | null)
      ?.errors
    if (details) err.fields = details
    throw err
  }
  return json.data
}

export const http = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
}
