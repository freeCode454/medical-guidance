<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { kg, type KgEdge, type KgNode, type KgStats } from '@/api/kg'
import { depts } from '@/api/admin'

type Mode = 'symptom' | 'dept'

const stats = ref<KgStats | null>(null)
const mode = ref<Mode>('symptom')

const symptom = ref('腹痛')
const symptomOptions = ref<string[]>([])
const deptCode = ref('')
const deptOptions = ref<{ code: string; name: string }[]>([])

const limit = ref(30)
const loading = ref(false)
const graph = ref<{ nodes: KgNode[]; edges: KgEdge[] } | null>(null)
const summary = ref('')
const paths = ref<string[]>([])

const chartEl = ref<HTMLDivElement>()
const chart = shallowRef<echarts.ECharts>()

const CATEGORIES = [
  { name: '症状', color: '#2f6f6a' },
  { name: '疾病', color: '#bf6a34' },
  { name: '科室', color: '#3f8a6f' },
]

const NODE_LABELS: Record<string, string> = {
  Symptom: '症状',
  Department: '科室',
  Disease: '疾病',
  ICD: 'ICD',
  Drug: '药物',
  Condition: '条件',
}

async function loadStats() {
  try {
    stats.value = await kg.stats()
  } catch (e) {
    ElMessage.error((e as Error).message || '图谱统计加载失败')
  }
}

async function loadOptions() {
  try {
    const s = await kg.symptoms()
    symptomOptions.value = s.items
  } catch {
    /* 忽略 */
  }
  try {
    const d = await depts.list({ size: 500 })
    deptOptions.value = d.items.map((x) => ({ code: x.dept_code, name: x.dept_name }))
    if (!deptCode.value && deptOptions.value.length) deptCode.value = deptOptions.value[0].code
  } catch {
    /* 忽略 */
  }
}

function renderChart() {
  if (!chart.value || !graph.value) return
  const { nodes, edges } = graph.value
  chart.value.setOption(
    {
      tooltip: { trigger: 'item' },
      legend: [{ data: CATEGORIES.map((c) => c.name), bottom: 6 }],
      color: CATEGORIES.map((c) => c.color),
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          categories: CATEGORIES,
          symbolSize: 44,
          data: nodes.map((n) => ({
            id: n.id,
            name: n.name,
            category: n.category,
            symbolSize: n.category === 2 ? 64 : n.category === 0 ? 48 : 58,
          })),
          links: edges.map((e) => ({
            source: e.source,
            target: e.target,
            // 科室视角边多，只给「归属」标文字，避免画面糊
            label: { show: e.label === '归属', formatter: e.label, fontSize: 10, color: '#64748b' },
          })),
          force: { repulsion: 300, edgeLength: [70, 140], gravity: 0.08 },
          label: { show: true, position: 'inside', fontSize: 10, color: '#fff' },
          lineStyle: { color: 'source', curveness: 0.1, opacity: 0.65 },
          edgeSymbol: ['none', 'arrow'],
          edgeSymbolSize: 7,
          emphasis: { focus: 'adjacency', lineStyle: { width: 2.4 } },
        },
      ],
    },
    true,
  )
}

async function query() {
  loading.value = true
  try {
    if (mode.value === 'symptom') {
      const name = symptom.value.trim()
      if (!name) {
        ElMessage.warning('请选择或输入症状')
        return
      }
      const d = await kg.network(name, limit.value)
      graph.value = d
      summary.value = d.nodes.length
        ? `命中 ${d.paths} 条推理路径`
        : `图谱中没有「${name}」的推理路径`
      paths.value = d.edges
        .filter((x) => x.label === '提示')
        .map((e) => {
          const dept = d.edges.find((x) => x.label === '归属' && x.source === e.target)
          return `${name} → ${e.target.replace('disease::', '')} → ${
            dept ? dept.target.replace('dept::', '') : '—'
          }`
        })
    } else {
      if (!deptCode.value) {
        ElMessage.warning('请选择科室')
        return
      }
      const d = await kg.deptNetwork(deptCode.value, limit.value)
      graph.value = d
      summary.value = d.nodes.length
        ? `${d.dept_name}：${d.diseases} 个疾病 / ${d.nodes.length} 个节点`
        : '该科室在图谱中没有疾病数据'
      paths.value = d.edges
        .filter((x) => x.label === '归属')
        .map((e) => e.source.replace('disease::', ''))
    }
    await nextTick()
    renderChart()
  } catch (e) {
    ElMessage.error((e as Error).message || '查询失败')
  } finally {
    loading.value = false
  }
}

function onModeChange() {
  graph.value = null
  paths.value = []
  summary.value = ''
  chart.value?.clear()
  query()
}

function onResize() {
  chart.value?.resize()
}

watch(limit, () => query())

onMounted(async () => {
  chart.value = echarts.init(chartEl.value!)
  window.addEventListener('resize', onResize)
  await Promise.all([loadStats(), loadOptions()])
  await query()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart.value?.dispose()
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div class="page-title">
        <h1>知识图谱</h1>
        <p>Neo4j 两跳推理网络：症状 → 疾病 → 科室，支持症状与科室双视角。</p>
      </div>
      <div class="page-actions">
        <el-button @click="loadStats(); loadOptions()">刷新</el-button>
      </div>
    </div>

    <div v-if="stats" class="stat-row">
      <div v-for="n in stats.nodes" :key="n.label" class="stat">
        <p class="stat__label">{{ NODE_LABELS[n.label] || n.label }}</p>
        <p class="stat__value">{{ n.count }}</p>
      </div>
    </div>

    <section class="panel panel--pad toolbar">
      <el-radio-group v-model="mode" @change="onModeChange">
        <el-radio-button value="symptom">症状视角</el-radio-button>
        <el-radio-button value="dept">科室视角</el-radio-button>
      </el-radio-group>

      <template v-if="mode === 'symptom'">
        <span class="label">症状</span>
        <el-select
          v-model="symptom"
          filterable
          allow-create
          default-first-option
          placeholder="选择或输入症状"
          style="width: 210px"
          @change="query"
        >
          <el-option v-for="s in symptomOptions" :key="s" :label="s" :value="s" />
        </el-select>
      </template>

      <template v-else>
        <span class="label">科室</span>
        <el-select
          v-model="deptCode"
          filterable
          placeholder="选择科室"
          style="width: 210px"
          @change="query"
        >
          <el-option
            v-for="d in deptOptions"
            :key="d.code"
            :label="`${d.name}（${d.code}）`"
            :value="d.code"
          />
        </el-select>
      </template>

      <span class="label">{{ mode === 'symptom' ? '路径数' : '疾病数' }}</span>
      <el-slider v-model="limit" :min="5" :max="100" :step="5" style="width: 130px" />
      <span class="limit mono">{{ limit }}</span>

      <el-button type="primary" :loading="loading" @click="query">查询</el-button>
      <span v-if="summary" class="count">{{ summary }}</span>
    </section>

    <section class="panel chart-card">
      <div class="chart-head">
        <span class="section-label">关系网络</span>
        <span class="chart-hint">拖拽节点查看邻接关系，滚轮缩放</span>
      </div>
      <div ref="chartEl" class="chart" v-loading="loading" />
    </section>

    <section v-if="paths.length" class="panel panel--pad paths">
      <div class="paths-head">
        <span class="section-label">{{ mode === 'symptom' ? '推理路径' : '科室下的疾病' }}</span>
        <span class="muted">{{ paths.length }} 条</span>
      </div>
      <div class="path-list">
        <div v-for="(p, i) in paths" :key="i" class="path-item">
          <span class="path-index mono">{{ String(i + 1).padStart(2, '0') }}</span>
          <span>{{ p }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.label {
  color: var(--c-muted);
  font-size: 12.5px;
}

.limit {
  font-size: 12px;
  color: var(--c-ink);
  width: 28px;
}

.count {
  margin-left: auto;
  color: var(--c-muted);
  font-size: 12px;
}

.chart-card {
  overflow: hidden;
}

.chart-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px 0;
}

.section-label {
  font-size: 11.5px;
  letter-spacing: 0.08em;
  color: var(--c-muted);
}

.chart-hint {
  font-size: 11px;
  color: var(--c-faint);
}

.chart {
  height: 540px;
  width: 100%;
}

.paths {
  margin-top: 14px;
}

.paths-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.path-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 8px;
  max-height: 240px;
  overflow: auto;
}

.path-item {
  display: flex;
  align-items: baseline;
  gap: 9px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--c-ink);
  padding: 8px 12px;
  background: var(--c-surface-soft);
  border: 1px solid var(--c-line-soft);
  border-radius: 9px;
}

.path-index {
  font-size: 10px;
  color: var(--c-faint);
}

@media (max-width: 760px) {
  .chart {
    height: 420px;
  }
}
</style>
