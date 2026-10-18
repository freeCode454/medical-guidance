<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { depts, type Dept } from '@/api/admin'

const loading = ref(false)
const items = ref<Dept[]>([])
const dialog = ref(false)
const form = ref({ dept_code: '', dept_name: '', sort_no: 0 })
const page = ref(1)
const size = ref(10)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const d = await depts.list({ page: page.value, size: size.value })
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

async function onCreate() {
  try {
    await depts.create(form.value)
    ElMessage.success('新增成功')
    dialog.value = false
    form.value = { dept_code: '', dept_name: '', sort_no: 0 }
    load()
  } catch (e) {
    ElMessage.error((e as Error).message || '新增失败')
  }
}

async function onToggle(row: Dept) {
  const action = row.status === '1' ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确定${action}科室「${row.dept_name}」？`, '确认操作', {
      type: 'warning',
      confirmButtonText: '确定' + action,
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await depts.toggle(row.dept_id)
    ElMessage.success(`已${action}`)
    load()
  } catch (e) {
    ElMessage.error((e as Error).message || '操作失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="head">
      <h2>科室管理</h2>
      <el-button type="primary" @click="dialog = true">新增科室</el-button>
    </div>

    <el-table :data="items" v-loading="loading">
      <el-table-column prop="dept_code" label="科室编码" width="140" />
      <el-table-column prop="dept_name" label="科室名称" width="200" />
      <el-table-column prop="sort_no" label="排序" width="90" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === '1' ? 'success' : 'info'" size="small">{{ row.status === '1' ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" @click="onToggle(row)">{{ row.status === '1' ? '停用' : '启用' }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="size"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      background
      class="pager"
      @current-change="onPageChange"
      @size-change="onSizeChange"
    />

    <el-dialog v-model="dialog" title="新增科室" width="420px">
      <el-form label-width="90px">
        <el-form-item label="科室编码"><el-input v-model="form.dept_code" placeholder="如 ORTH" /></el-form-item>
        <el-form-item label="科室名称"><el-input v-model="form.dept_name" placeholder="如 骨科" /></el-form-item>
        <el-form-item label="排序号"><el-input-number v-model="form.sort_no" :min="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="onCreate">新增</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
h2 { font-size: 18px; }
.pager { justify-content: center; margin-top: 14px; }
</style>
