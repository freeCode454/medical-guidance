<script setup lang="ts">
import type { DetailField } from './detail'

const visible = defineModel<boolean>({ default: false })

defineProps<{
  title: string
  subtitle?: string
  badge?: string
  fields: DetailField[]
}>()
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="560px"
    top="7vh"
    append-to-body
    destroy-on-close
    class="entity-detail-dialog"
  >
    <div v-if="badge || subtitle" class="entity-head">
      <span v-if="badge" class="entity-badge">{{ badge }}</span>
      <span v-if="subtitle" class="entity-subtitle">{{ subtitle }}</span>
    </div>

    <dl class="entity-grid">
      <div v-for="field in fields" :key="field.label" class="entity-row">
        <dt>{{ field.label }}</dt>
        <dd :class="{ mono: field.mono }">{{ field.value ?? '—' }}</dd>
      </div>
    </dl>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.entity-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 2px 0 16px;
  border-bottom: 1px solid var(--c-line-soft);
}

.entity-badge {
  width: 42px;
  height: 42px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 13px;
  background: var(--c-primary-soft);
  border: 1px solid var(--c-primary-line);
  color: var(--c-primary);
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
}

.entity-subtitle {
  color: var(--c-muted);
  font-size: 12px;
  word-break: break-all;
}

.entity-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 24px;
  margin: 10px 0 0;
}

.entity-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid var(--c-line-soft);
}

.entity-row dt {
  flex: none;
  font-size: 12px;
  color: var(--c-muted);
}

.entity-row dd {
  margin: 0;
  font-size: 12.5px;
  color: var(--c-ink-soft);
  text-align: right;
  word-break: break-all;
}

.entity-row dd.mono {
  font-family: var(--font-mono);
  font-size: 11.5px;
}

@media (max-width: 560px) {
  .entity-grid {
    grid-template-columns: 1fr;
  }
}
</style>
