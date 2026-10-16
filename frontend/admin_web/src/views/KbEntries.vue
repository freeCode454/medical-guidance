<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { kb, type KbEntry } from '@/api/kb'

const loading = ref(false)
const items = ref<KbEntry[]>([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')

// 检索测试台
const query = ref('')
const results = ref<Array<{ dept_code: string; dept_name: string; score: number }>>([])
const testing = ref(false)

// 新增弹窗
const dialog = ref(false)
const form = ref({ entry_code: '', kb_type: 'DEPT_EXPERTISE', title: '', content: '', dept_code: '' })

const kbTypes = [
  { v: 'DEPT_EXPERTISE', l: '科室专长' },
  { v: 'SYMPTOM_DISEASE', l: '症状-疾病' },
  { v: 'GUIDELINE', l: '指南' },
  { v: 'ICD-10', l: 'ICD-10' },
  { v: 'DRUG_SAFETY', l: '用药安全' },
]

async function load() {
  loading.value = true
  try {
    const d = await kb.list({ page: page.value, keyword: keyword.value || null })
    items.value = d.items
    total.value = d.total
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  try {
    await kb.create(form.value)
    ElMessage.success('新增成功')
    dialog.value = false
    form.value = { entry_code: '', kb_type: 'DEPT_EXPERTISE', title: '', content: '', dept_code: '' }
    load()
  } catch (e) {
    ElMessage.error((e as Error).message || '新增失败')
  }
}

async function onToggle(row: KbEntry) {
  try {
    await kb.toggle(row.entry_id)
    ElMessage.success('已切换')
    load()
  } catch (e) {
    ElMessage.error((e as Error).message || '操作失败')
  }
}

async function onTest() {
  if (!query.value.trim()) return
  testing.value = true
  try {
    const d = await kb.retrievalTest({ query: query.value, mode: 'DENSE' })
    results.value = d.candidates
  } catch (e) {
    ElMessage.error((e as Error).message || '检索失败')
  } finally {
    testing.value = false
  }
}

async function onPublish() {
  try {
    const d = await kb.publish()
    ElMessage.success('已发布版本 ' + d.version_tag)
  } catch (e) {
    ElMessage.error((e as Error).message || '发布失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="head">
      <h2>知识库条目</h2>
      <div>
        <el-button @click="onPublish">发布知识库</el-button>
        <el-button type="primary" @click="dialog = true">新增条目</el-button>
      </div>
    </div>

    <!-- 检索测试台 -->
    <el-card shadow="never" class="mb">
      <h3>检索测试台</h3>
      <div class="test-row">
        <el-input v-model="query" placeholder="输入主诉，如「肚子疼还拉肚子」" @keyup.enter="onTest" />
        <el-button type="primary" :loading="testing" @click="onTest">测试</el-button>
      </div>
      <div v-if="results.length" class="results">
        <el-tag v-for="(r, i) in results" :key="r.dept_code" :type="i === 0 ? 'primary' : 'info'" class="mr8">
          {{ r.dept_name }} {{ (r.score * 100).toFixed(1) }}%
        </el-tag>
      </div>
    </el-card>

    <!-- 条目列表 -->
    <div class="filter">
      <el-input v-model="keyword" placeholder="搜索标题/正文" style="width: 240px" clearable @keyup.enter="load" />
      <el-button @click="load">搜索</el-button>
    </div>

    <el-table :data="items" v-loading="loading">
      <el-table-column prop="entry_code" label="编码" width="150" />
      <el-table-column prop="title" label="标题" width="180" />
      <el-table-column prop="kb_type" label="类型" width="120" />
      <el-table-column prop="dept_code" label="科室" width="90" />
      <el-table-column label="参与检索" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '参与' : '未参与' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" @click="onToggle(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      :total="total"
      :page-size="20"
      layout="total, prev, pager, next"
      class="mt"
      @current-change="load"
    />

    <!-- 新增弹窗 -->
    <el-dialog v-model="dialog" title="新增知识库条目" width="520px">
      <el-form label-width="90px">
        <el-form-item label="编码"><el-input v-model="form.entry_code" placeholder="如 DEPT-DIG-002" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.kb_type" style="width: 100%">
            <el-option v-for="t in kbTypes" :key="t.v" :label="t.l" :value="t.v" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="科室"><el-input v-model="form.dept_code" placeholder="如 DIG" /></el-form-item>
        <el-form-item label="正文"><el-input v-model="form.content" type="textarea" :rows="4" /></el-form-item>
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
h3 { font-size: 15px; margin-bottom: 10px; }
.mb { margin-bottom: 16px; }
.mt { margin-top: 16px; }
.mr8 { margin-right: 8px; }
.test-row { display: flex; gap: 10px; }
.results { margin-top: 12px; }
.filter { display: flex; gap: 10px; margin-bottom: 12px; }
</style>
