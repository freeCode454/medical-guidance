// 医生端接口封装
import { http } from './client'

export interface DoctorInfo {
  user_id: string
  account: string
  real_name: string | null
  role: string
  title: string | null
  dept_code: string | null
  dept_name: string | null
  tenant_id: string
  tenant_name: string
}

export interface EncounterItem {
  session_id: string
  session_no: string
  patient_display: string
  patient_hash: string | null
  chief_complaint: string | null
  status: string
  risk_flag: boolean
  inquiry_rounds: number
  started_time: string | null
}

export interface PageData<T> {
  total: number
  page: number
  size: number
  items: T[]
}

export interface SessionDetail {
  session_id: string
  session_no: string
  status: string
  risk_flag: boolean
  chief_complaint: string | null
  inquiry_rounds: number
  patient: {
    patient_id: string
    patient_display: string
    age: number | null
    gender: string | null
  }
  triage_status: { has_result: boolean; route: string | null; doctor_confirmed: boolean }
  consent_granted: boolean
  consent_scope_label: string | null
  started_time: string | null
  finished_time: string | null
}

export interface EmrDoc {
  emr_record_id: string
  generate_status: string
  completeness_rate: number
  subjective: {
    chief_complaint: string
    present_illness: string
    past_history: string[]
    allergy: string[]
  }
  objective: { note: string }
  assessment: { differential_directions: any[]; note: string } | null
  plan: { recommended_depts: string[]; suggested_workup: string[]; note: string }
  disclaimer: string
  generated_time?: string
}

export interface PatientHistoryRecord {
  emr_record_id: string
  session_id: string
  chief_complaint: string
  generate_status: string
  created_time: string | null
}

export interface PatientHistory {
  patient_id: string
  patient_display: string
  consent_required: boolean
  records: PatientHistoryRecord[]
}

export interface Diagnosis {
  triage_result_id: string
  retrieval_mode: string
  candidates: Array<{ rank: number; dept_code: string; dept_name: string; confidence: number; hit_symptoms: string[]; guideline_refs: any[] }>
  mdt: {
    triggered: boolean
    consensus_dept: string | null
    consensus_confidence: number
    divergence: { exists: boolean; items: any[] }
  } | null
  drug_safety: { checked: boolean; allergy_hits: any[]; contraindication_hits: any[]; note: string }
}

export function login(account: string, password: string) {
  return http.post<{ access_token: string; refresh_token: string; user: DoctorInfo }>(
    '/auth/staff/login',
    { account, password, client_type: 'WEB' },
  )
}

export function listEncounters(params: Record<string, any> = {}) {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== '') as any).toString()
  return http.get<PageData<EncounterItem>>(`/doctor/encounters${q ? '?' + q : ''}`)
}

export function listTakeoverQueue(page = 1, size = 10) {
  return http.get<PageData<EncounterItem>>(`/doctor/takeover-queue?page=${page}&size=${size}`)
}

export function getSession(sessionId: string) {
  return http.get<SessionDetail>(`/doctor/sessions/${sessionId}`)
}

export function listMessages(sessionId: string) {
  return http.get<PageData<any>>(`/doctor/sessions/${sessionId}/messages?size=100`)
}

export function getEmr(sessionId: string) {
  return http.get<EmrDoc>(`/doctor/sessions/${sessionId}/emr`)
}

export function getDiagnosis(sessionId: string) {
  return http.get<Diagnosis>(`/doctor/sessions/${sessionId}/diagnosis`)
}

export function getPatientEmr(patientId: string) {
  return http.get<PatientHistory>(`/doctor/patients/${patientId}/emr`)
}

export function confirmTriage(sessionId: string, note?: string) {
  return http.post(`/doctor/sessions/${sessionId}/confirm`, { note })
}

export function correctTriage(sessionId: string, afterDept: string, reason: string) {
  return http.post(`/doctor/sessions/${sessionId}/correct`, { after_dept: afterDept, reason })
}

export function takeover(sessionId: string) {
  return http.post(`/doctor/sessions/${sessionId}/takeover`)
}

export function listDepts() {
  return http.get<Array<{ dept_code: string; dept_name: string }>>('/doctor/depts')
}
