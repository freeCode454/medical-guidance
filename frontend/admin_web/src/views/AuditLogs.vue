<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { audits, type AuditItem } from '@/api/admin'

const loading = ref(false)
const items = ref<AuditItem[]>([])
const total = ref(0)
const page = ref(1)
const actionType = ref('')

const actionLabels: Record<string, string> = {
  EMR_READ: '病历读取', EXTERNAL_CALL: '外部调用', TRIAGE_CONFIRM: '确认分诊',
  TRIAGE_CORRECT: '修正分诊', PERM_CHANGE: '权限变更', KB_CHANGE: '知识库变更',
  EGRESS_BLOCK: '出域拦截', DATA_ARCHIVE: '数据归档',
}

async function load() {
  loading.value = true
  try {
    const d = await audits.list({ page: page.value, action_type: actionType.value || null })
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
  <div>
    <div class="head">
      <h2>审计日志</h2>
      <el-select v-model="actionType" placeholder="全部动作" clearable style="width: 160px" @change="load">
        <el-option v-for="(l, v) in actionLabels" :key="v" :label="l" :value="v" />
      </el-select>
    </div>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="动作" width="130">
        <template #default="{ row }">{{ actionLabels[row.action_type] || row.action_type }}</template>
      </el-table-column>
      <el-table-column prop="actor_role" label="角色" width="110" />
      <el-table-column prop="target_type" label="对象类型" width="130" />
      <el-table-column label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="row.result === 'SUCCESS' ? 'success' : 'danger'" size="small">{{ row.result }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="详情" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ JSON.stringify(row.detail) }}</template>
      </el-table-column>
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ row.action_time ? row.action_time.replace('T', ' ').slice(0, 19) : '' }}</template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      :total="total"
      :page-size="20"
      layout="total, prev, pager, next"
      class="mt pager"
      @current-change="load"
    />
  </div>
</template>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
h2 { font-size: 18px; }
.mt { margin-top: 16px; }
.pager { justify-content: center; }
</style>
