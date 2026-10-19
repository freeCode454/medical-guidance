<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { patients, type Patient } from '@/api/admin'
import EntityDetailDialog from '@/components/EntityDetailDialog.vue'
import type { DetailField } from '@/components/detail'
import { fmtDateTime } from '@/utils/format'

const loading = ref(false)
const items = ref<Patient[]>([])
const page = ref(1)
const size = ref(10)
const total = ref(0)
const keyword = ref('')
const registeredFilter = ref('true')
const detailVisible = ref(false)
const detail = ref<Patient | null>(null)

const detailFields = computed<DetailField[]>(() => {
  const row = detail.value
  if (!row) return []
  return [
    { label: '患者编号', value: row.patient_no || '—', mono: true },
    { label: '登录账号', value: row.account || '匿名患者' },
    { label: '患者类型', value: row.registered ? '已注册' : '匿名患者' },
    { label: '性别', value: row.gender_label },
    { label: '年龄', value: row.age == null ? '—' : `${row.age} 岁` },
    { label: '账号状态', value: row.status === '1' ? '正常' : '停用' },
    { label: '问诊次数', value: row.session_count },
    { label: '预约次数', value: row.appointment_count },
    { label: '注册时间', value: row.create_time ? fmtDateTime(row.create_time) : '—' },
    { label: '最近登录', value: row.last_login_time ? fmtDateTime(row.last_login_time) : '从未登录' },
    { label: '患者 ID', value: row.patient_id, mono: true },
  ]
})

async function load() {
  loading.value = true
  try {
    const d = await patients.list({
      page: page.value,
      size: size.value,
      keyword: keyword.value || null,
      registered: registeredFilter.value || null,
    })
    items.value = d.items
    total.value = d.total
  } catch (e) {
    ElMessage.error((e as Error).message || '加载患者失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function resetFilters() {
  keyword.value = ''
  registeredFilter.value = 'true'
  search()
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

function onView(row: Patient) {
  detail.value = row
  detailVisible.value = true
}

async function onDelete(row: Patient) {
  const name = row.account || row.patient_no || row.patient_id
  try {
    await ElMessageBox.confirm(
      `删除后该患者将无法登录，问诊、预约与病历历史会保留。确定删除「${name}」？`,
      '确认删除患者',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await patients.remove(row.patient_id)
    ElMessage.success('患者已删除')
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message || '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div class="page-title">
        <h1>患者管理</h1>
        <p>查看普通患者账号、问诊与预约情况；删除后患者无法登录，历史数据保留。</p>
      </div>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索患者账号 / 患者编号"
        clearable
        style="width: 240px"
        @keyup.enter="search"
        @clear="search"
      >
        <template #prefix>
          <svg class="search-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.6" />
            <path d="M16 16l4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          </svg>
        </template>
      </el-input>

      <el-select v-model="registeredFilter" placeholder="患者类型" style="width: 140px" @change="search">
        <el-option label="已注册患者" value="true" />
        <el-option label="匿名患者" value="false" />
        <el-option label="全部患者" value="" />
      </el-select>

      <el-button @click="search">查询</el-button>
      <el-button text @click="resetFilters">重置</el-button>
      <span class="result-count">共 <b>{{ total }}</b> 位患者</span>
    </div>

    <section class="table-card" v-loading="loading">
      <el-table :data="items" row-key="patient_id" @row-click="onView">
        <el-table-column label="患者" min-width="220">
          <template #default="{ row }">
            <div class="patient-cell">
              <span class="patient-avatar">{{ (row.account || '匿').slice(0, 1) }}</span>
              <div class="patient-cell__text">
                <b>{{ row.account || '匿名患者' }}</b>
                <em class="mono">{{ row.patient_no || row.patient_id }}</em>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="性别 / 年龄" width="130">
          <template #default="{ row }">
            {{ row.gender_label }}<span v-if="row.age != null"> · {{ row.age }} 岁</span>
          </template>
        </el-table-column>
        <el-table-column label="问诊" width="90">
          <template #default="{ row }"><span class="tnum">{{ row.session_count }}</span> 次</template>
        </el-table-column>
        <el-table-column label="预约" width="90">
          <template #default="{ row }"><span class="tnum">{{ row.appointment_count }}</span> 次</template>
        </el-table-column>
        <el-table-column label="注册时间" width="160">
          <template #default="{ row }">
            <span class="muted">{{ row.create_time ? fmtDateTime(row.create_time) : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" width="160">
          <template #default="{ row }">
            <span class="muted">{{ row.last_login_time ? fmtDateTime(row.last_login_time) : '从未登录' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="onView(row)">查看</el-button>
            <el-button link type="danger" size="small" @click.stop="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-block">
            <p class="empty-block__title">没有匹配的患者</p>
            <p>试试更换关键词，或切换“已注册 / 匿名 / 全部”。</p>
            <el-button @click="resetFilters">重置筛选</el-button>
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

    <EntityDetailDialog
      v-model="detailVisible"
      :title="detail ? (detail.account || '患者详情') : '患者详情'"
      :subtitle="detail ? (detail.patient_no || detail.patient_id) : ''"
      badge="患"
      :fields="detailFields"
    />
  </div>
</template>

<style scoped>
.table-card :deep(.el-table__row) {
  cursor: pointer;
}

.table-card :deep(.el-table__row:hover > td) {
  background: var(--c-surface-soft) !important;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.search-icon {
  width: 15px;
  height: 15px;
  color: var(--c-faint);
}

.result-count {
  margin-left: auto;
  font-size: 12px;
  color: var(--c-muted);
}

.result-count b {
  color: var(--c-primary);
  font-family: var(--font-display);
  font-size: 14px;
}

.patient-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.patient-avatar {
  width: 32px;
  height: 32px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--c-primary-soft);
  border: 1px solid var(--c-primary-line);
  color: var(--c-primary);
  font-family: var(--font-display);
  font-size: 14px;
}

.patient-cell__text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.patient-cell__text b {
  font-size: 13px;
  font-weight: 500;
  color: var(--c-ink);
}

.patient-cell__text em {
  font-style: normal;
  font-size: 11px;
  color: var(--c-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono {
  font-family: var(--font-mono);
}

.muted {
  color: var(--c-muted);
  font-size: 12px;
}

.tnum {
  font-family: var(--font-mono);
  color: var(--c-ink);
}
</style>
