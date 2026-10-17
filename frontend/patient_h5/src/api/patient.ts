// 患者端接口封装
import { http } from './client'

export interface PatientSession {
  access_token: string
  patient_id: string
  device_id: string
}

export interface SessionInfo {
  session_id: string
  session_no: string
  status: string
  chief_complaint: string | null
  inquiry_rounds: number
  has_triage: boolean
  route: string | null
}

export interface ChatMessage {
  message_id: string
  seq_no: number
  role: 'PATIENT' | 'AI' | 'DOCTOR' | 'SYSTEM'
  content: string
  msg_type: string
  extra: Record<string, unknown>
  send_time: string | null
}

export interface TriageResult {
  triage_result_id: string
  route: string
  confidence: number
  recommended_depts: Array<{
    dept_code: string
    dept_name: string
    confidence: number
    is_primary: boolean
  }>
  disclaimer: string
}

export interface EmrView {
  emr_record_id: string
  generate_status: string
  subjective: { chief_complaint: string; present_illness: string; past_history: string[]; allergy: string[] }
  objective: { collected_vitals: unknown[]; note: string }
  assessment: null
  plan: { recommended_depts: string[]; suggested_workup: string[]; note: string }
  disclaimer: string
}

// 创建匿名会话（拿患者 token）
export function createAnonymousSession(deviceId: string) {
  return http.post<PatientSession>('/auth/patient/session', {
    device_id: deviceId,
    client_type: 'H5',
    channel: 'DIRECT',
  })
}

// 创建预问诊会话
export function createSession(
  chiefComplaint: string,
  deviceId: string,
  extra?: { gender?: '男' | '女'; age?: number },
) {
  return http.post<{ session_id: string; session_no: string; status: string }>('/patient/sessions', {
    chief_complaint: chiefComplaint,
    device_id: deviceId,
    input_type: 'TEXT',
    gender: extra?.gender ?? null,
    age: extra?.age ?? null,
  })
}

// 发送消息
export function sendMessage(sessionId: string, content: string) {
  return http.post<{ message_id: string; seq_no: number; async: boolean }>(
    `/patient/sessions/${sessionId}/messages`,
    { content, msg_type: 'TEXT' },
  )
}

// 查询消息列表
export function listMessages(sessionId: string, afterSeq?: number) {
  const q = afterSeq !== undefined ? `?after_seq=${afterSeq}` : ''
  return http.get<{ total: number; items: ChatMessage[] }>(`/patient/sessions/${sessionId}/messages${q}`)
}

// 查询会话详情
export function getSession(sessionId: string) {
  return http.get<SessionInfo>(`/patient/sessions/${sessionId}`)
}

// 查询分诊结果
export function getTriage(sessionId: string) {
  return http.get<TriageResult>(`/patient/sessions/${sessionId}/triage`)
}

// 查询患者视图病历
export function getEmr(sessionId: string) {
  return http.get<EmrView>(`/patient/sessions/${sessionId}/emr`)
}
