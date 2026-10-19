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

export interface SymptomSummary {
  chief_complaint: string | null
  duration: string | null
  location: string | null
  nature: string | null
  accompanying: string[] | null
  past_history: string[] | null
  allergy: string[] | null
}

export interface EmergencyGuidance {
  triggered: boolean
  reason: string
  advice: string
  emergency_phone: string
  recommended_dept: string
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
  symptom_summary: SymptomSummary
  inquiry_rounds: number
  history_used?: boolean
  emergency_guidance: EmergencyGuidance | null
  disclaimer: string
  generated_time: string
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

export interface ConsentItem {
  consent_id: string
  scope: string
  consent_time: string
  expire_time: string | null
  revoke_time: string | null
  channel: string | null
}

export interface AppointmentSlot {
  time_slot: string
  capacity: number
  remaining: number
  available: boolean
}

export interface AppointmentDoctor {
  doctor_id: string
  doctor_name: string
  title: string
  is_expert: boolean
  slots: AppointmentSlot[]
}

export interface AppointmentDay {
  date: string
  weekday: string
  doctors: AppointmentDoctor[]
}

export interface AppointmentDeptSlots {
  dept_code: string
  dept_name: string
  dates: AppointmentDay[]
}

export interface AppointmentItem {
  appointment_id: string
  appointment_no: string
  session_id: string | null
  dept_code: string
  dept_name: string
  doctor_id: string
  doctor_name: string
  doctor_title: string | null
  schedule_date: string
  time_slot: string
  status: string
  status_label: string
  can_cancel: boolean
  create_time: string | null
}

// 创建匿名会话（拿患者 token）
export function createAnonymousSession(deviceId: string) {
  return http.post<PatientSession>('/auth/patient/session', {
    device_id: deviceId,
    client_type: 'H5',
    channel: 'DIRECT',
  })
}

// 病史调阅授权
export function grantConsent(sessionId?: string, expireDays = 180) {
  return http.post<ConsentItem>('/patient/consents', {
    scope: 'EMR_READ',
    session_id: sessionId ?? null,
    expire_days: expireDays,
  })
}

export function listConsents() {
  return http.get<{ items: ConsentItem[] }>('/patient/consents')
}

export function revokeConsent(consentId: string) {
  return http.post<ConsentItem>(`/patient/consents/${consentId}/revoke`)
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

// 预约挂号
export function getAppointmentSlots(deptCode: string) {
  return http.get<AppointmentDeptSlots>(
    `/patient/appointments/slots?dept_code=${encodeURIComponent(deptCode)}`,
  )
}

export function listAppointments() {
  return http.get<{ items: AppointmentItem[] }>('/patient/appointments')
}

export function bookAppointment(payload: {
  session_id?: string | null
  dept_code: string
  doctor_id: string
  schedule_date: string
  time_slot: string
}) {
  return http.post<AppointmentItem>('/patient/appointments', payload)
}

export function cancelAppointment(appointmentId: string) {
  return http.post<AppointmentItem>(`/patient/appointments/${appointmentId}/cancel`)
}
