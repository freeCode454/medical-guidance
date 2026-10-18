<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppHeader from '@/components/AppHeader.vue'
import { listTakeoverQueue, takeover, type EncounterItem } from '@/api/doctor'
import { fmtTime } from '@/utils/format'

const router = useRouter()
const loading = ref(false)
const items = ref<EncounterItem[]>([])
const page = ref(1)
const size = ref(10)
const total = ref(0)
const claiming = ref('')

async function load() {
  loading.value = true
  try {
    const d = await listTakeoverQueue(page.value, size.value)
    items.value = d.items
    total.value = d.total
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

function waiting(started: string | null): string {
  if (!started) return '—'
  const diff = Date.now() - new Date(started).getTime()
  if (Number.isNaN(diff)) return '—'
  const minutes = Math.max(0, Math.round(diff / 60000))
  if (minutes < 60) return `${minutes} 分钟`
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`
}

function onPageChange(p: number) {
  page.value = p
  load()
}

function onSizeChange(s: number) {
  size.value = s
  page.value = 1
  load()
}

async function onTakeover(row: EncounterItem) {
  claiming.value = row.session_id
  try {
    await takeover(row.session_id)
    ElMessage.success('已接管，正在打开会话')
    router.push(`/session/${row.session_id}`)
  } catch (e) {
    ElMessage.error((e as Error).message || '接管失败')
  } finally {
    claiming.value = ''
  }
}

onMounted(load)
</script>

<template>
  <AppHeader />
  <main class="page">
    <div class="page-head">
      <div class="page-title">
        <h1>待接管队列</h1>
        <p>按等待时长排序，接管后进入您的今日接诊</p>
      </div>
      <div class="page-actions">
        <span class="wait-chip"><b>{{ total }}</b> 位等待接诊</span>
        <el-button @click="load">刷新</el-button>
        <el-button @click="router.push('/')">返回今日接诊</el-button>
      </div>
    </div>

    <div v-loading="loading" class="queue">
      <article
        v-for="row in items"
        :key="row.session_id"
        class="queue-item"
        :class="{ 'is-risk': row.risk_flag }"
      >
        <div class="q-patient">
          <span class="q-avatar">{{ row.patient_display.slice(0, 1) }}</span>
          <div class="q-patient__text">
            <b>{{ row.patient_display }}</b>
            <em class="mono">{{ row.session_no }}</em>
          </div>
        </div>

        <p class="q-complaint">{{ row.chief_complaint || '患者尚未描述症状' }}</p>

        <div class="q-meta">
          <span v-if="row.risk_flag" class="q-risk">高危</span>
          <span class="q-meta__item">追问 {{ row.inquiry_rounds }} 轮</span>
          <span class="q-meta__item">等待 {{ waiting(row.started_time) }}</span>
          <span class="q-meta__item">提交于 {{ fmtTime(row.started_time) }}</span>
        </div>

        <el-button
          type="primary"
          class="q-claim"
          :loading="claiming === row.session_id"
          @click="onTakeover(row)"
        >
          接管并接诊
        </el-button>
      </article>

      <div v-if="!loading && !items.length" class="empty-block queue-empty">
        <div class="queue-empty__icon" aria-hidden="true">
          <svg viewBox="0 0 64 64" fill="none">
            <path d="M16 20h32v24H16z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
            <path d="M22 28h20M22 35h12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            <path d="M26 52h12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
        </div>
        <p class="empty-block__title">暂时没有待接管患者</p>
        <p>新的预问诊完成后会自动进入这里，也可以回到今日接诊查看已认领患者。</p>
        <el-button @click="router.push('/')">返回今日接诊</el-button>
      </div>
    </div>

    <div v-if="total > size" class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>
  </main>
</template>

<style scoped>
.wait-chip {
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

.wait-chip b {
  font-family: var(--font-display);
  font-size: 15px;
  color: var(--c-accent-strong);
}

.queue {
  display: grid;
  gap: 10px;
  min-height: 120px;
}

.queue-item {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr) auto;
  grid-template-areas:
    'patient complaint claim'
    'patient meta claim';
  gap: 6px 20px;
  align-items: center;
  padding: 16px 18px;
  background: var(--c-surface);
  border: 1px solid var(--c-line);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-xs);
  transition: border-color 0.18s var(--ease), box-shadow 0.18s var(--ease), transform 0.18s var(--ease);
}

.queue-item:hover {
  border-color: var(--c-primary-line);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.queue-item.is-risk {
  border-left: 3px solid var(--c-danger);
}

.q-patient {
  grid-area: patient;
  display: flex;
  align-items: center;
  gap: 10px;
}

.q-avatar {
  width: 36px;
  height: 36px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: var(--c-primary-soft);
  border: 1px solid var(--c-primary-line);
  color: var(--c-primary);
  font-family: var(--font-display);
  font-size: 15px;
}

.q-patient__text {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.q-patient__text b {
  font-size: 14px;
  font-weight: 600;
}

.q-patient__text em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--c-faint);
}

.q-complaint {
  grid-area: complaint;
  font-size: 14px;
  color: var(--c-ink-soft);
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.q-meta {
  grid-area: meta;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 11.5px;
  color: var(--c-muted);
}

.q-risk {
  padding: 1px 7px;
  border-radius: 5px;
  background: rgba(180, 67, 47, 0.1);
  border: 1px solid rgba(180, 67, 47, 0.22);
  color: var(--c-danger);
  font-weight: 500;
}

.q-meta__item {
  position: relative;
}

.q-meta__item + .q-meta__item::before {
  content: '';
  position: absolute;
  left: -7px;
  top: 50%;
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: var(--c-faint);
}

.q-claim {
  grid-area: claim;
  align-self: center;
}

.queue-empty {
  background: var(--c-surface);
  border: 1px dashed var(--c-line);
  border-radius: var(--r-lg);
}

.queue-empty__icon {
  width: 56px;
  height: 56px;
  margin: 0 auto 12px;
  color: var(--c-primary-line);
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

@media (max-width: 860px) {
  .queue-item {
    grid-template-columns: 1fr auto;
    grid-template-areas:
      'patient claim'
      'complaint complaint'
      'meta meta';
    gap: 10px;
  }

  .q-complaint {
    white-space: normal;
  }
}
</style>
