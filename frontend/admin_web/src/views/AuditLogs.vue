<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { audits, type AuditItem } from '@/api/admin'
import { fmtDateTime } from '@/utils/format'

const loading = ref(false)
const items = ref<AuditItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const actionType = ref('')

const actionLabels: Record<string, string> = {
  EMR_READ: '病历读取',
  EXTERNAL_CALL: '外部调用',
  TRIAGE_CONFIRM: '确认分诊',
  TRIAGE_CORRECT: '修正分诊',
  PERM_CHANGE: '权限变更',
  KB_CHANGE: '知识库变更',
  EGRESS_BLOCK: '出域拦截',
  EGRESS_DEV: '开发出域放行',
  DATA_ARCHIVE: '数据归档',
}

const roleLabels: Record<string, string> = {
  DOCTOR: '医生',
  ORG_ADMIN: '机构管理员',
  KB_ADMIN: '知识库管理员',
  PATIENT: '患者',
}

async function load() {
  loading.value = true
  try {
    const d = await audits.list({
      page: page.value,
      size: size.value,
      action_type: actionType.value || null,
    })
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
  void load()
}

function onSizeChange(s: number) {
  size.value = s
  page.value = 1
  void load()
}

function onFilter() {
  page.value = 1
  void load()
}

function detailText(detail: unknown) {
  if (detail == null) return '—'
  try {
    return JSON.stringify(detail, null, 2)
  } catch {
    return String(detail)
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div class="page-title">
        <h1>审计日志</h1>
        <p>敏感读取、分诊确认/修正、出域调用与权限变更均会留痕，只追加不可修改。</p>
      </div>
      <div class="page-actions">
        <span class="result-count">共 <b>{{ total }}</b> 条记录</span>
      </div>
    </div>

    <div class="filter-bar">
      <el-select v-model="actionType" placeholder="全部动作" clearable style="width: 170px" @change="onFilter">
        <el-option v-for="(label, value) in actionLabels" :key="value" :label="label" :value="value" />
      </el-select>
      <el-button @click="load">刷新</el-button>
      <span class="filter-hint">按时间倒序，展开行可看完整 detail</span>
    </div>

    <section class="table-card" v-loading="loading">
      <el-table :data="items" row-key="audit_id">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="detail-box">
              <p class="detail-title">操作详情</p>
              <pre>{{ detailText(row.detail) }}</pre>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="动作" width="150">
          <template #default="{ row }">
            <span class="action">
              <i :class="{ 'is-danger': row.result !== 'SUCCESS' }" aria-hidden="true" />
              {{ actionLabels[row.action_type] || row.action_type }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作者" width="130">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ roleLabels[row.actor_role] || row.actor_role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_type" label="对象" width="120" />
        <el-table-column label="结果" width="100">
          <template #default="{ row }">
            <el-tag :type="row.result === 'SUCCESS' ? 'success' : 'danger'" size="small" effect="light">
              {{ row.result === 'SUCCESS' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="摘要" min-width="220">
          <template #default="{ row }">
            <span class="muted summary">{{ row.detail ? JSON.stringify(row.detail) : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">
            <span class="muted">{{ fmtDateTime(row.action_time) }}</span>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-block">
            <p class="empty-block__title">暂无审计记录</p>
            <p>医生调阅病历、确认或修正分诊后，日志会出现在这里。</p>
          </div>
        </template>
      </el-table>

      <div v-if="total > size" class="table-foot">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.result-count {
  font-size: 12px;
  color: var(--c-muted);
}

.result-count b {
  color: var(--c-primary);
  font-family: var(--font-display);
  font-size: 15px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.filter-hint {
  margin-left: auto;
  font-size: 11.5px;
  color: var(--c-faint);
}

.action {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: var(--c-ink);
}

.action i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-success);
}

.action i.is-danger {
  background: var(--c-danger);
}

.summary {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 12px;
}

.detail-box {
  padding: 10px 16px 14px 48px;
}

.detail-title {
  font-size: 11.5px;
  letter-spacing: 0.06em;
  color: var(--c-muted);
  margin-bottom: 6px;
}

.detail-box pre {
  margin: 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--c-surface-soft);
  border: 1px solid var(--c-line-soft);
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--c-ink-soft);
  overflow-x: auto;
}
</style>
