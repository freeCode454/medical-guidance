<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { depts, type Dept } from '@/api/admin'

const loading = ref(false)
const items = ref<Dept[]>([])
const dialog = ref(false)
const form = ref({ dept_code: '', dept_name: '', sort_no: 0 })

async function load() {
  loading.value = true
  try {
    items.value = (await depts.list()).items
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
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
  try {
    await depts.toggle(row.dept_id)
    ElMessage.success('已切换状态')
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
</style>
