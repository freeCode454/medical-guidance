// 知识库接口封装
import { http } from './client'

export interface KbEntry {
  entry_id: string
  entry_code: string
  kb_type: string
  title: string | null
  dept_code: string | null
  status: string
  is_active: boolean
  entry_version: string | null
  update_time: string | null
}

export interface KbEntryDetail extends KbEntry {
  content: string
  content_json?: unknown
  icd10_codes?: string[] | null
  age_group?: string | null
  gender?: string | null
  source?: string | null
}

export interface PageData<T> { total: number; page: number; size: number; items: T[] }

export interface KbPublish {
  publish_id: string
  version_tag: string
  entry_count: number
  snapshot_hash?: string | null
  published_by: string
  published_time: string | null
}

export interface KbIngestTask {
  task_id: string
  task_no: string
  status: string
  stage: string | null
  progress: number
  total_count: number
  added_count: number
  updated_count?: number
  disabled_count?: number
  failed_count: number
  error_json?: { message?: string } | null
}

export const kb = {
  list: (q: Record<string, any> = {}) => http.get<PageData<KbEntry>>(`/admin/kb/entries?${new URLSearchParams(Object.entries(q).filter(([, v]) => v != null && v !== '') as any)}`),
  create: (b: any) => http.post('/admin/kb/entries', b),
  get: (id: string) => http.get<KbEntryDetail>(`/admin/kb/entries/${id}`),
  update: (id: string, b: any) => http.put(`/admin/kb/entries/${id}`, b),
  toggle: (id: string) => http.post(`/admin/kb/entries/${id}/toggle`),
  history: (id: string) => http.get(`/admin/kb/entries/${id}/history`),
  retrievalTest: (b: any) => http.post<{ candidates: Array<{ dept_code: string; dept_name: string; score: number }> }>('/admin/kb/retrieval-test', b),
  publish: () => http.post<{ publish_id: string; version_tag: string; entry_count: number }>('/admin/kb/publish', {}),
  publishes: () => http.get<{ total: number; items: KbPublish[] }>('/admin/kb/publishes'),
  ingest: () => http.post<KbIngestTask>('/admin/kb/ingest', {}),
  ingestTask: (id: string) => http.get<KbIngestTask>(`/admin/kb/ingest-tasks/${id}`),
}
