<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppHeader from '@/components/AppHeader.vue'
import {
  getSession, listMessages, getEmr, getDiagnosis,
  confirmTriage, correctTriage, listDepts, type SessionDetail, type EmrDoc, type Diagnosis,
} from '@/api/doctor'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.id as string
const activeTab = ref('overview')

const session = ref<SessionDetail | null>(null)
const messages = ref<any[]>([])
const emr = ref<EmrDoc | null>(null)
const diagnosis = ref<Diagnosis | null>(null)
const depts = ref<Array<{ dept_code: string; dept_name: string }>>([])
const loading = ref(true)

// 修正分诊弹窗
const correctVisible = ref(false)
const afterDept = ref('')
const reason = ref('')

function pct(n: number) {
  return Math.round(n * 100) + '%'
}

async function load() {
  loading.value = true
  try {
    ;[session.value, messages.value] = await Promise.all([
      getSession(sessionId),
      listMessages(sessionId).then((d) => d.items),
    ])
    try { emr.value = await getEmr(sessionId) } catch { emr.value = null }
    try { diagnosis.value = await getDiagnosis(sessionId) } catch { diagnosis.value = null }
    depts.value = await listDepts()
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function onConfirm() {
  try {
    await ElMessageBox.confirm('确认将患者分诊到系统建议科室？', '确认分诊')
    await confirmTriage(sessionId)
    ElMessage.success('已确认分诊')
    load()
  } catch { /* 取消 */ }
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
    ElMessage.success('修正已记录')
    correctVisible.value = false
    load()
  } catch (e) {
    ElMessage.error((e as Error).message || '修正失败')
  }
}

onMounted(load)
</script>

<template>
  <AppHeader />
  <main class="page" v-loading="loading">
    <div class="page-head" v-if="session">
      <div>
        <h1>{{ session.patient.patient_display }}</h1>
        <p class="meta">
          {{ session.patient.gender || '未知' }} · {{ session.patient.age ?? '年龄未知' }}
          · 会话号 {{ session.session_no }}
          <el-tag v-if="session.risk_flag" type="danger" size="small">高危</el-tag>
        </p>
      </div>
      <div class="actions">
        <el-button type="primary" :disabled="session.triage_status.doctor_confirmed" @click="onConfirm">
          {{ session.triage_status.doctor_confirmed ? '已确认' : '确认分诊' }}
        </el-button>
        <el-button @click="openCorrect">修正分诊</el-button>
        <el-button text @click="router.back()">返回</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="概览" name="overview">
        <el-card v-if="session" shadow="never">
          <h3>主诉</h3>
          <p class="body">{{ session.chief_complaint || '—' }}</p>
          <el-divider />
          <h3>分诊状态</h3>
          <p class="body">
            路由：<b>{{ session.triage_status.route || '—' }}</b>
            · 追问轮次：{{ session.inquiry_rounds }}
            · 医生确认：{{ session.triage_status.doctor_confirmed ? '是' : '否' }}
          </p>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="对话记录" name="messages">
        <el-card shadow="never">
          <div v-for="m in messages" :key="m.message_id" class="msg" :class="m.role === 'PATIENT' ? 'mine' : 'ai'">
            <span class="role">{{ m.role === 'PATIENT' ? '患者' : m.role === 'AI' ? 'AI' : m.role }}</span>
            <span class="content">{{ m.content }}</span>
          </div>
          <el-empty v-if="!messages.length" description="暂无对话" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="预问诊病历" name="emr">
        <el-card v-if="emr" shadow="never">
          <h3>S 主观资料</h3>
          <p class="body">{{ emr.subjective.chief_complaint || '—' }}</p>
          <el-divider />
          <h3>O 客观资料</h3>
          <p class="body">{{ emr.objective.note || '—' }}</p>
          <el-divider />
          <h3>A 评估（鉴别方向）</h3>
          <p v-if="emr.assessment?.differential_directions?.length" class="body">
            <el-tag v-for="d in emr.assessment.differential_directions" :key="d.dept_code" class="mr8" type="info">
              {{ d.dept_code }} {{ pct(d.confidence) }}
            </el-tag>
          </p>
          <p v-else class="body muted">—</p>
          <el-divider />
          <h3>P 计划</h3>
          <p class="body">
            <el-tag v-for="d in emr.plan.recommended_depts" :key="d" class="mr8">{{ d }}</el-tag>
          </p>
          <el-divider />
          <p class="disclaimer">{{ emr.disclaimer }}</p>
        </el-card>
        <el-empty v-else description="病历尚未生成" />
      </el-tab-pane>

      <el-tab-pane label="鉴别诊断" name="diagnosis">
        <template v-if="diagnosis">
          <el-card shadow="never" class="mb">
            <h3>候选科室</h3>
            <el-table :data="diagnosis.candidates" size="small">
              <el-table-column type="expand">
                <template #default="{ row }">
                  <div class="kg-box">
                    <p class="kg-title">
                      知识图谱推理路径
                      <span v-if="row.kg_disease_hits" class="kg-hits">（{{ row.kg_disease_hits }} 个疾病命中）</span>
                    </p>
                    <div v-for="p in row.kg_paths" :key="p" class="kg-path">{{ p }}</div>
                    <p v-if="!row.kg_paths || !row.kg_paths.length" class="muted">该科室暂无图谱路径</p>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="rank" label="#" width="50" />
              <el-table-column prop="dept_name" label="科室" width="140" />
              <el-table-column label="置信度" width="100">
                <template #default="{ row }">{{ pct(row.confidence) }}</template>
              </el-table-column>
              <el-table-column label="命中症状" min-width="160">
                <template #default="{ row }">{{ row.hit_symptoms.join('、') || '依据不足' }}</template>
              </el-table-column>
              <el-table-column label="图谱" width="90">
                <template #default="{ row }">
                  <el-tag v-if="row.kg_paths && row.kg_paths.length" size="small" type="success">有路径</el-tag>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card v-if="diagnosis.mdt?.triggered" shadow="never" class="mb">
            <h3>多学科会诊（MDT）</h3>
            <p class="body">
              共识科室：<b>{{ diagnosis.mdt.consensus_dept }}</b>
              · 置信度 {{ pct(diagnosis.mdt.consensus_confidence) }}
              <el-tag v-if="diagnosis.mdt.divergence.exists" type="warning" size="small">存在分歧</el-tag>
            </p>
            <el-alert
              v-if="diagnosis.mdt.divergence.exists"
              type="warning"
              :closable="false"
              title="各专科意见不一致，请关注分歧区块"
              class="mt"
            />
          </el-card>

          <el-card shadow="never">
            <h3>用药禁忌校验</h3>
            <el-alert
              v-if="!diagnosis.drug_safety.checked"
              type="warning"
              :closable="false"
              :title="diagnosis.drug_safety.note"
            />
            <p v-else class="body muted">{{ diagnosis.drug_safety.note }}</p>
          </el-card>
        </template>
        <el-empty v-else description="分诊结论尚未生成" />
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="correctVisible" title="修正分诊" width="440px">
      <el-form label-width="90px">
        <el-form-item label="修正后科室">
          <el-select v-model="afterDept" placeholder="选择科室" style="width: 100%">
            <el-option v-for="d in depts" :key="d.dept_code" :label="d.dept_name" :value="d.dept_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="修正理由">
          <el-input v-model="reason" type="textarea" :rows="3" placeholder="不少于 10 字，例如：患者疼痛位置偏右下腹，需优先排除外科急腹症" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="correctVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCorrect">提交修正</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<style scoped>
.page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

h1 {
  font-size: 24px;
}

.meta {
  color: var(--c-muted);
  font-size: 13px;
  margin: 6px 0 0;
}

.actions {
  display: flex;
  gap: 8px;
}

h3 {
  font-size: 15px;
  margin-bottom: 8px;
}

.body {
  margin: 0;
  line-height: 1.8;
}

.disclaimer {
  color: var(--c-muted);
  font-size: 12px;
  margin: 0;
}

.msg {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--c-line);
}

.msg.mine .role {
  color: var(--c-primary);
}

.msg.ai .role {
  color: var(--c-accent);
}

.role {
  font-size: 12px;
  width: 44px;
  flex-shrink: 0;
  padding-top: 2px;
}

.content {
  flex: 1;
  line-height: 1.7;
}

.muted { color: var(--c-muted); }

.kg-box {
  padding: 8px 16px 10px 20px;
  background: var(--c-primary-soft);
  border-radius: 6px;
}

.kg-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-primary);
  margin: 0 0 6px;
}

.kg-hits {
  font-weight: 400;
  color: var(--c-muted);
}

.kg-path {
  font-size: 13px;
  color: var(--c-ink);
  line-height: 1.9;
  padding-left: 10px;
  border-left: 2px solid var(--c-accent);
  margin-bottom: 4px;
}
.mb { margin-bottom: 14px; }
.mt { margin-top: 12px; }
.mr8 { margin-right: 8px; }
</style>
