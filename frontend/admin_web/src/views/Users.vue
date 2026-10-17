<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { users, depts, type User, type Dept } from '@/api/admin'

const loading = ref(false)
const items = ref<User[]>([])
const deptList = ref<Dept[]>([])
const dialog = ref(false)
const form = ref({ account: '', real_name: '', role: 'DOCTOR', title: '', dept_code: '', initial_password: '' })
const page = ref(1)
const size = ref(10)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const d = await users.list({ page: page.value, size: size.value })
    items.value = d.items
    total.value = d.total
    deptList.value = (await depts.list({ size: 500 })).items
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
    await users.create(form.value)
    ElMessage.success('创建成功')
    dialog.value = false
    form.value = { account: '', real_name: '', role: 'DOCTOR', title: '', dept_code: '', initial_password: '' }
    load()
  } catch (e) {
    ElMessage.error((e as Error).message || '创建失败')
  }
}

async function onToggle(row: User) {
  try {
    await users.toggle(row.user_id)
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
      <h2>用户管理</h2>
      <el-button type="primary" @click="dialog = true">新建用户</el-button>
    </div>

    <el-table :data="items" v-loading="loading">
      <el-table-column prop="account" label="账号" width="140" />
      <el-table-column prop="real_name" label="姓名" width="120" />
      <el-table-column prop="role_label" label="角色" width="120" />
      <el-table-column prop="title" label="职称" width="120" />
      <el-table-column prop="dept_name" label="科室" width="120" />
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

    <el-dialog v-model="dialog" title="新建用户" width="480px">
      <el-form label-width="90px">
        <el-form-item label="账号"><el-input v-model="form.account" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.real_name" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%">
            <el-option label="医生" value="DOCTOR" />
            <el-option label="知识库管理员" value="KB_ADMIN" />
            <el-option label="机构管理员" value="ORG_ADMIN" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.role === 'DOCTOR'" label="职称">
          <el-select v-model="form.title" style="width: 100%">
            <el-option v-for="t in ['住院医师', '主治医师', '副主任医师', '主任医师']" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.role === 'DOCTOR'" label="科室">
          <el-select v-model="form.dept_code" style="width: 100%">
            <el-option v-for="d in deptList" :key="d.dept_code" :label="d.dept_name" :value="d.dept_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="初始密码"><el-input v-model="form.initial_password" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
h2 { font-size: 18px; }
.pager { justify-content: center; margin-top: 14px; }
</style>
