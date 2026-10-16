const BASE = '/api/v1'

export interface ApiEnvelope<T = unknown> {
  code: number
  message: string
  data: T
}

let token: string | null = localStorage.getItem('admin_token')

export function setToken(t: string | null) {
  token = t
  if (t) localStorage.setItem('admin_token', t)
  else localStorage.removeItem('admin_token')
}

export function getToken() {
  return token
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, {
    method, headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  let json: ApiEnvelope<T>
  try { json = await res.json() } catch { throw new Error(`请求失败（HTTP ${res.status}）`) }

  if (json.code !== 200) {
    if (json.code === 401) {
      setToken(null)
      window.location.href = '/login'
    }
    const err = new Error(json.message || `请求失败（${json.code}）`) as Error & { code: number }
    err.code = json.code
    throw err
  }
  return json.data
}

export const http = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
}
