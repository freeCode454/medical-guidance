<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { kb, type KbEntry, type KbPublish } from '@/api/kb'
import { fmtDateTime } from '@/utils/format'

const loading = ref(false)
const items = ref<KbEntry[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const keyword = ref('')
const typeFilter = ref('')
const activeFilter = ref('')
const publishing = ref(false)
const publishes = ref<KbPublish[]>([])

const query = ref('')
const results = ref<Array<{ dept_code: string; dept_name: string; score: number }>>([])
const testing = ref(false)

const dialog = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  entry_code: '',
  kb_type: 'DEPT_EXPERTISE',
  title: '',
  content: '',
  dept_code: '',
})

const kbTypes = [
  { v: 'DEPT_EXPERTISE', l: '科室专长' },
  { v: 'SYMPTOM_DISEASE', l: '症状-疾病' },
  { v: 'GUIDELINE', l: '临床指南' },
  { v: 'GUIDELINE_REC', l: '指南推荐' },
  { v: 'ICD-10', l: 'ICD-10' },
  { v: 'DRUG_SAFETY', l: '用药安全' },
  { v: 'CASE', l: '病例' },
]

const typeLabels = Object.fromEntries(kbTypes.map((t) => [t.v, t.l]))
const typeShort: Record<string, string> = {
  DEPT_EXPERTISE: '科室',
  SYMPTOM_DISEASE: '症状',
  GUIDELINE: '指南',
  GUIDELINE_REC: '荐',
  'ICD-10': 'ICD',
  DRUG_SAFETY: '药',
  CASE: '病例',
}
const latestPublish = computed(() => publishes.value[0] ?? null)

const rules: FormRules = {
  entry_code: [{ required: true, message: '请输入条目编码', trigger: 'blur' }],
  kb_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  content: [{ required: true, message: '请输入正文内容', trigger: 'blur' }],
}

function pct(score: number) {
  return (Math.max(0, Math.min(1, score)) * 100).toFixed(1) + '%'
}

async function load() {
  loading.value = true
  try {
    const d = await kb.list({
      page: page.value,
      size: size.value,
      keyword: keyword.value || null,
      kb_type: typeFilter.value || null,
      is_active: activeFilter.value === '' ? null : activeFilter.value,
    })
    items.value = d.items
    total.value = d.total
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadPublishes() {
  try {
    publishes.value = (await kb.publishes()).items
  } catch {
    publishes.value = []
  }
}

function search() {
  page.value = 1
  void load()
}

function resetFilters() {
  keyword.value = ''
  typeFilter.value = ''
  activeFilter.value = ''
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

async function onCreate() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await kb.create({ ...form })
    ElMessage.success('条目已创建，启用后可参与检索')
    dialog.value = false
    Object.assign(form, {
      entry_code: '',
      kb_type: 'DEPT_EXPERTISE',
      title: '',
      content: '',
      dept_code: '',
    })
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message || '新增失败')
  } finally {
    saving.value = false
  }
}

async function onToggle(row: KbEntry) {
  const action = row.is_active ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(
      `${action}后该条目将${row.is_active ? '不再' : ''}参与检索，确定继续？`,
      `确认${action}`,
      { type: 'warning', confirmButtonText: `确定${action}`, cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await kb.toggle(row.entry_id)
    ElMessage.success(`已${action}`)
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message || '操作失败')
  }
}

async function onTest() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入要测试的主诉')
    return
  }
  testing.value = true
  try {
    const d = await kb.retrievalTest({ query: query.value.trim(), mode: 'DENSE' })
    results.value = d.candidates
    if (!d.candidates.length) ElMessage.info('没有召回结果，试试更具体的症状描述')
  } catch (e) {
    ElMessage.error((e as Error).message || '检索失败')
  } finally {
    testing.value = false
  }
}

async function onPublish() {
  try {
    await ElMessageBox.confirm(
      '发布会把当前启用的知识条目固化为新版本，并切换线上检索依据。确定发布？',
      '发布知识库',
      { type: 'warning', confirmButtonText: '确认发布', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  publishing.value = true
  try {
    const d = await kb.publish()
    ElMessage.success(`已发布版本 ${d.version_tag}（${d.entry_count} 条）`)
    await loadPublishes()
  } catch (e) {
    ElMessage.error((e as Error).message || '发布失败')
  } finally {
    publishing.value = false
  }
}

onMounted(() => {
  void load()
  void loadPublishes()
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div class="page-title">
        <h1>知识库</h1>
        <p>检索测试台验证召回质量，发布后切换线上分诊依据。</p>
      </div>
      <div class="page-actions">
        <el-button :loading="publishing" @click="onPublish">发布知识库</el-button>
        <el-button type="primary" @click="dialog = true">新增条目</el-button>
      </div>
    </div>

    <div class="top-grid">
      <article class="panel test-panel">
        <div class="panel-head">
          <div>
            <p class="section-label">检索测试台</p>
            <p class="panel-desc">输入患者主诉，看候选科室召回与得分</p>
          </div>
          <span class="test-mode">DENSE</span>
        </div>
        <div class="test-row">
          <el-input
            v-model="query"
            placeholder="例如：肚子疼还拉肚子"
            @keyup.enter="onTest"
          />
          <el-button type="primary" :loading="testing" @click="onTest">测试</el-button>
        </div>

        <div v-if="results.length" class="results">
          <div v-for="(r, i) in results" :key="r.dept_code" class="result-row">
            <span class="result-rank">{{ i + 1 }}</span>
            <span class="result-name">{{ r.dept_name }}</span>
            <div class="result-bar"><i :style="{ width: pct(r.score) }" /></div>
            <span class="result-score mono">{{ pct(r.score) }}</span>
          </div>
        </div>
        <p v-else class="test-hint">还没有测试结果，输入一个主诉试试。</p>
      </article>

      <article class="panel publish-panel">
        <p class="section-label">最近发布</p>
        <template v-if="latestPublish">
          <p class="publish-version mono">{{ latestPublish.version_tag }}</p>
          <dl class="publish-meta">
            <div><dt>条目数</dt><dd>{{ latestPublish.entry_count }}</dd></div>
            <div><dt>发布时间</dt><dd>{{ fmtDateTime(latestPublish.published_time) }}</dd></div>
            <div v-if="latestPublish.snapshot_hash">
              <dt>快照指纹</dt>
              <dd class="mono">{{ latestPublish.snapshot_hash.slice(0, 12) }}…</dd>
            </div>
          </dl>
        </template>
        <template v-else>
          <p class="publish-empty">还没有发布记录</p>
          <p class="panel-desc">首次发布后，这里会显示版本号与条目数。</p>
        </template>
      </article>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索标题 / 正文"
        clearable
        style="width: 220px"
        @keyup.enter="search"
        @clear="search"
      />
      <el-select v-model="typeFilter" placeholder="全部类型" clearable style="width: 140px" @change="search">
        <el-option v-for="t in kbTypes" :key="t.v" :label="t.l" :value="t.v" />
      </el-select>
      <el-select v-model="activeFilter" placeholder="检索状态" clearable style="width: 130px" @change="search">
        <el-option label="参与检索" :value="true" />
        <el-option label="未参与" :value="false" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <el-button text @click="resetFilters">重置</el-button>
      <span class="result-count">共 <b>{{ total }}</b> 条</span>
    </div>

    <section class="table-card" v-loading="loading">
      <el-table :data="items" row-key="entry_id">
        <el-table-column label="条目" min-width="260">
          <template #default="{ row }">
            <div class="entry-cell">
              <span class="entry-type">{{ typeShort[row.kb_type] || row.kb_type.slice(0, 2) }}</span>
              <div class="entry-cell__text">
                <b>{{ row.title || row.entry_code }}</b>
                <em class="mono">{{ row.entry_code }}</em>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ typeLabels[row.kb_type] || row.kb_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="dept_code" label="归属科室" width="110">
          <template #default="{ row }">{{ row.dept_code || '—' }}</template>
        </el-table-column>
        <el-table-column label="参与检索" width="110">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              inline-prompt
              active-text="开"
              inactive-text="关"
              @change="onToggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">
            <span class="muted">{{ row.update_time ? fmtDateTime(row.update_time) : '—' }}</span>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-block">
            <p class="empty-block__title">没有匹配的知识条目</p>
            <p>调整筛选条件，或新增一条知识。</p>
            <el-button @click="dialog = true">新增条目</el-button>
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

    <el-dialog v-model="dialog" title="新增知识条目" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="条目编码" prop="entry_code">
            <el-input v-model="form.entry_code" placeholder="如 DEPT-DIG-002，入库幂等键" />
          </el-form-item>
          <el-form-item label="类型" prop="kb_type">
            <el-select v-model="form.kb_type" style="width: 100%">
              <el-option v-for="t in kbTypes" :key="t.v" :label="t.l" :value="t.v" />
            </el-select>
          </el-form-item>
          <el-form-item label="标题">
            <el-input v-model="form.title" placeholder="供列表展示，可留空" />
          </el-form-item>
          <el-form-item label="归属科室">
            <el-input v-model="form.dept_code" placeholder="如 DIG，可留空" />
          </el-form-item>
        </div>
        <el-form-item label="正文" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="5" maxlength="4000" show-word-limit placeholder="用于向量化与全文检索的内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">创建条目</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.top-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.test-panel,
.publish-panel {
  padding: 18px 20px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-label {
  font-size: 11.5px;
  letter-spacing: 0.08em;
  color: var(--c-muted);
}

.panel-desc {
  margin-top: 3px;
  font-size: 12px;
  color: var(--c-faint);
}

.test-mode {
  padding: 2px 8px;
  border-radius: 5px;
  border: 1px solid var(--c-line);
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--c-muted);
}

.test-row {
  display: flex;
  gap: 8px;
}

.results {
  margin-top: 12px;
  display: grid;
  gap: 7px;
}

.result-row {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) 100px 52px;
  align-items: center;
  gap: 10px;
}

.result-rank {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  background: var(--c-surface-soft);
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--c-muted);
}

.result-name {
  font-size: 13px;
  color: var(--c-ink);
}

.result-bar {
  height: 4px;
  border-radius: 999px;
  background: var(--c-line-soft);
  overflow: hidden;
}

.result-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #6fa39b, var(--c-primary));
}

.result-score {
  font-size: 11px;
  color: var(--c-muted);
  text-align: right;
}

.test-hint {
  margin-top: 12px;
  font-size: 12px;
  color: var(--c-faint);
}

.publish-version {
  margin-top: 8px;
  font-size: 17px;
  color: var(--c-primary);
  font-weight: 500;
}

.publish-meta {
  display: grid;
  gap: 7px;
  margin: 12px 0 0;
}

.publish-meta div {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.publish-meta dt {
  color: var(--c-muted);
}

.publish-meta dd {
  margin: 0;
  color: var(--c-ink-soft);
}

.publish-empty {
  margin-top: 10px;
  font-family: var(--font-display);
  font-size: 16px;
  color: var(--c-ink);
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

.entry-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.entry-type {
  width: 40px;
  height: 34px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--c-accent-soft);
  border: 1px solid #e6cdb5;
  color: var(--c-accent-strong);
  font-family: var(--font-display);
  font-size: 11px;
}

.entry-cell__text {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
  min-width: 0;
}

.entry-cell__text b {
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entry-cell__text em {
  font-style: normal;
  font-size: 10.5px;
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

@media (max-width: 960px) {
  .top-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .result-row {
    grid-template-columns: 22px minmax(0, 1fr) 46px;
  }

  .result-bar {
    display: none;
  }

  .result-count {
    margin-left: 0;
  }
}
</style>
