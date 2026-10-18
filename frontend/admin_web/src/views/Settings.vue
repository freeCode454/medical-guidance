<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { org, providers } from '@/api/admin'

const loading = ref(false)
const saving = ref(false)
const orgInfo = ref<any>(null)
const configs = ref<any[]>([])
const providerList = ref<any[]>([])

const providerDialog = ref(false)
const providerSaving = ref(false)
const editingProviderId = ref('')
const providerFormRef = ref<FormInstance>()
const providerForm = reactive({
  provider_code: '',
  provider_type: 'LLM',
  provider_name: '',
  base_url: '',
  model_name: '',
  api_key: '',
  is_on_prem: false,
})

const providerTypes = [
  { value: 'LLM', label: 'LLM 内容生成' },
  { value: 'EMBEDDING', label: 'Embedding 向量化' },
  { value: 'RERANK', label: 'Rerank 精排' },
]

const providerRules: FormRules = {
  provider_code: [{ required: true, message: '请输入配置编码', trigger: 'blur' }],
  provider_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  base_url: [{ required: true, message: '请输入服务地址', trigger: 'blur' }],
}

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

function resetProviderForm() {
  editingProviderId.value = ''
  Object.assign(providerForm, {
    provider_code: '',
    provider_type: 'LLM',
    provider_name: '',
    base_url: '',
    model_name: '',
    api_key: '',
    is_on_prem: false,
  })
  providerFormRef.value?.clearValidate()
}

function openProviderCreate() {
  resetProviderForm()
  providerDialog.value = true
}

function openProviderEdit(row: any) {
  editingProviderId.value = row.provider_id
  Object.assign(providerForm, {
    provider_code: row.provider_code,
    provider_type: row.provider_type,
    provider_name: row.provider_name || '',
    base_url: row.base_url || '',
    model_name: row.model_name || '',
    api_key: '',
    is_on_prem: !!row.is_on_prem,
  })
  providerDialog.value = true
}

async function saveProvider() {
  if (!providerFormRef.value) return
  const valid = await providerFormRef.value.validate().catch(() => false)
  if (!valid) return
  providerSaving.value = true
  try {
    if (editingProviderId.value) {
      await providers.update(editingProviderId.value, {
        provider_name: providerForm.provider_name,
        base_url: providerForm.base_url,
        model_name: providerForm.model_name,
        ...(providerForm.api_key ? { api_key_enc: providerForm.api_key } : {}),
      })
      ElMessage.success('模型配置已更新')
    } else {
      await providers.create({
        provider_code: providerForm.provider_code,
        provider_type: providerForm.provider_type,
        provider_name: providerForm.provider_name,
        base_url: providerForm.base_url,
        model_name: providerForm.model_name,
        api_key_enc: providerForm.api_key || undefined,
        is_on_prem: providerForm.is_on_prem,
      })
      ElMessage.success('模型配置已创建，密钥将加密存储')
    }
    providerDialog.value = false
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    providerSaving.value = false
  }
}

async function setDefaultProvider(row: any) {
  try {
    await ElMessageBox.confirm(
      `将「${row.provider_name || row.provider_code}」设为 ${row.provider_type} 类型的默认服务？`,
      '设为默认',
      { confirmButtonText: '设为默认', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await providers.setDefault(row.provider_id)
    ElMessage.success('已设为该类型默认服务')
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message || '操作失败')
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
        <div class="provider-head">
          <span class="muted">LLM / Embedding / Rerank</span>
          <el-button size="small" type="primary" @click="openProviderCreate">新增模型服务</el-button>
        </div>
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
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openProviderEdit(row)">编辑</el-button>
            <el-button
              v-if="!row.is_default"
              link
              type="success"
              size="small"
              @click="setDefaultProvider(row)"
            >
              设为默认
            </el-button>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-block">
            <p class="empty-block__title">还没有模型配置</p>
            <p>点击右上角「新增模型服务」添加 LLM / Embedding / Rerank。</p>
          </div>
        </template>
      </el-table>
    </article>

    <el-dialog
      v-model="providerDialog"
      :title="editingProviderId ? '编辑模型服务' : '新增模型服务'"
      width="560px"
      destroy-on-close
    >
      <el-form ref="providerFormRef" :model="providerForm" :rules="providerRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="配置编码" prop="provider_code">
            <el-input v-model="providerForm.provider_code" :disabled="!!editingProviderId" placeholder="如 qwen-llm" />
          </el-form-item>
          <el-form-item label="类型" prop="provider_type">
            <el-select v-model="providerForm.provider_type" :disabled="!!editingProviderId" style="width: 100%">
              <el-option v-for="t in providerTypes" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="名称">
            <el-input v-model="providerForm.provider_name" placeholder="如 Qwen2.5-32B" />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="providerForm.model_name" placeholder="如 Qwen/Qwen2.5-32B-Instruct" />
          </el-form-item>
        </div>
        <el-form-item label="服务地址" prop="base_url">
          <el-input v-model="providerForm.base_url" placeholder="https://api.example.com/v1" />
        </el-form-item>
        <el-form-item :label="editingProviderId ? 'API Key（留空不修改）' : 'API Key'">
          <el-input
            v-model="providerForm.api_key"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="仅提交时传输，服务端 Fernet 加密存储"
          />
        </el-form-item>
        <el-form-item label="部署位置">
          <el-switch v-model="providerForm.is_on_prem" active-text="院内" inactive-text="院外" :disabled="!!editingProviderId" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="providerDialog = false">取消</el-button>
        <el-button type="primary" :loading="providerSaving" @click="saveProvider">
          {{ editingProviderId ? '保存修改' : '创建配置' }}
        </el-button>
      </template>
    </el-dialog>
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

.provider-head {
  display: flex;
  align-items: center;
  gap: 10px;
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
