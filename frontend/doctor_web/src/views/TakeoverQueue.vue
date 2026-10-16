<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppHeader from '@/components/AppHeader.vue'
import { listTakeoverQueue, takeover, type EncounterItem } from '@/api/doctor'

const router = useRouter()
const loading = ref(false)
const items = ref<EncounterItem[]>([])

async function load() {
  loading.value = true
  try {
    const d = await listTakeoverQueue()
    items.value = d.items
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function onTakeover(row: EncounterItem) {
  try {
    await takeover(row.session_id)
    ElMessage.success('已接管，请开始接诊')
    router.push(`/session/${row.session_id}`)
  } catch (e) {
    ElMessage.error((e as Error).message || '接管失败')
  }
}

onMounted(load)
</script>

<template>
  <AppHeader />
  <main class="page">
    <div class="page-head">
      <h1>待接管队列</h1>
      <span class="count">共 {{ items.length }} 位患者等待接诊</span>
    </div>

    <el-table :data="items" v-loading="loading">
      <el-table-column prop="patient_display" label="患者" width="140" />
      <el-table-column prop="chief_complaint" label="主诉" min-width="220" show-overflow-tooltip />
      <el-table-column label="风险" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.risk_flag" type="danger" size="small">高危</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="inquiry_rounds" label="追问轮次" width="90" />
      <el-table-column label="操作" width="110">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="onTakeover(row)">接管</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !items.length" description="暂无待接管患者" />
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

h1 { font-size: 22px; }
.count { color: var(--c-muted); font-size: 14px; }
.muted { color: var(--c-muted); }
</style>
