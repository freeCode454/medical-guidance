<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { kg, type KgNetwork, type KgStats } from '@/api/kg'

const stats = ref<KgStats | null>(null)
const symptomOptions = ref<string[]>([])
const symptom = ref('腹痛')
const limit = ref(30)
const network = ref<KgNetwork | null>(null)
const loading = ref(false)

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

async function loadSymptoms() {
  try {
    const d = await kg.symptoms()
    symptomOptions.value = d.items
  } catch {
    /* 下拉失败不阻断主流程 */
  }
}

function renderChart() {
  if (!chart.value || !network.value) return
  const { nodes, edges } = network.value
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
            symbolSize: n.category === 0 ? 60 : 42,
          })),
          links: edges.map((e) => ({
            source: e.source,
            target: e.target,
            label: { show: true, formatter: e.label, fontSize: 10, color: '#64748b' },
          })),
          force: { repulsion: 320, edgeLength: [90, 150], gravity: 0.08 },
          label: { show: true, position: 'inside', fontSize: 11, color: '#fff' },
          lineStyle: { color: 'source', curveness: 0.12, opacity: 0.7 },
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
  const name = symptom.value.trim()
  if (!name) {
    ElMessage.warning('请选择或输入症状')
    return
  }
  loading.value = true
  try {
    network.value = await kg.network(name, limit.value)
    if (!network.value.nodes.length) {
      ElMessage.info(`图谱中没有「${name}」的推理路径`)
    }
    await nextTick()
    renderChart()
  } catch (e) {
    ElMessage.error((e as Error).message || '查询失败')
  } finally {
    loading.value = false
  }
}

function onResize() {
  chart.value?.resize()
}

watch(limit, () => query())

onMounted(async () => {
  chart.value = echarts.init(chartEl.value!)
  window.addEventListener('resize', onResize)
  await Promise.all([loadStats(), loadSymptoms()])
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
      <span class="sub">症状 → 疾病 → 科室 的两跳推理网络（Neo4j）</span>
    </div>

    <div v-if="stats" class="stat-row">
      <div v-for="n in stats.nodes" :key="n.label" class="stat-card">
        <div class="stat-value">{{ n.count }}</div>
        <div class="stat-label">{{ n.label }}</div>
      </div>
    </div>

    <div class="toolbar">
      <span class="label">症状</span>
      <el-select
        v-model="symptom"
        filterable
        allow-create
        default-first-option
        placeholder="选择或输入症状"
        style="width: 240px"
        @change="query"
      >
        <el-option v-for="s in symptomOptions" :key="s" :label="s" :value="s" />
      </el-select>

      <span class="label">路径数</span>
      <el-slider v-model="limit" :min="5" :max="100" :step="5" style="width: 160px" />
      <span class="limit">{{ limit }}</span>

      <el-button type="primary" :loading="loading" @click="query">查询</el-button>
      <span v-if="network" class="count">命中 {{ network.paths }} 条推理路径</span>
    </div>

    <div ref="chartEl" class="chart" v-loading="loading"></div>

    <div v-if="network && network.nodes.length" class="paths">
      <div class="paths-head">推理路径</div>
      <div class="path-list">
        <div v-for="(e, i) in network.edges.filter((x) => x.label === '提示')" :key="i" class="path-item">
          {{ network.symptom }}
          <span class="arrow">→</span>
          {{ e.target.replace('disease::', '') }}
          <span class="arrow">→</span>
          <span class="dept">
            {{
              network.edges.find((x) => x.label === '归属' && x.source === e.target)?.target.replace('dept::', '') ||
              '—'
            }}
          </span>
        </div>
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
.path-list { display: flex; flex-direction: column; gap: 6px; max-height: 220px; overflow: auto; }

.path-item {
  font-size: 13px;
  color: var(--c-ink);
  padding: 6px 12px;
  background: var(--c-primary-soft);
  border-radius: 6px;
}

.arrow { color: var(--c-muted); margin: 0 6px; }
.dept { color: var(--c-primary); font-weight: 500; }
</style>
