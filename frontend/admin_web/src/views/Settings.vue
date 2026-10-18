<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { org, providers } from '@/api/admin'

const loading = ref(false)
const saving = ref(false)
const orgInfo = ref<any>(null)
const configs = ref<any[]>([])
const providerList = ref<any[]>([])

async function load() {
  loading.value = true
  try {
    const [orgData, configData, providerData] = await Promise.all([
      org.get(),
      org.configs(),
      providers.list(),
    ])
    orgInfo.value = orgData
    configs.value = configData.items
    providerList.value = providerData.items
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function onSaveOrg() {
  if (!orgInfo.value?.tenant_name?.trim()) {
    ElMessage.warning('机构名称不能为空')
    return
  }
  saving.value = true
  try {
    await org.update({
      tenant_name: orgInfo.value.tenant_name,
      hospital_level: orgInfo.value.hospital_level,
      contact_person: orgInfo.value.contact_person,
      contact_phone: orgInfo.value.contact_phone,
    })
    ElMessage.success('机构信息已保存')
  } catch (e) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

function keyStatus(row: any) {
  return row.api_key_configured ? '已配置' : '未配置'
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head">
      <div class="page-title">
        <h1>系统设置</h1>
        <p>维护机构信息、系统参数与模型服务；密钥只展示配置状态，不返回明文。</p>
      </div>
      <div class="page-actions">
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <div class="settings-grid">
      <article class="panel panel--pad org-card">
        <div class="panel-head">
          <div>
            <p class="section-label">机构信息</p>
            <p class="panel-desc">展示在医生端与管理后台的机构名称</p>
          </div>
        </div>
        <el-form v-if="orgInfo" label-position="top">
          <div class="form-grid">
            <el-form-item label="机构名称">
              <el-input v-model="orgInfo.tenant_name" placeholder="例如：演示医院" />
            </el-form-item>
            <el-form-item label="医院等级">
              <el-input v-model="orgInfo.hospital_level" placeholder="例如：三级甲等" />
            </el-form-item>
            <el-form-item label="联系人">
              <el-input v-model="orgInfo.contact_person" placeholder="联系人姓名" />
            </el-form-item>
            <el-form-item label="联系电话">
              <el-input v-model="orgInfo.contact_phone" placeholder="联系电话" />
            </el-form-item>
          </div>
          <el-button type="primary" :loading="saving" @click="onSaveOrg">保存机构信息</el-button>
        </el-form>
      </article>

      <article class="panel panel--pad summary-card">
        <p class="section-label">运行概览</p>
        <div class="summary-list">
          <div class="summary-item">
            <span>系统配置项</span>
            <b>{{ configs.length }}</b>
          </div>
          <div class="summary-item">
            <span>模型服务</span>
            <b>{{ providerList.length }}</b>
          </div>
          <div class="summary-item">
            <span>默认模型</span>
            <b class="mono">{{ providerList.find((p) => p.is_default)?.model_name || '—' }}</b>
          </div>
        </div>
        <p class="summary-hint">模型密钥以密文存储，页面只显示是否已配置。</p>
      </article>
    </div>

    <article class="panel config-card">
      <div class="panel-head panel-head--pad">
        <p class="section-label">系统配置</p>
        <span class="muted">{{ configs.length }} 项</span>
      </div>
      <el-table :data="configs" size="small" class="config-table">
        <el-table-column prop="config_key" label="配置键" width="280">
          <template #default="{ row }">
            <span class="mono">{{ row.config_key }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="config_value" label="值" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="config-value">{{ row.config_value }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="muted">{{ row.description || '—' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </article>

    <article class="panel provider-card">
      <div class="panel-head panel-head--pad">
        <p class="section-label">模型配置</p>
        <span class="muted">LLM / Embedding / Rerank</span>
      </div>
      <el-table :data="providerList" size="small" class="config-table">
        <el-table-column prop="provider_name" label="名称" width="180">
          <template #default="{ row }">
            <div class="provider-name">
              <b>{{ row.provider_name }}</b>
              <el-tag v-if="row.is_default" size="small" type="success" effect="light">默认</el-tag>
              <el-tag v-if="row.is_on_prem" size="small" type="warning" effect="plain">院内</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="provider_type" label="类型" width="120">
          <template #default="{ row }">
            <span class="mono">{{ row.provider_type }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="base_url" label="地址" min-width="260" show-overflow-tooltip />
        <el-table-column prop="model_name" label="模型" width="190" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.model_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="密钥" width="100">
          <template #default="{ row }">
            <span class="key-status" :class="{ 'is-empty': !row.api_key_configured }">
              {{ keyStatus(row) }}
            </span>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-block">
            <p class="empty-block__title">还没有模型配置</p>
            <p>通过管理接口添加 LLM / Embedding / Rerank 服务后展示在这里。</p>
          </div>
        </template>
      </el-table>
    </article>
  </div>
</template>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-head--pad {
  padding: 16px 18px 0;
  margin-bottom: 10px;
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

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 14px;
}

.form-grid :deep(.el-form-item) {
  margin-bottom: 14px;
}

.summary-list {
  display: grid;
  gap: 8px;
  margin-top: 4px;
}

.summary-item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--c-line-soft);
}

.summary-item span {
  font-size: 12px;
  color: var(--c-muted);
}

.summary-item b {
  font-family: var(--font-display);
  font-size: 17px;
  color: var(--c-primary);
}

.summary-item b.mono {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--c-ink-soft);
}

.summary-hint {
  margin-top: 12px;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--c-faint);
}

.config-card,
.provider-card {
  overflow: hidden;
}

.config-card {
  margin-bottom: 14px;
}

.config-table {
  --el-table-border-color: var(--c-line-soft);
  --el-table-header-bg-color: var(--c-surface-soft);
}

.config-value {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--c-ink-soft);
}

.provider-name {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
}

.provider-name b {
  font-size: 13px;
  font-weight: 600;
}

.key-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--c-success);
}

.key-status::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.key-status.is-empty {
  color: var(--c-faint);
}

@media (max-width: 960px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
