<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppHeader from '@/components/AppHeader.vue'
import {
  getSession, getEmr, getDiagnosis, getPatientEmr,
  confirmTriage, correctTriage, listDepts,
  type SessionDetail, type EmrDoc, type Diagnosis, type PatientHistory,
} from '@/api/doctor'
import { fmtDateTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.id as string
const activeTab = ref('overview')

const session = ref<SessionDetail | null>(null)
const emr = ref<EmrDoc | null>(null)
const diagnosis = ref<Diagnosis | null>(null)
const depts = ref<Array<{ dept_code: string; dept_name: string }>>([])
const loading = ref(true)
const loadError = ref('')
const emrError = ref('')
const diagnosisError = ref('')

const correctVisible = ref(false)
const afterDept = ref('')
const reason = ref('')

const historyVisible = ref(false)
const historyLoading = ref(false)
const history = ref<PatientHistory | null>(null)
const historyError = ref('')

const statusMap: Record<string, { label: string; type: 'info' | 'success' | 'warning' | 'danger' | 'primary' }> = {
  IN_PROGRESS: { label: '问诊中', type: 'info' },
  FINISHED: { label: '已出结论', type: 'success' },
  PENDING_TAKEOVER: { label: '待接管', type: 'warning' },
  TAKEN_OVER: { label: '已接管', type: 'primary' },
  CLOSED: { label: '已结束', type: 'info' },
  EMERGENCY: { label: '急诊', type: 'danger' },
}

const emrStatusLabel: Record<string, string> = {
  SUCCESS: '生成成功',
  PARTIAL: '部分生成',
  FAILED: '生成失败',
}

const patientName = computed(() => session.value?.patient.patient_display || '患者')
const patientInitial = computed(() => patientName.value.slice(0, 1))
const primaryDept = computed(() => diagnosis.value?.candidates?.[0] ?? null)
const allergyHits = computed(() => diagnosis.value?.drug_safety?.allergy_hits || [])
const contraindicationHits = computed(
  () => diagnosis.value?.drug_safety?.contraindication_hits || [],
)
const drugSafetyTotal = computed(() => allergyHits.value.length + contraindicationHits.value.length)

function severityType(severity: string): 'danger' | 'warning' | 'info' {
  if (severity === 'HIGH') return 'danger'
  if (severity === 'MEDIUM') return 'warning'
  return 'info'
}

function severityLabel(severity: string) {
  if (severity === 'HIGH') return '禁用风险'
  if (severity === 'MEDIUM') return '慎用'
  return '注意'
}
const confirmed = computed(() => session.value?.triage_status.doctor_confirmed ?? false)
const canConfirm = computed(
  () => !!session.value?.triage_status.has_result && !confirmed.value,
)
const statusInfo = computed(
  () => statusMap[session.value?.status || ''] || { label: session.value?.status || '—', type: 'info' as const },
)

function pct(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return '—'
  return Math.round(Math.min(1, Math.max(0, n)) * 100) + '%'
}

function barWidth(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return '0%'
  return Math.round(Math.min(1, Math.max(0, n)) * 100) + '%'
}

function errorMessage(error: unknown, fallback: string) {
  const e = error as { message?: string; code?: number }
  return e.message || fallback
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    session.value = await getSession(sessionId)
  } catch (e) {
    loadError.value = errorMessage(e, '会话加载失败')
    loading.value = false
    return
  }
  loading.value = false

  const [emrResult, diagnosisResult, deptResult] = await Promise.allSettled([
    getEmr(sessionId),
    getDiagnosis(sessionId),
    listDepts(),
  ])

  if (emrResult.status === 'fulfilled') {
    emr.value = emrResult.value
    emrError.value = ''
  } else {
    emr.value = null
    emrError.value =
      (emrResult.reason as { code?: number })?.code === 20006
        ? '预问诊病历尚未生成，等待 AI 整理完成后刷新'
        : errorMessage(emrResult.reason, '病历加载失败')
  }

  if (diagnosisResult.status === 'fulfilled') {
    diagnosis.value = diagnosisResult.value
    diagnosisError.value = ''
  } else {
    diagnosis.value = null
    diagnosisError.value =
      (diagnosisResult.reason as { code?: number })?.code === 20006
        ? '分诊结论尚未生成'
        : errorMessage(diagnosisResult.reason, '鉴别诊断加载失败')
  }

  if (deptResult.status === 'fulfilled') depts.value = deptResult.value
}

async function onConfirm() {
  if (!canConfirm.value) return
  const dept = primaryDept.value?.dept_name
  try {
    await ElMessageBox.confirm(
      dept ? `确认将患者分诊到「${dept}」？确认后会写入审计日志。` : '确认该分诊结论？',
      '确认分诊',
      { confirmButtonText: '确认分诊', cancelButtonText: '再看看' },
    )
  } catch {
    return
  }
  try {
    await confirmTriage(sessionId)
    ElMessage.success('已确认分诊')
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e, '确认失败'))
  }
}

function openCorrect() {
  afterDept.value = ''
  reason.value = ''
  correctVisible.value = true
}

async function submitCorrect() {
  if (!afterDept.value) {
    ElMessage.warning('请选择修正后的科室')
    return
  }
  if (reason.value.trim().length < 10) {
    ElMessage.warning('修正理由不少于 10 字')
    return
  }
  try {
    await correctTriage(sessionId, afterDept.value, reason.value.trim())
    ElMessage.success('修正已记录，可作为评测样本')
    correctVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e, '修正失败'))
  }
}

async function openHistory() {
  if (!session.value) return
  historyVisible.value = true
  if (history.value || historyLoading.value) return
  historyLoading.value = true
  historyError.value = ''
  try {
    history.value = await getPatientEmr(session.value.patient.patient_id)
  } catch (e) {
    historyError.value = errorMessage(e, '历史病历加载失败')
  } finally {
    historyLoading.value = false
  }
}

onMounted(load)
</script>

<template>
  <AppHeader />
  <main class="session-page">
    <div class="crumb">
      <button class="crumb__back" type="button" aria-label="返回今日接诊" @click="router.back()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M14.5 6l-6 6 6 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <span>今日接诊</span>
      <i>/</i>
      <span class="crumb__current">{{ patientName }}</span>
    </div>

    <div v-if="loading" class="loading-block">
      <div class="skeleton skeleton--head" />
      <div class="skeleton skeleton--body" />
    </div>

    <div v-else-if="loadError" class="empty-block panel">
      <p class="empty-block__title">会话加载失败</p>
      <p>{{ loadError }}</p>
      <el-button @click="load">重试</el-button>
    </div>

    <template v-else-if="session">
      <header class="patient-head">
        <div class="patient-id">
          <span class="patient-avatar">{{ patientInitial }}</span>
          <div class="patient-id__text">
            <h1>{{ patientName }}</h1>
            <div class="patient-meta">
              <span>{{ session.patient.gender || '性别未知' }}</span>
              <span>{{ session.patient.age ?? '年龄未知' }}</span>
              <span class="mono">{{ session.session_no }}</span>
              <span>{{ fmtDateTime(session.started_time) }} 开始</span>
            </div>
          </div>
          <div class="patient-tags">
            <el-tag :type="statusInfo.type" size="small" effect="light">{{ statusInfo.label }}</el-tag>
            <span v-if="session.risk_flag" class="risk-badge">高危</span>
          </div>
        </div>

        <div class="head-actions">
          <el-button plain @click="openHistory">
            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M5 6.5A2.5 2.5 0 017.5 4H19v16H7.5A2.5 2.5 0 015 17.5v-11z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
              <path d="M9 8h6M9 12h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            历史病历
          </el-button>
          <el-button plain @click="openCorrect">修正分诊</el-button>
          <button class="confirm-btn" type="button" :disabled="!canConfirm" @click="onConfirm">
            <svg v-if="!confirmed" class="btn-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M5 12.5l4.5 4.5L19 7.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            {{ confirmed ? '已确认分诊' : '确认分诊' }}
          </button>
        </div>
      </header>

      <div class="layout">
        <section class="main-col">
          <el-tabs v-model="activeTab" class="tabs">
            <el-tab-pane label="概览" name="overview">
              <article class="panel complaint-card">
                <p class="section-label">患者主诉</p>
                <p class="complaint-text">{{ session.chief_complaint || '患者尚未描述症状' }}</p>
                <div class="info-grid">
                  <div class="info-cell">
                    <span>状态</span>
                    <b>{{ statusInfo.label }}</b>
                  </div>
                  <div class="info-cell">
                    <span>医生确认</span>
                    <b>{{ confirmed ? '已确认' : '未确认' }}</b>
                  </div>
                </div>
              </article>

              <article class="panel guide-card">
                <div class="guide-card__icon" aria-hidden="true">i</div>
                <div>
                  <b>接诊建议</b>
                  <p>
                    先看右侧分诊结论与置信度，再展开「鉴别诊断」查看知识图谱路径与指南推荐；
                    确认或修正分诊后，本次操作会写入审计日志。
                  </p>
                </div>
              </article>
            </el-tab-pane>

            <el-tab-pane label="预问诊病历" name="emr">
              <template v-if="emr">
                <article class="panel emr-head">
                  <div>
                    <p class="section-label">SOAP 预问诊病历</p>
                    <div class="emr-head__tags">
                      <el-tag size="small" effect="plain">生成状态 {{ emrStatusLabel[emr.generate_status] || emr.generate_status }}</el-tag>
                      <span v-if="emr.generated_time" class="muted">
                        {{ fmtDateTime(emr.generated_time) }}
                      </span>
                    </div>
                  </div>
                  <div class="completeness">
                    <span>字段完整度 <b>{{ pct(emr.completeness_rate) }}</b></span>
                    <div class="bar"><i :style="{ width: barWidth(emr.completeness_rate) }" /></div>
                  </div>
                </article>

                <div class="soap-grid">
                  <article class="panel soap-card">
                    <header class="soap-head">
                      <span class="soap-letter">S</span>
                      <div><b>主观资料</b><em>患者自述</em></div>
                    </header>
                    <p class="soap-label">主诉</p>
                    <p class="soap-text">{{ emr.subjective.chief_complaint || '—' }}</p>
                    <p class="soap-label">现病史</p>
                    <p class="soap-text">{{ emr.subjective.present_illness || '—' }}</p>
                    <div v-if="emr.subjective.allergy?.length" class="tag-row">
                      <span class="tag-label">过敏史</span>
                      <span v-for="a in emr.subjective.allergy" :key="a" class="tag tag--warn">{{ a }}</span>
                    </div>
                    <div v-if="emr.subjective.past_history?.length" class="tag-row">
                      <span class="tag-label">既往史</span>
                      <span v-for="h in emr.subjective.past_history" :key="h" class="tag">{{ h }}</span>
                    </div>
                  </article>

                  <article class="panel soap-card">
                    <header class="soap-head">
                      <span class="soap-letter soap-letter--amber">O</span>
                      <div><b>客观资料</b><em>问诊采集</em></div>
                    </header>
                    <p class="soap-text">{{ emr.objective.note || '本次未采集额外客观信息' }}</p>
                  </article>

                  <article class="panel soap-card">
                    <header class="soap-head">
                      <span class="soap-letter soap-letter--slate">A</span>
                      <div><b>评估</b><em>仅医生端可见</em></div>
                    </header>
                    <p class="soap-text">{{ emr.assessment?.note || '—' }}</p>
                    <div v-if="emr.assessment?.differential_directions?.length" class="tag-row">
                      <span
                        v-for="d in emr.assessment.differential_directions"
                        :key="d.dept_code"
                        class="tag tag--dept"
                      >
                        {{ d.dept_code }} · {{ pct(d.confidence) }}
                      </span>
                    </div>
                  </article>

                  <article class="panel soap-card">
                    <header class="soap-head">
                      <span class="soap-letter">P</span>
                      <div><b>计划</b><em>就诊建议</em></div>
                    </header>
                    <p class="soap-text">{{ emr.plan.note || '—' }}</p>
                    <div v-if="emr.plan.recommended_depts?.length" class="tag-row">
                      <span v-for="d in emr.plan.recommended_depts" :key="d" class="tag tag--dept">{{ d }}</span>
                    </div>
                    <div v-if="emr.plan.suggested_workup?.length" class="tag-row">
                      <span class="tag-label">建议检查</span>
                      <span v-for="w in emr.plan.suggested_workup" :key="w" class="tag">{{ w }}</span>
                    </div>
                  </article>
                </div>

                <p class="disclaimer">{{ emr.disclaimer }}</p>
              </template>

              <div v-else class="empty-block panel">
                <p class="empty-block__title">病历尚未生成</p>
                <p>{{ emrError || '等待 AI 整理完成后刷新' }}</p>
                <el-button @click="load">刷新</el-button>
              </div>
            </el-tab-pane>

            <el-tab-pane label="鉴别诊断" name="diagnosis">
              <template v-if="diagnosis">
                <article class="panel">
                  <div class="panel-head">
                    <p class="section-label">候选科室</p>
                    <span class="muted">按综合得分排序</span>
                  </div>
                  <el-table :data="diagnosis.candidates" size="small" class="candidate-table">
                    <el-table-column type="expand">
                      <template #default="{ row }">
                        <div class="expand-box">
                          <div class="kg-box">
                            <p class="kg-title">
                              知识图谱推理路径
                              <span v-if="row.kg_disease_hits" class="kg-hits">（{{ row.kg_disease_hits }} 个疾病命中）</span>
                            </p>
                            <div v-for="p in row.kg_paths" :key="p" class="kg-path">{{ p }}</div>
                            <p v-if="!row.kg_paths || !row.kg_paths.length" class="muted">该科室暂无图谱路径</p>
                          </div>

                          <div v-if="row.guideline_refs && row.guideline_refs.length" class="gl-box">
                            <p class="gl-title">指南推荐意见</p>
                            <div v-for="(g, gi) in row.guideline_refs" :key="gi" class="gl-item">
                              <div class="gl-head">
                                <el-tag size="small" type="warning">{{ g.disease_name }}</el-tag>
                                <el-tag size="small" effect="plain">证据 {{ g.evidence_level }}</el-tag>
                                <el-tag size="small" :type="g.strength === '强' ? 'danger' : 'info'">{{ g.strength }}推荐</el-tag>
                                <span v-if="g.population && g.population !== '通用'" class="gl-pop">{{ g.population }}</span>
                              </div>
                              <div class="gl-text">{{ g.recommendation }}</div>
                              <div class="gl-src">{{ g.source }}</div>
                            </div>
                          </div>
                          <p v-else class="muted">该科室暂无指南推荐</p>
                        </div>
                      </template>
                    </el-table-column>
                    <el-table-column prop="rank" label="#" width="48" />
                    <el-table-column prop="dept_name" label="科室" width="140" />
                    <el-table-column label="置信度" width="170">
                      <template #default="{ row }">
                        <div class="conf-cell">
                          <div class="bar"><i :style="{ width: barWidth(row.confidence) }" /></div>
                          <span class="mono">{{ pct(row.confidence) }}</span>
                        </div>
                      </template>
                    </el-table-column>
                    <el-table-column label="命中症状" min-width="180">
                      <template #default="{ row }">{{ row.hit_symptoms.join('、') || '依据不足' }}</template>
                    </el-table-column>
                    <el-table-column label="图谱" width="86">
                      <template #default="{ row }">
                        <el-tag v-if="row.kg_paths && row.kg_paths.length" size="small" type="success">有路径</el-tag>
                        <span v-else class="muted">—</span>
                      </template>
                    </el-table-column>
                  </el-table>
                </article>

                <article v-if="diagnosis.mdt?.triggered" class="panel panel--pad mdt-card">
                  <div class="panel-head">
                    <p class="section-label">多学科会诊（MDT）</p>
                    <el-tag v-if="diagnosis.mdt.divergence.exists" type="warning" size="small">存在分歧</el-tag>
                  </div>
                  <p class="soap-text">
                    共识科室：<b>{{ diagnosis.mdt.consensus_dept }}</b>
                    · 置信度 {{ pct(diagnosis.mdt.consensus_confidence) }}
                  </p>
                  <p v-if="diagnosis.mdt.divergence.exists" class="muted">
                    各专科意见不一致，展开候选科室可查看各自依据。
                  </p>
                </article>

                <article class="panel panel--pad">
                  <div class="panel-head">
                    <p class="section-label">用药禁忌校验</p>
                    <el-tag
                      v-if="diagnosis.drug_safety.checked"
                      :type="drugSafetyTotal ? 'danger' : 'success'"
                      size="small"
                      effect="plain"
                    >
                      {{ drugSafetyTotal ? `${drugSafetyTotal} 项需核对` : '已校验' }}
                    </el-tag>
                  </div>

                  <el-alert
                    v-if="!diagnosis.drug_safety.checked"
                    type="warning"
                    :closable="false"
                    :title="diagnosis.drug_safety.note"
                  />

                  <template v-else>
                    <el-alert
                      v-if="diagnosis.drug_safety.allergy_known === false"
                      type="info"
                      :closable="false"
                      title="患者过敏史未记录，以下结果仅基于既往疾病和年龄，仍需人工核对。"
                    />

                    <div v-if="!drugSafetyTotal" class="drug-safe-empty">
                      <span class="drug-safe-empty__icon">✓</span>
                      <span>未发现已知的用药禁忌冲突</span>
                    </div>

                    <template v-else>
                      <section v-if="allergyHits.length" class="drug-section">
                        <p class="drug-section__title">
                          过敏史冲突
                          <span>{{ allergyHits.length }} 项</span>
                        </p>
                        <div v-for="hit in allergyHits" :key="`a-${hit.entry_code || hit.drug_name}`" class="drug-hit">
                          <div class="drug-hit__main">
                            <b>{{ hit.drug_name }}</b>
                            <span>与「{{ hit.allergy_item }}」冲突</span>
                          </div>
                          <div class="drug-hit__side">
                            <el-tag :type="severityType(hit.severity)" size="small">
                              {{ severityLabel(hit.severity) }}
                            </el-tag>
                            <span>{{ hit.suggestion }}</span>
                          </div>
                          <p v-if="hit.note" class="drug-hit__note">{{ hit.note }}</p>
                        </div>
                      </section>

                      <section v-if="contraindicationHits.length" class="drug-section">
                        <p class="drug-section__title">
                          基础疾病 / 人群禁忌
                          <span>{{ contraindicationHits.length }} 项</span>
                        </p>
                        <div
                          v-for="hit in contraindicationHits"
                          :key="`c-${hit.entry_code || hit.drug_name}`"
                          class="drug-hit"
                        >
                          <div class="drug-hit__main">
                            <b>{{ hit.drug_name }}</b>
                            <span>与「{{ hit.allergy_item }}」冲突</span>
                          </div>
                          <div class="drug-hit__side">
                            <el-tag :type="severityType(hit.severity)" size="small">
                              {{ severityLabel(hit.severity) }}
                            </el-tag>
                            <span>{{ hit.suggestion }}</span>
                          </div>
                          <p v-if="hit.note" class="drug-hit__note">{{ hit.note }}</p>
                        </div>
                      </section>
                    </template>

                    <p class="drug-safe-note">{{ diagnosis.drug_safety.note }}</p>
                  </template>
                </article>
              </template>

              <div v-else class="empty-block panel">
                <p class="empty-block__title">分诊结论尚未生成</p>
                <p>{{ diagnosisError || '等待 AI 完成检索与决策' }}</p>
                <el-button @click="load">刷新</el-button>
              </div>
            </el-tab-pane>
          </el-tabs>
        </section>

        <aside class="side-col">
          <article class="panel triage-card">
            <p class="side-label">分诊结论</p>
            <template v-if="primaryDept">
              <h2 class="triage-dept">{{ primaryDept.dept_name }}</h2>
              <div class="triage-conf">
                <div class="bar bar--light"><i :style="{ width: barWidth(primaryDept.confidence) }" /></div>
                <span>{{ pct(primaryDept.confidence) }}</span>
              </div>
              <dl class="triage-meta">
                <div><dt>候选</dt><dd>{{ diagnosis?.candidates.length ?? 0 }} 个科室</dd></div>
              </dl>
              <p v-if="confirmed" class="confirmed-note">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M5 12.5l4.5 4.5L19 7.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
                已确认分诊
              </p>
              <button v-else class="confirm-btn confirm-btn--block" type="button" :disabled="!canConfirm" @click="onConfirm">
                确认分诊
              </button>
            </template>
            <p v-else class="muted">分诊结论尚未生成</p>
          </article>

          <article class="panel info-card">
            <p class="side-label">会话信息</p>
            <dl class="info-list">
              <div><dt>会话号</dt><dd class="mono">{{ session.session_no }}</dd></div>
              <div><dt>开始时间</dt><dd>{{ fmtDateTime(session.started_time) }}</dd></div>
              <div><dt>患者授权</dt><dd>{{ session.consent_granted ? '已授权历史病历' : '未授权历史病历' }}</dd></div>
            </dl>
          </article>

          <article class="panel consent-card">
            <p class="side-label">隐私授权</p>
            <p class="consent-state" :class="{ 'is-ok': session.consent_granted }">
              {{ session.consent_granted ? '患者已授权调阅历史病历' : '患者未授权调阅历史病历' }}
            </p>
            <p class="consent-hint">
              仅影响历史病历；本次预问诊病历属于当前诊疗关系，不受影响。
            </p>
            <el-button text size="small" @click="openHistory">查看历史病历</el-button>
          </article>
        </aside>
      </div>
    </template>
  </main>

  <el-drawer v-model="historyVisible" title="历史预问诊病历" size="420px">
    <div v-loading="historyLoading" class="history-body">
      <div v-if="historyError" class="empty-block">
        <p class="empty-block__title">加载失败</p>
        <p>{{ historyError }}</p>
        <el-button size="small" @click="history = null; openHistory()">重试</el-button>
      </div>

      <template v-else-if="history">
        <div v-if="history.consent_required" class="consent-empty">
          <span class="consent-empty__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <rect x="5" y="10" width="14" height="10" rx="3" stroke="currentColor" stroke-width="1.6" />
              <path d="M8.5 10V7.5a3.5 3.5 0 017 0V10" stroke="currentColor" stroke-width="1.6" />
            </svg>
          </span>
          <p class="empty-block__title">患者未授权调阅历史病历</p>
          <p>患者可在首页勾选「允许接诊医生调阅历史预问诊病历」，或在此次就诊时口头授权后由患者端操作。</p>
        </div>

        <template v-else>
          <p class="history-summary">共 {{ history.records.length }} 份历史预问诊病历</p>
          <article v-for="r in history.records" :key="r.emr_record_id" class="history-item">
            <div class="history-item__head">
              <b>{{ r.chief_complaint || '未记录主诉' }}</b>
              <el-tag size="small" effect="plain">{{ r.generate_status }}</el-tag>
            </div>
            <p class="history-item__meta">
              {{ fmtDateTime(r.created_time) }} · 会话 {{ r.session_id.slice(0, 8) }}
            </p>
          </article>
          <div v-if="!history.records.length" class="empty-block">
            <p class="empty-block__title">暂无历史病历</p>
            <p>该患者还没有已生成的历史预问诊病历。</p>
          </div>
        </template>
      </template>
    </div>
  </el-drawer>

  <el-dialog v-model="correctVisible" title="修正分诊" width="460px">
    <el-form label-position="top">
      <el-form-item label="修正后科室">
        <el-select v-model="afterDept" placeholder="选择科室" style="width: 100%">
          <el-option v-for="d in depts" :key="d.dept_code" :label="d.dept_name" :value="d.dept_code" />
        </el-select>
      </el-form-item>
      <el-form-item label="修正理由（不少于 10 字）">
        <el-input
          v-model="reason"
          type="textarea"
          :rows="3"
          maxlength="200"
          show-word-limit
          placeholder="例如：患者疼痛位置偏右下腹，需优先排除外科急腹症"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="correctVisible = false">取消</el-button>
      <el-button type="primary" @click="submitCorrect">提交修正</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.session-page {
  width: 100%;
  max-width: 1180px;
  margin: 0 auto;
  padding: 18px 28px 56px;
  animation: page-in 0.4s var(--ease) both;
}

.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 12.5px;
  color: var(--c-muted);
}

.crumb i {
  color: var(--c-line);
  font-style: normal;
}

.crumb__current {
  color: var(--c-ink-soft);
}

.crumb__back {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid var(--c-line);
  border-radius: 9px;
  background: var(--c-surface);
  color: var(--c-primary);
  cursor: pointer;
  margin-right: 2px;
}

.crumb__back svg {
  width: 16px;
  height: 16px;
}

/* ---------- 患者头 ---------- */
.patient-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
  padding: 20px 22px;
  margin-bottom: 16px;
  border: 1px solid var(--c-line);
  border-radius: var(--r-lg);
  background: var(--c-surface);
  box-shadow: var(--shadow-sm);
}

.patient-id {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.patient-avatar {
  width: 48px;
  height: 48px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: linear-gradient(145deg, var(--c-primary), var(--c-primary-strong));
  color: #f3dcc8;
  font-family: var(--font-display);
  font-size: 20px;
}

.patient-id__text h1 {
  font-size: 23px;
  line-height: 1.25;
}

.patient-meta {
  display: flex;
  align-items: center;
  gap: 6px 10px;
  flex-wrap: wrap;
  margin-top: 4px;
  font-size: 12px;
  color: var(--c-muted);
}

.patient-meta span + span::before {
  content: '·';
  margin-right: 8px;
  color: var(--c-faint);
}

.patient-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 4px;
}

.risk-badge {
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(180, 67, 47, 0.1);
  border: 1px solid rgba(180, 67, 47, 0.22);
  color: var(--c-danger);
  font-size: 11.5px;
  font-weight: 500;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-icon {
  width: 15px;
  height: 15px;
  margin-right: 3px;
}

.confirm-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 10px 20px;
  border: 0;
  border-radius: 10px;
  background: linear-gradient(135deg, #c9763c, #b15d2b);
  color: #fff;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  box-shadow: var(--shadow-accent);
  transition: transform 0.15s var(--ease), filter 0.15s var(--ease);
}

.confirm-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.03);
}

.confirm-btn:disabled {
  cursor: not-allowed;
  background: var(--c-line-soft);
  color: var(--c-faint);
  box-shadow: none;
}

.confirm-btn--block {
  width: 100%;
  margin-top: 14px;
}

/* ---------- 两栏 ---------- */
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 16px;
  align-items: start;
}

.main-col {
  min-width: 0;
}

.side-col {
  display: grid;
  gap: 12px;
  position: sticky;
  top: 84px;
}

.tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.tabs :deep(.el-tabs__item) {
  padding: 0 16px;
  height: 38px;
  font-size: 13.5px;
}

.section-label {
  font-size: 11.5px;
  letter-spacing: 0.08em;
  color: var(--c-muted);
  margin-bottom: 8px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

/* ---------- 概览 ---------- */
.complaint-card {
  padding: 20px 22px;
}

.complaint-text {
  font-family: var(--font-display);
  font-size: 19px;
  line-height: 1.75;
  color: var(--c-ink);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px dashed var(--c-line);
}

.info-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.info-cell span {
  font-size: 11px;
  color: var(--c-muted);
}

.info-cell b {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-ink);
}

.guide-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-top: 12px;
  padding: 16px 18px;
  background: rgba(230, 239, 236, 0.55);
  border-color: var(--c-primary-line);
}

.guide-card__icon {
  flex: none;
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid var(--c-primary-line);
  color: var(--c-primary);
  font-family: var(--font-mono);
  font-size: 11px;
}

.guide-card b {
  font-size: 13.5px;
  color: var(--c-primary);
}

.guide-card p {
  margin-top: 3px;
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--c-ink-soft);
}

/* ---------- 对话 ---------- */
.chat-panel {
  padding: 6px 18px;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0 2px;
  border-bottom: 1px solid var(--c-line-soft);
  font-size: 11.5px;
}

.chat-scroll {
  max-height: 62vh;
  overflow-y: auto;
  padding: 12px 0;
}

.chat-row {
  display: flex;
  gap: 10px;
  padding: 8px 0;
}

.chat-row--patient {
  flex-direction: row-reverse;
}

.chat-avatar {
  flex: none;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--c-primary-soft);
  border: 1px solid var(--c-primary-line);
  color: var(--c-primary);
  font-size: 12px;
  font-family: var(--font-display);
}

.chat-row--patient .chat-avatar {
  background: var(--c-accent-soft);
  border-color: #e6cdb5;
  color: var(--c-accent-strong);
}

.chat-body {
  max-width: 74%;
}

.chat-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 11px;
  color: var(--c-muted);
}

.chat-row--patient .chat-meta {
  justify-content: flex-end;
}

.chat-meta b {
  font-weight: 500;
  color: var(--c-ink-soft);
}

.chat-bubble {
  padding: 10px 13px;
  border-radius: 13px;
  background: var(--c-surface-soft);
  border: 1px solid var(--c-line-soft);
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--c-ink);
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-row--ai .chat-bubble {
  border-top-left-radius: 4px;
}

.chat-row--patient .chat-bubble {
  background: var(--c-primary);
  border-color: var(--c-primary);
  color: #fff;
  border-top-right-radius: 4px;
}

.chat-row--system .chat-bubble {
  background: rgba(191, 106, 52, 0.06);
  border-color: rgba(191, 106, 52, 0.18);
  color: var(--c-accent-strong);
  font-size: 12.5px;
}

/* ---------- 病历 ---------- */
.emr-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 20px;
  margin-bottom: 12px;
}

.emr-head__tags {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.completeness {
  width: 200px;
  flex: none;
}

.completeness span {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--c-muted);
  margin-bottom: 5px;
}

.completeness b {
  color: var(--c-primary);
  font-family: var(--font-mono);
}

.bar {
  height: 5px;
  border-radius: 999px;
  background: var(--c-line-soft);
  overflow: hidden;
}

.bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #6fa39b, var(--c-primary));
}

.bar--light {
  background: rgba(255, 255, 255, 0.18);
}

.bar--light i {
  background: linear-gradient(90deg, #f0c9a8, #e0975c);
}

.soap-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.soap-card {
  padding: 16px 18px;
}

.soap-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  margin-bottom: 10px;
  border-bottom: 1px dashed var(--c-line);
}

.soap-letter {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--c-primary-soft);
  border: 1px solid var(--c-primary-line);
  color: var(--c-primary);
  font-family: var(--font-display);
  font-size: 16px;
}

.soap-letter--amber {
  background: var(--c-accent-soft);
  border-color: #e6cdb5;
  color: var(--c-accent-strong);
}

.soap-letter--slate {
  background: #eef0ee;
  border-color: #dfe3df;
  color: #4b5854;
}

.soap-head b {
  display: block;
  font-size: 13.5px;
  color: var(--c-ink);
}

.soap-head em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--c-faint);
}

.soap-label {
  margin-top: 8px;
  font-size: 10.5px;
  letter-spacing: 0.06em;
  color: var(--c-faint);
}

.soap-text {
  margin-top: 2px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--c-ink);
  white-space: pre-wrap;
}

.tag-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 10px;
}

.tag-label {
  font-size: 10.5px;
  color: var(--c-faint);
  margin-right: 2px;
}

.tag {
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--c-line-soft);
  background: var(--c-surface-soft);
  font-size: 11.5px;
  color: var(--c-ink-soft);
}

.tag--warn {
  background: rgba(180, 67, 47, 0.08);
  border-color: rgba(180, 67, 47, 0.2);
  color: var(--c-danger);
}

.tag--dept {
  background: var(--c-primary-soft);
  border-color: var(--c-primary-line);
  color: var(--c-primary);
}

.disclaimer {
  margin-top: 12px;
  padding: 10px 14px;
  border: 1px solid rgba(191, 106, 52, 0.18);
  border-radius: 10px;
  background: rgba(247, 231, 217, 0.35);
  font-size: 11.5px;
  color: #8a5a3a;
}

/* ---------- 鉴别 ---------- */
.candidate-table {
  --el-table-border-color: var(--c-line-soft);
  --el-table-header-bg-color: var(--c-surface-soft);
}

.conf-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.conf-cell .bar {
  flex: 1;
}

.conf-cell span {
  font-size: 11.5px;
  color: var(--c-muted);
  width: 34px;
}

.mdt-card {
  margin-top: 12px;
}

.expand-box {
  padding: 8px 16px 12px 20px;
}

.kg-box {
  padding: 10px 14px;
  background: var(--c-primary-soft);
  border-radius: 10px;
}

.kg-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-primary);
  margin-bottom: 6px;
}

.kg-hits {
  font-weight: 400;
  color: var(--c-muted);
}

.kg-path {
  font-size: 12.5px;
  line-height: 1.85;
  padding-left: 9px;
  border-left: 2px solid var(--c-accent);
  margin-bottom: 4px;
}

.gl-box {
  margin-top: 10px;
  padding: 10px 14px;
  background: #fff8ec;
  border-radius: 10px;
}

.gl-title {
  font-size: 12px;
  font-weight: 600;
  color: #8a5a20;
  margin-bottom: 6px;
}

.gl-item {
  padding: 7px 0;
  border-bottom: 1px dashed var(--c-line);
}

.gl-item:last-child {
  border-bottom: none;
}

.gl-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.gl-pop {
  font-size: 11px;
  color: var(--c-muted);
}

.gl-text {
  font-size: 12.5px;
  line-height: 1.65;
}

.gl-src {
  font-size: 11px;
  color: var(--c-muted);
  margin-top: 2px;
}

/* ---------- 右侧 ---------- */
.side-label {
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--c-muted);
  margin-bottom: 10px;
}

.triage-card {
  padding: 18px;
  background:
    radial-gradient(120% 120% at 100% 0%, rgba(191, 106, 52, 0.12), transparent 55%),
    linear-gradient(150deg, #17504e, #0f3b39);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 22px 44px -28px rgba(15, 59, 57, 0.75);
}

.triage-card .side-label {
  color: #a9c6c2;
}

.triage-dept {
  font-size: 26px;
  line-height: 1.25;
  color: #fff;
}

.triage-conf {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.triage-conf span {
  font-size: 12px;
  color: #d8e7e3;
}

.triage-meta {
  display: flex;
  gap: 18px;
  margin: 14px 0 0;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.14);
}

.triage-meta dt {
  font-size: 10.5px;
  color: #93b3ae;
}

.triage-meta dd {
  margin: 2px 0 0;
  font-size: 13px;
  color: #f2f8f6;
}

.confirmed-note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 14px;
  padding: 9px 12px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 12.5px;
  color: #e8f3f0;
}

.confirmed-note svg {
  width: 15px;
  height: 15px;
}

.info-card {
  padding: 16px 18px;
}

.info-list {
  margin: 0;
  display: grid;
  gap: 9px;
}

.info-list div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.info-list dt {
  font-size: 11.5px;
  color: var(--c-muted);
  flex: none;
}

.info-list dd {
  margin: 0;
  font-size: 12px;
  color: var(--c-ink-soft);
  text-align: right;
  word-break: break-all;
}

.consent-card {
  padding: 16px 18px;
}

.consent-state {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-danger);
}

.consent-state.is-ok {
  color: var(--c-success);
}

.consent-hint {
  margin-top: 6px;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--c-muted);
}

/* ---------- 加载 ---------- */
.loading-block {
  display: grid;
  gap: 14px;
}

.skeleton {
  border-radius: var(--r-lg);
  background: linear-gradient(90deg, var(--c-surface-soft), #fff, var(--c-surface-soft));
  background-size: 200% 100%;
  border: 1px solid var(--c-line-soft);
  animation: shimmer 1.5s linear infinite;
}

.skeleton--head {
  height: 96px;
}

.skeleton--body {
  height: 420px;
}

/* ---------- 历史抽屉 ---------- */
.history-body {
  min-height: 200px;
}

.history-summary {
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--c-muted);
}

.history-item {
  padding: 12px 14px;
  border: 1px solid var(--c-line);
  border-radius: 12px;
  margin-bottom: 9px;
  background: var(--c-surface);
}

.history-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.history-item__head b {
  font-size: 13.5px;
  font-weight: 600;
}

.history-item__meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--c-muted);
}

.consent-empty {
  padding: 28px 10px;
  text-align: center;
}

.consent-empty__icon {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  margin: 0 auto 12px;
  border-radius: 50%;
  background: var(--c-surface-soft);
  border: 1px solid var(--c-line);
  color: var(--c-muted);
}

.consent-empty__icon svg {
  width: 22px;
  height: 22px;
}

.consent-empty p {
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--c-muted);
  margin-top: 6px;
}

@keyframes shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

@media (max-width: 1080px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .side-col {
    position: static;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .triage-card {
    grid-row: span 2;
  }
}

@media (max-width: 760px) {
  .session-page {
    padding: 14px 14px 40px;
  }

  .soap-grid,
  .side-col {
    grid-template-columns: 1fr;
  }

  .info-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .patient-head {
    padding: 16px;
  }

  .patient-meta span + span::before {
    content: none;
  }

  .head-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    width: 100%;
  }

  .head-actions .confirm-btn {
    grid-column: 1 / -1;
    width: 100%;
  }

  .confirm-btn {
    white-space: nowrap;
  }

  .chat-body {
    max-width: 85%;
  }

  .completeness {
    width: 100%;
  }

  .emr-head {
    flex-direction: column;
    align-items: stretch;
  }
}

.drug-safe-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(63, 138, 111, 0.08);
  color: var(--c-success);
  font-size: 12.5px;
}

.drug-safe-empty__icon {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(63, 138, 111, 0.14);
  font-size: 12px;
  font-weight: 700;
}

.drug-section {
  margin-top: 14px;
}

.drug-section__title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
  color: var(--c-ink);
  font-size: 12.5px;
  font-weight: 600;
}

.drug-section__title span {
  color: var(--c-muted);
  font-size: 11px;
  font-weight: 400;
}

.drug-hit {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 6px 14px;
  padding: 11px 13px;
  margin-bottom: 8px;
  border: 1px solid var(--c-line-soft);
  border-left: 3px solid var(--c-danger);
  border-radius: 9px;
  background: var(--c-surface-soft);
}

.drug-hit__main {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
}

.drug-hit__main b {
  color: var(--c-ink);
  font-size: 13px;
  font-weight: 600;
}

.drug-hit__main span {
  color: var(--c-muted);
  font-size: 11.5px;
}

.drug-hit__side {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--c-muted);
  font-size: 11.5px;
  white-space: nowrap;
}

.drug-hit__note {
  grid-column: 1 / -1;
  color: var(--c-faint);
  font-size: 11px;
  line-height: 1.5;
}

.drug-safe-note {
  margin-top: 12px;
  color: var(--c-faint);
  font-size: 11px;
  line-height: 1.65;
}
</style>
