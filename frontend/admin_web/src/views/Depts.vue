<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { depts, type Dept } from '@/api/admin'
import EntityDetailDialog from '@/components/EntityDetailDialog.vue'
import type { DetailField } from '@/components/detail'

const loading = ref(false)
const items = ref<Dept[]>([])
const dialog = ref(false)
const saving = ref(false)
const editingId = ref('')
const formRef = ref<FormInstance>()
const page = ref(1)
const size = ref(10)
const total = ref(0)
const keyword = ref('')
const statusFilter = ref('')

const form = reactive({ dept_code: '', dept_name: '', sort_no: 0 })
const detailVisible = ref(false)
const detail = ref<Dept | null>(null)

const detailFields = computed<DetailField[]>(() => {
  const row = detail.value
  if (!row) return []
  return [
    { label: '科室编码', value: row.dept_code, mono: true },
    { label: '科室名称', value: row.dept_name },
    { label: '排序号', value: row.sort_no },
    { label: '状态', value: row.status === '1' ? '启用' : '停用' },
    { label: '科室 ID', value: row.dept_id, mono: true },
  ]
})

const rules = computed<FormRules>(() => ({
  dept_code: [{ required: true, message: '请输入科室编码', trigger: 'blur' }],
  dept_name: [{ required: true, message: '请输入科室名称', trigger: 'blur' }],
  sort_no: [{ required: true, message: '请输入排序号', trigger: 'change' }],
}))

async function load() {
  loading.value = true
  try {
    const d = await depts.list({
      page: page.value,
      size: size.value,
      keyword: keyword.value || null,
      status: statusFilter.value || null,
    })
    items.value = d.items
    total.value = d.total
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
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
  statusFilter.value = ''
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

function onView(row: Dept) {
  detail.value = row
  detailVisible.value = true
}

function resetForm() {
  editingId.value = ''
  Object.assign(form, { dept_code: '', dept_name: '', sort_no: 0 })
  formRef.value?.clearValidate()
}

function openCreate() {
  resetForm()
  dialog.value = true
}

function openEdit(row: Dept) {
  editingId.value = row.dept_id
  Object.assign(form, {
    dept_code: row.dept_code,
    dept_name: row.dept_name,
    sort_no: row.sort_no,
  })
  dialog.value = true
}

async function submit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editingId.value) {
      await depts.update(editingId.value, {
        dept_name: form.dept_name,
        sort_no: form.sort_no,
      })
      ElMessage.success('科室已更新')
    } else {
      await depts.create({ ...form })
      ElMessage.success('科室已新增')
    }
    dialog.value = false
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function onToggle(row: Dept) {
  const action = row.status === '1' ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(
      `${action}后该科室将${row.status === '1' ? '不再出现在分诊候选与挂号选择中' : '恢复参与分诊'}。确定${action}「${row.dept_name}」？`,
      `确认${action}`,
      { type: 'warning', confirmButtonText: `确定${action}`, cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await depts.toggle(row.dept_id)
    ElMessage.success(`已${action}`)
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message || '操作失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div class="page-title">
        <h1>科室管理</h1>
        <p>科室编码是分诊与知识库的关联键，新增后请勿随意修改。</p>
      </div>
      <div class="page-actions">
        <el-button type="primary" @click="openCreate">新增科室</el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索科室编码 / 名称"
        clearable
        style="width: 240px"
        @keyup.enter="search"
        @clear="search"
      />
      <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 120px" @change="search">
        <el-option label="启用" value="1" />
        <el-option label="停用" value="0" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <el-button text @click="resetFilters">重置</el-button>
      <span class="result-count">共 <b>{{ total }}</b> 个科室</span>
    </div>

    <section class="table-card" v-loading="loading">
      <el-table :data="items" row-key="dept_id" @row-click="onView">
        <el-table-column label="科室" min-width="220">
          <template #default="{ row }">
            <div class="dept-cell">
              <span class="dept-mark">{{ row.dept_name.slice(0, 1) }}</span>
              <div>
                <b>{{ row.dept_name }}</b>
                <em class="mono">{{ row.dept_code }}</em>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="sort_no" label="排序" width="90" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span class="status-dot" :class="{ 'is-off': row.status !== '1' }">
              {{ row.status === '1' ? '启用' : '停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="onView(row)">查看</el-button>
            <el-button link type="primary" size="small" @click.stop="openEdit(row)">编辑</el-button>
            <el-button link :type="row.status === '1' ? 'danger' : 'success'" size="small" @click.stop="onToggle(row)">
              {{ row.status === '1' ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-block">
            <p class="empty-block__title">没有匹配的科室</p>
            <p>试试更换关键词，或新增一个科室。</p>
            <el-button @click="openCreate">新增科室</el-button>
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
      :title="detail ? detail.dept_name : '科室详情'"
      :subtitle="detail ? detail.dept_code : ''"
      :badge="detail ? detail.dept_name.slice(0, 1) : '科'"
      :fields="detailFields"
    />

    <el-dialog v-model="dialog" :title="editingId ? '编辑科室' : '新增科室'" width="440px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="科室编码" prop="dept_code">
          <el-input v-model="form.dept_code" :disabled="!!editingId" placeholder="如 ORTH" />
        </el-form-item>
        <el-form-item label="科室名称" prop="dept_name">
          <el-input v-model="form.dept_name" placeholder="如 骨科" />
        </el-form-item>
        <el-form-item label="排序号" prop="sort_no">
          <el-input-number v-model="form.sort_no" :min="0" :max="9999" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">
          {{ editingId ? '保存修改' : '新增科室' }}
        </el-button>
      </template>
    </el-dialog>
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

.dept-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dept-mark {
  width: 32px;
  height: 32px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--c-accent-soft);
  border: 1px solid #e6cdb5;
  color: var(--c-accent-strong);
  font-family: var(--font-display);
  font-size: 14px;
}

.dept-cell b {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
}

.dept-cell em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--c-faint);
}

.status-dot {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--c-success);
}

.status-dot::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-dot.is-off {
  color: var(--c-faint);
}
</style>
