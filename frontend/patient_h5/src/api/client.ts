// HTTP 客户端：统一处理 {code, data, message} 响应格式
// 开发期走 Vite 代理（/api → 127.0.0.1:8000），业务错误（10xxx~60xxx）HTTP 200 + code 非 200

const BASE = '/api/v1'

export interface ApiEnvelope<T = unknown> {
  code: number
  message: string
  data: T
}

let token: string | null = null

export function setToken(t: string | null) {
  token = t
}

export function getToken() {
  return token
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  let json: ApiEnvelope<T>
  try {
    json = await res.json()
  } catch {
    throw new Error(`请求失败（HTTP ${res.status}）`)
  }

  if (json.code !== 200) {
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
