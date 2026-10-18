<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppHeader from '@/components/AppHeader.vue'
import { listEncounters, type EncounterItem } from '@/api/doctor'
import { fmtTime } from '@/utils/format'

const router = useRouter()
const loading = ref(false)
const items = ref<EncounterItem[]>([])
const total = ref(0)
const status = ref('')
const page = ref(1)
const size = ref(10)

const statusMap: Record<string, { label: string; type: 'info' | 'success' | 'warning' | 'danger' | 'primary' }> = {
  IN_PROGRESS: { label: '问诊中', type: 'info' },
  FINISHED: { label: '已出结论', type: 'success' },
  PENDING_TAKEOVER: { label: '待接管', type: 'warning' },
  TAKEN_OVER: { label: '已接管', type: 'primary' },
  CLOSED: { label: '已结束', type: 'info' },
  EMERGENCY: { label: '急诊', type: 'danger' },
}

const filters = [
  { value: '', label: '全部' },
  { value: 'TAKEN_OVER', label: '已接管' },
  { value: 'PENDING_TAKEOVER', label: '待接管' },
  { value: 'IN_PROGRESS', label: '问诊中' },
  { value: 'EMERGENCY', label: '急诊' },
]

const today = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  month: 'long',
  day: 'numeric',
  weekday: 'long',
}).format(new Date())

const riskCount = computed(() => items.value.filter((item) => item.risk_flag).length)

const emptyDescription = computed(() =>
  status.value ? '当前筛选下没有接诊记录' : '今天还没有接诊记录，去待接管队列认领患者',
)

async function load() {
  loading.value = true
  try {
    const d = await listEncounters({
      status: status.value || null,
      page: page.value,
      size: size.value,
    })
    items.value = d.items
    total.value = d.total
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

function changePage(next: number) {
  page.value = next
  void load()
}

function changeFilter(value: string) {
  status.value = value
  page.value = 1
  void load()
}

function openSession(row: EncounterItem) {
  router.push(`/session/${row.session_id}`)
}

onMounted(load)
</script>

<template>
  <AppHeader />
  <main class="page">
    <div class="page-head">
      <div class="page-title">
        <h1>今日接诊</h1>
        <p>{{ today }} · 只显示您已接管或问诊中的患者</p>
      </div>
      <div class="page-actions">
        <span class="total-chip">共 <b>{{ total }}</b> 位</span>
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="router.push('/takeover')">待接管队列</el-button>
      </div>
    </div>

    <div class="filter-bar">
      <button
        v-for="f in filters"
        :key="f.value"
        type="button"
        class="filter-chip"
        :class="{ 'is-active': status === f.value }"
        @click="changeFilter(f.value)"
      >
        {{ f.label }}
      </button>
      <span v-if="riskCount" class="risk-note">
        <i aria-hidden="true" />本页 {{ riskCount }} 位高危
      </span>
    </div>

    <section class="table-card" v-loading="loading">
      <el-table
        :data="items"
        row-key="session_id"
        :show-header="!!items.length"
        @row-click="openSession"
      >
        <el-table-column label="患者" width="190">
          <template #default="{ row }">
            <div class="patient">
              <span class="patient__avatar">{{ row.patient_display.slice(0, 1) }}</span>
              <span class="patient__text">
                <b>{{ row.patient_display }}</b>
                <em class="mono">{{ row.session_no }}</em>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="主诉" min-width="260">
          <template #default="{ row }">
            <span class="complaint">{{ row.chief_complaint || '患者尚未描述症状' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type || 'info'" size="small" effect="light">
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="86">
          <template #default="{ row }">
            <span v-if="row.risk_flag" class="risk-badge">高危</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="inquiry_rounds" label="追问" width="76" />
        <el-table-column label="开始时间" width="96">
          <template #default="{ row }">
            <span class="mono time">{{ fmtTime(row.started_time) }}</span>
          </template>
        </el-table-column>
        <el-table-column width="52">
          <template #default>
            <span class="row-arrow" aria-hidden="true">→</span>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-block">
            <div class="empty-illustration" aria-hidden="true">
              <svg viewBox="0 0 64 64" fill="none">
                <rect x="12" y="14" width="40" height="38" rx="8" stroke="currentColor" stroke-width="2" />
                <path d="M12 26h40" stroke="currentColor" stroke-width="2" />
                <path d="M22 36h12M22 43h20" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                <circle cx="45" cy="20" r="3" fill="currentColor" />
              </svg>
            </div>
            <p class="empty-block__title">{{ emptyDescription }}</p>
            <p>接诊后患者会出现在这里，分诊结论与预问诊病历可直接查看。</p>
            <el-button @click="router.push('/takeover')">去认领患者</el-button>
          </div>
        </template>
      </el-table>

      <div v-if="total > size" class="table-foot">
        <el-pagination
          layout="prev, pager, next"
          :total="total"
          :page-size="size"
          :current-page="page"
          @current-change="changePage"
        />
      </div>
    </section>
  </main>
</template>

<style scoped>
.total-chip {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid var(--c-line);
  border-radius: 999px;
  background: var(--c-surface);
  color: var(--c-muted);
  font-size: 12px;
}

.total-chip b {
  color: var(--c-primary);
  font-size: 15px;
  font-family: var(--font-display);
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.filter-chip {
  border: 1px solid transparent;
  background: transparent;
  color: var(--c-muted);
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12.5px;
  cursor: pointer;
  transition: background 0.18s var(--ease), color 0.18s var(--ease), border-color 0.18s var(--ease);
}

.filter-chip:hover {
  color: var(--c-primary);
  background: var(--c-primary-soft);
}

.filter-chip.is-active {
  color: var(--c-primary);
  background: var(--c-surface);
  border-color: var(--c-primary-line);
  box-shadow: var(--shadow-xs);
}

.risk-note {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 12px;
  color: var(--c-accent-strong);
}

.risk-note i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-accent);
}

.patient {
  display: flex;
  align-items: center;
  gap: 10px;
}

.patient__avatar {
  width: 32px;
  height: 32px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--c-primary-soft);
  border: 1px solid var(--c-primary-line);
  color: var(--c-primary);
  font-family: var(--font-display);
  font-size: 14px;
}

.patient__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.patient__text b {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--c-ink);
}

.patient__text em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--c-faint);
}

.complaint {
  color: var(--c-ink-soft);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.risk-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(180, 67, 47, 0.1);
  border: 1px solid rgba(180, 67, 47, 0.22);
  color: var(--c-danger);
  font-size: 11.5px;
  font-weight: 500;
}

.time {
  color: var(--c-muted);
  font-size: 12px;
}

.row-arrow {
  color: var(--c-faint);
  opacity: 0;
  transition: opacity 0.18s ease, transform 0.18s ease;
  display: inline-block;
}

:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-table__row:hover) .row-arrow {
  opacity: 1;
  transform: translateX(2px);
  color: var(--c-primary);
}

.table-foot {
  display: flex;
  justify-content: flex-end;
  padding: 10px 14px;
  border-top: 1px solid var(--c-line-soft);
  background: var(--c-surface);
}

.empty-illustration {
  width: 58px;
  height: 58px;
  margin: 0 auto 12px;
  color: var(--c-primary-line);
}
</style>
