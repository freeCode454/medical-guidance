// 知识图谱接口封装
import { http } from './client'

export interface KgNode {
  id: string
  name: string
  category: number // 0 症状 / 1 疾病 / 2 科室
}

export interface KgEdge {
  source: string
  target: string
  label: string
}

export interface KgStats {
  nodes: { label: string; count: number }[]
  relationships: { type: string; count: number }[]
}

export interface KgNetwork {
  symptom: string
  nodes: KgNode[]
  edges: KgEdge[]
  paths: number
}

export const kg = {
  stats: () => http.get<KgStats>('/admin/kg/stats'),
  symptoms: () => http.get<{ items: string[] }>('/admin/kg/symptoms'),
  network: (symptom: string, limit = 30) =>
    http.get<KgNetwork>(
      `/admin/kg/network?symptom=${encodeURIComponent(symptom)}&limit=${limit}`,
    ),
}
