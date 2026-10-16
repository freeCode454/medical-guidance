<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppHeader from '@/components/AppHeader.vue'
import { listEncounters, type EncounterItem } from '@/api/doctor'

const router = useRouter()
const loading = ref(false)
const items = ref<EncounterItem[]>([])
const total = ref(0)
const status = ref('')

const statusMap: Record<string, { label: string; type: string }> = {
  IN_PROGRESS: { label: '问诊中', type: 'info' },
  FINISHED: { label: '已出结论', type: 'success' },
  PENDING_TAKEOVER: { label: '待接管', type: 'warning' },
  TAKEN_OVER: { label: '已接管', type: 'primary' },
  CLOSED: { label: '已结束', type: 'info' },
  EMERGENCY: { label: '急诊', type: 'danger' },
}

async function load() {
  loading.value = true
  try {
    const d = await listEncounters({ status: status.value || null })
    items.value = d.items
    total.value = d.total
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <AppHeader />
  <main class="page">
    <div class="page-head">
      <h1>今日接诊</h1>
      <span class="count">共 {{ total }} 位患者</span>
      <el-select v-model="status" placeholder="全部状态" clearable style="width: 140px; margin-left: auto" @change="load">
        <el-option v-for="(v, k) in statusMap" :key="k" :label="v.label" :value="k" />
      </el-select>
    </div>

    <el-table :data="items" v-loading="loading" @row-click="(row: EncounterItem) => router.push(`/session/${row.session_id}`)">
      <el-table-column prop="patient_display" label="患者" width="140" />
      <el-table-column prop="chief_complaint" label="主诉" min-width="220" show-overflow-tooltip />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusMap[row.status]?.type || 'info'" size="small">
            {{ statusMap[row.status]?.label || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="风险" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.risk_flag" type="danger" size="small">高危</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="inquiry_rounds" label="追问轮次" width="90" />
      <el-table-column label="开始时间" width="100">
        <template #default="{ row }">{{ row.started_time ? row.started_time.slice(11, 16) : '' }}</template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !items.length" description="今日暂无接诊记录" />
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
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}

h1 {
  font-size: 22px;
}

.count {
  color: var(--c-muted);
  font-size: 14px;
}

.muted {
  color: var(--c-muted);
}

:deep(.el-table__row) {
  cursor: pointer;
}
</style>
