<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppHeader from '@/components/AppHeader.vue'
import { listTakeoverQueue, takeover, type EncounterItem } from '@/api/doctor'

const router = useRouter()
const loading = ref(false)
const items = ref<EncounterItem[]>([])
const page = ref(1)
const size = ref(20)
const total = ref(0)

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
      <span class="count">共 {{ total }} 位患者等待接诊</span>
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

    <div class="pager">
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
.pager { display: flex; justify-content: flex-end; margin-top: 14px; }
</style>
