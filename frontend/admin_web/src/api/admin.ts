// 管理端接口封装（账号/机构/系统配置/模型/审计）
import { http } from './client'

export interface PageData<T> { total: number; page: number; size: number; items: T[] }
export interface User { user_id: string; account: string; real_name: string; role: string; role_label: string; title: string | null; dept_code: string | null; dept_name: string | null; status: string; last_login_time?: string | null; create_time?: string | null }
export interface Dept { dept_id: string; dept_code: string; dept_name: string; sort_no: number; status: string }
export interface Patient {
  patient_id: string
  account: string | null
  patient_no: string | null
  registered: boolean
  gender: string | null
  gender_label: string
  age: number | null
  status: string
  session_count: number
  appointment_count: number
  last_login_time?: string | null
  create_time?: string | null
}
export interface AuditItem { audit_id: string; actor_role: string; action_type: string; target_type: string; result: string; detail: any; action_time: string }

export function login(account: string, password: string) {
  return http.post<{ access_token: string; refresh_token: string; user: any }>(
    '/auth/staff/login',
    { account, password, client_type: 'ADMIN_WEB' },
  )
}

// 用户
export const users = {
  list: (q: Record<string, any> = {}) => http.get<PageData<User>>(`/admin/users?${new URLSearchParams(Object.entries(q).filter(([, v]) => v != null && v !== '') as any)}`),
  create: (b: any) => http.post('/admin/users', b),
  update: (id: string, b: any) => http.put(`/admin/users/${id}`, b),
  toggle: (id: string) => http.post(`/admin/users/${id}/toggle`),
}

// 患者（普通用户）
export const patients = {
  list: (q: Record<string, any> = {}) =>
    http.get<PageData<Patient>>(
      `/admin/patients?${new URLSearchParams(
        Object.entries(q).filter(([, v]) => v != null && v !== '') as any,
      )}`,
    ),
  remove: (id: string) => http.delete(`/admin/patients/${id}`),
}

// 科室
export const depts = {
  list: (q: Record<string, any> = {}) => http.get<{ total: number; items: Dept[] }>(`/admin/depts?${new URLSearchParams(Object.entries(q).filter(([, v]) => v != null && v !== '') as any)}`),
  create: (b: any) => http.post('/admin/depts', b),
  update: (id: string, b: any) => http.put(`/admin/depts/${id}`, b),
  toggle: (id: string) => http.post(`/admin/depts/${id}/toggle`),
}

// 机构 + 配置
export const org = {
  get: () => http.get('/admin/org'),
  update: (b: any) => http.put('/admin/org', b),
  configs: () => http.get<{ total: number; items: any[] }>('/admin/configs'),
}

// 模型配置
export const providers = {
  list: () => http.get<{ total: number; items: any[] }>('/admin/model-providers'),
  create: (b: any) => http.post('/admin/model-providers', b),
  update: (id: string, b: any) => http.put(`/admin/model-providers/${id}`, b),
  setDefault: (id: string) => http.post(`/admin/model-providers/${id}/default`, {}),
}

// 审计
export const audits = {
  list: (q: Record<string, any> = {}) => http.get<PageData<AuditItem>>(`/admin/audit-logs?${new URLSearchParams(Object.entries(q).filter(([, v]) => v != null && v !== '') as any)}`),
}
