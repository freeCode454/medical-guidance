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
  { name: '症状', color: '#2563eb' },
  { name: '疾病', color: '#d97706' },
  { name: '科室', color: '#059669' },
]

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
      legend: [{ data: CATEGORIES.map((c) => c.name), top: 4 }],
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
            symbolSize: n.category === 2 ? 62 : n.category === 0 ? 46 : 40,
          })),
          links: edges.map((e) => ({
            source: e.source,
            target: e.target,
            // 科室视角边多，只给「归属」标文字，避免画面糊
            label: { show: e.label === '归属', formatter: e.label, fontSize: 10, color: '#64748b' },
          })),
          force: { repulsion: 300, edgeLength: [70, 140], gravity: 0.08 },
          label: { show: true, position: 'inside', fontSize: 11, color: '#fff' },
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
  <div class="kg-page">
    <div class="head">
      <h2>知识图谱</h2>
      <span class="sub">Neo4j 两跳推理网络（症状 / 科室 双视角）</span>
    </div>

    <div v-if="stats" class="stat-row">
      <div v-for="n in stats.nodes" :key="n.label" class="stat-card">
        <div class="stat-value">{{ n.count }}</div>
        <div class="stat-label">{{ n.label }}</div>
      </div>
    </div>

    <div class="toolbar">
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
          style="width: 220px"
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
          style="width: 220px"
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
      <el-slider v-model="limit" :min="5" :max="100" :step="5" style="width: 140px" />
      <span class="limit">{{ limit }}</span>

      <el-button type="primary" :loading="loading" @click="query">查询</el-button>
      <span v-if="summary" class="count">{{ summary }}</span>
    </div>

    <div ref="chartEl" class="chart" v-loading="loading"></div>

    <div v-if="paths.length" class="paths">
      <div class="paths-head">{{ mode === 'symptom' ? '推理路径' : '科室下的疾病' }}</div>
      <div class="path-list">
        <div v-for="(p, i) in paths" :key="i" class="path-item">{{ p }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kg-page { padding: 4px 0; }

.head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; }
h2 { font-size: 18px; }
.sub { color: var(--c-muted); font-size: 13px; }

.stat-row { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }

.stat-card {
  flex: 1;
  min-width: 110px;
  background: var(--c-surface);
  border: 1px solid var(--c-line);
  border-radius: 8px;
  padding: 12px 16px;
}

.stat-value { font-size: 22px; font-weight: 600; color: var(--c-primary); }
.stat-label { font-size: 12px; color: var(--c-muted); margin-top: 2px; }

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.label { color: var(--c-muted); font-size: 13px; }
.limit { font-size: 13px; color: var(--c-ink); width: 28px; }
.count { color: var(--c-muted); font-size: 13px; }

.chart {
  height: 520px;
  background: var(--c-surface);
  border: 1px solid var(--c-line);
  border-radius: 8px;
}

.paths { margin-top: 16px; }
.paths-head { font-size: 14px; font-weight: 600; margin-bottom: 8px; }

.path-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 6px;
  max-height: 200px;
  overflow: auto;
}

.path-item {
  font-size: 13px;
  color: var(--c-ink);
  padding: 6px 12px;
  background: var(--c-primary-soft);
  border-radius: 6px;
}
</style>
