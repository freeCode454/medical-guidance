<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { users, depts, type User, type Dept } from '@/api/admin'
import EntityDetailDialog from '@/components/EntityDetailDialog.vue'
import type { DetailField } from '@/components/detail'
import { fmtDateTime } from '@/utils/format'

const loading = ref(false)
const items = ref<User[]>([])
const deptList = ref<Dept[]>([])
const dialog = ref(false)
const saving = ref(false)
const editingId = ref('')
const formRef = ref<FormInstance>()
const page = ref(1)
const size = ref(10)
const total = ref(0)
const keyword = ref('')
const roleFilter = ref('')
const statusFilter = ref('')

const form = reactive({
  account: '',
  real_name: '',
  role: 'DOCTOR',
  title: '',
  dept_code: '',
  initial_password: '',
})

const rules = computed<FormRules>(() => ({
  account: [
    { required: true, message: '请输入账号', trigger: 'blur' },
    { min: 4, max: 64, message: '账号长度 4~64 位', trigger: 'blur' },
  ],
  real_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  title: [{ required: true, message: '请选择职称', trigger: 'change' }],
  dept_code: [{ required: true, message: '请选择科室', trigger: 'change' }],
  initial_password: editingId.value
    ? [{ min: 8, max: 64, message: '密码至少 8 位', trigger: 'blur' }]
    : [
        { required: true, message: '请设置初始密码', trigger: 'blur' },
        { min: 8, max: 64, message: '密码至少 8 位', trigger: 'blur' },
      ],
}))

const roleOptions = [
  { value: 'DOCTOR', label: '医生' },
  { value: 'KB_ADMIN', label: '知识库管理员' },
  { value: 'ORG_ADMIN', label: '机构管理员' },
]

const roleLabels = Object.fromEntries(roleOptions.map((r) => [r.value, r.label]))
const isDoctor = computed(() => form.role === 'DOCTOR')
const detailVisible = ref(false)
const detail = ref<User | null>(null)

const detailFields = computed<DetailField[]>(() => {
  const row = detail.value
  if (!row) return []
  return [
    { label: '登录账号', value: row.account, mono: true },
    { label: '姓名', value: row.real_name || '未填写' },
    { label: '角色', value: roleLabels[row.role] || row.role_label },
    { label: '职称', value: row.title || '—' },
    { label: '所属科室', value: row.dept_name || row.dept_code || '—' },
    { label: '账号状态', value: row.status === '1' ? '启用' : '停用' },
    { label: '最近登录', value: row.last_login_time ? fmtDateTime(row.last_login_time) : '从未登录' },
    { label: '创建时间', value: row.create_time ? fmtDateTime(row.create_time) : '—' },
    { label: '用户 ID', value: row.user_id, mono: true },
  ]
})

async function load() {
  loading.value = true
  try {
    const d = await users.list({
      page: page.value,
      size: size.value,
      keyword: keyword.value || null,
      role: roleFilter.value || null,
      status: statusFilter.value || null,
    })
    items.value = d.items
    total.value = d.total
    if (!deptList.value.length) {
      deptList.value = (await depts.list({ size: 500 })).items
    }
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
  roleFilter.value = ''
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

function onView(row: User) {
  detail.value = row
  detailVisible.value = true
}

function resetForm() {
  editingId.value = ''
  Object.assign(form, {
    account: '',
    real_name: '',
    role: 'DOCTOR',
    title: '',
    dept_code: '',
    initial_password: '',
  })
  formRef.value?.clearValidate()
}

function openCreate() {
  resetForm()
  dialog.value = true
}

function openEdit(row: User) {
  editingId.value = row.user_id
  Object.assign(form, {
    account: row.account,
    real_name: row.real_name || '',
    role: row.role,
    title: row.title || '',
    dept_code: row.dept_code || '',
    initial_password: '',
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
      await users.update(editingId.value, {
        real_name: form.real_name,
        role: form.role,
        title: isDoctor.value ? form.title : null,
        dept_code: isDoctor.value ? form.dept_code : null,
        ...(form.initial_password ? { initial_password: form.initial_password } : {}),
      })
      ElMessage.success('用户已更新')
    } else {
      await users.create({
        account: form.account,
        real_name: form.real_name,
        role: form.role,
        title: isDoctor.value ? form.title : undefined,
        dept_code: isDoctor.value ? form.dept_code : undefined,
        initial_password: form.initial_password,
      })
      ElMessage.success('用户已创建')
    }
    dialog.value = false
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function onToggle(row: User) {
  const action = row.status === '1' ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(
      `${action}后该账号将${row.status === '1' ? '无法登录，但历史数据保留' : '恢复登录'}。确定${action}「${row.account}」？`,
      `确认${action}`,
      { type: 'warning', confirmButtonText: `确定${action}`, cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await users.toggle(row.user_id)
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
        <h1>用户管理</h1>
        <p>维护机构内的医生与管理员账号，停用后立即无法登录。</p>
      </div>
      <div class="page-actions">
        <el-button type="primary" @click="openCreate">新建用户</el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索账号 / 姓名"
        clearable
        style="width: 220px"
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

      <el-select v-model="roleFilter" placeholder="全部角色" clearable style="width: 150px" @change="search">
        <el-option v-for="r in roleOptions" :key="r.value" :label="r.label" :value="r.value" />
      </el-select>

      <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 120px" @change="search">
        <el-option label="启用" value="1" />
        <el-option label="停用" value="0" />
      </el-select>

      <el-button @click="search">查询</el-button>
      <el-button text @click="resetFilters">重置</el-button>
      <span class="result-count">共 <b>{{ total }}</b> 个账号</span>
    </div>

    <section class="table-card" v-loading="loading">
      <el-table :data="items" row-key="user_id" @row-click="onView">
        <el-table-column label="用户" min-width="220">
          <template #default="{ row }">
            <div class="user-cell">
              <span class="user-avatar">{{ (row.real_name || row.account).slice(0, 1) }}</span>
              <div class="user-cell__text">
                <b>{{ row.real_name || '未填写姓名' }}</b>
                <em class="mono">{{ row.account }}</em>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="130">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.role === 'ORG_ADMIN' ? 'warning' : row.role === 'KB_ADMIN' ? 'success' : 'info'">
              {{ roleLabels[row.role] || row.role_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="职称" width="120">
          <template #default="{ row }">{{ row.title || '—' }}</template>
        </el-table-column>
        <el-table-column prop="dept_name" label="科室" width="140">
          <template #default="{ row }">{{ row.dept_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="status-dot" :class="{ 'is-off': row.status !== '1' }">
              {{ row.status === '1' ? '启用' : '停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" width="160">
          <template #default="{ row }">
            <span class="muted">{{ row.last_login_time ? fmtDateTime(row.last_login_time) : '从未登录' }}</span>
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
            <p class="empty-block__title">没有匹配的账号</p>
            <p>试试更换关键词或重置筛选条件。</p>
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
      :title="detail ? (detail.real_name || detail.account) : '用户详情'"
      :subtitle="detail ? detail.account : ''"
      :badge="detail ? (detail.real_name || detail.account).slice(0, 1) : '用'"
      :fields="detailFields"
    />

    <el-dialog
      v-model="dialog"
      :title="editingId ? '编辑用户' : '新建用户'"
      width="500px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="账号" prop="account">
            <el-input v-model="form.account" :disabled="!!editingId" placeholder="登录账号，4~64 位" />
          </el-form-item>
          <el-form-item label="姓名" prop="real_name">
            <el-input v-model="form.real_name" placeholder="真实姓名" />
          </el-form-item>
          <el-form-item label="角色" prop="role">
            <el-select v-model="form.role" style="width: 100%">
              <el-option v-for="r in roleOptions" :key="r.value" :label="r.label" :value="r.value" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="isDoctor" label="职称" prop="title">
            <el-select v-model="form.title" style="width: 100%">
              <el-option v-for="t in ['住院医师', '主治医师', '副主任医师', '主任医师']" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="isDoctor" label="科室" prop="dept_code">
            <el-select v-model="form.dept_code" filterable style="width: 100%">
              <el-option v-for="d in deptList" :key="d.dept_code" :label="d.dept_name" :value="d.dept_code" />
            </el-select>
          </el-form-item>
          <el-form-item :label="editingId ? '重置密码（可选）' : '初始密码'" prop="initial_password">
            <el-input v-model="form.initial_password" type="password" show-password placeholder="至少 8 位" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">
          {{ editingId ? '保存修改' : '创建用户' }}
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

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-avatar {
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

.user-cell__text {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.user-cell__text b {
  font-size: 13.5px;
  font-weight: 600;
}

.user-cell__text em {
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

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 14px;
}

.form-grid :deep(.el-form-item) {
  margin-bottom: 16px;
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .result-count {
    margin-left: 0;
  }
}
</style>
