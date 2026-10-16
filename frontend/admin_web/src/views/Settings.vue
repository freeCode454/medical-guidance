<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { org, providers } from '@/api/admin'

const orgInfo = ref<any>(null)
const configs = ref<any[]>([])
const providerList = ref<any[]>([])

async function load() {
  try {
    ;[orgInfo.value, configs.value, providerList.value] = await Promise.all([
      org.get(),
      org.configs().then((d) => d.items),
      providers.list().then((d) => d.items),
    ])
  } catch (e) {
    ElMessage.error((e as Error).message || '加载失败')
  }
}

async function onSaveOrg() {
  try {
    await org.update(orgInfo.value)
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error((e as Error).message || '保存失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <el-card shadow="never" class="mb">
      <template #header><h3>机构信息</h3></template>
      <el-form v-if="orgInfo" label-width="90px" style="max-width: 480px">
        <el-form-item label="机构名称"><el-input v-model="orgInfo.tenant_name" /></el-form-item>
        <el-form-item label="医院等级"><el-input v-model="orgInfo.hospital_level" /></el-form-item>
        <el-form-item label="联系人"><el-input v-model="orgInfo.contact_person" /></el-form-item>
        <el-form-item label="联系电话"><el-input v-model="orgInfo.contact_phone" /></el-form-item>
        <el-button type="primary" @click="onSaveOrg">保存机构信息</el-button>
      </el-form>
    </el-card>

    <el-card shadow="never" class="mb">
      <template #header><h3>系统配置</h3></template>
      <el-table :data="configs" size="small">
        <el-table-column prop="config_key" label="配置键" width="260" />
        <el-table-column prop="config_value" label="值" show-overflow-tooltip />
        <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header><h3>模型配置</h3></template>
      <el-table :data="providerList" size="small">
        <el-table-column prop="provider_type" label="类型" width="110" />
        <el-table-column prop="provider_name" label="名称" width="160" />
        <el-table-column prop="base_url" label="地址" min-width="240" show-overflow-tooltip />
        <el-table-column prop="model_name" label="模型" width="180" show-overflow-tooltip />
        <el-table-column label="默认" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" size="small">默认</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="院内" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_on_prem" type="warning" size="small">院内</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
h3 { font-size: 15px; margin: 0; }
.mb { margin-bottom: 16px; }
</style>
