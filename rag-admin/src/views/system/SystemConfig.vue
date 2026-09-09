<template>
  <div class="system-config">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>系统配置管理</span>
          <el-button type="primary" @click="handleAdd">新增配置</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="配置分组">
          <el-select v-model="searchForm.group" placeholder="全部" clearable>
            <el-option label="GENERAL" value="GENERAL" />
            <el-option label="LLM" value="LLM" />
            <el-option label="RAG" value="RAG" />
            <el-option label="SECURITY" value="SECURITY" />
            <el-option label="EMAIL" value="EMAIL" />
            <el-option label="STORAGE" value="STORAGE" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="searchForm.keyword" placeholder="搜索配置键或描述" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="tableData" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="configKey" label="配置键" min-width="180" />
        <el-table-column prop="configValue" label="配置值" min-width="200">
          <template #default="{ row }">
            <span v-if="row.configType === 'BOOLEAN'">
              <el-tag :type="row.configValue === 'true' ? 'success' : 'danger'" size="small">
                {{ row.configValue === 'true' ? '启用' : '禁用' }}
              </el-tag>
            </span>
            <span v-else-if="row.configType === 'JSON'" class="json-value">
              <el-tooltip :content="row.configValue" placement="top">
                <span>{{ truncate(row.configValue, 40) }}</span>
              </el-tooltip>
            </span>
            <span v-else>{{ maskSecret(row.configKey, row.configValue) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="configType" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.configType }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="configGroup" label="分组" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="groupTagType(row.configGroup)">{{ row.configGroup }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
        <el-table-column prop="enabled" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled === 1 ? 'success' : 'info'" size="small">
              {{ row.enabled === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
        class="pagination"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="550px" @close="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="配置键" prop="configKey">
          <el-input v-model="form.configKey" placeholder="如: system.name" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="配置值" prop="configValue">
          <el-input v-if="form.configType === 'STRING' || form.configType === 'NUMBER'" v-model="form.configValue" placeholder="配置值" />
          <el-input v-else-if="form.configType === 'JSON'" v-model="form.configValue" type="textarea" :rows="4" placeholder="JSON格式" />
          <el-switch v-else-if="form.configType === 'BOOLEAN'" v-model="form.configValue" active-value="true" inactive-value="false" />
        </el-form-item>
        <el-form-item label="配置类型" prop="configType">
          <el-select v-model="form.configType" :disabled="isEdit">
            <el-option label="STRING" value="STRING" />
            <el-option label="NUMBER" value="NUMBER" />
            <el-option label="BOOLEAN" value="BOOLEAN" />
            <el-option label="JSON" value="JSON" />
          </el-select>
        </el-form-item>
        <el-form-item label="配置分组" prop="configGroup">
          <el-select v-model="form.configGroup">
            <el-option label="GENERAL" value="GENERAL" />
            <el-option label="LLM" value="LLM" />
            <el-option label="RAG" value="RAG" />
            <el-option label="SECURITY" value="SECURITY" />
            <el-option label="EMAIL" value="EMAIL" />
            <el-option label="STORAGE" value="STORAGE" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" placeholder="配置描述" />
        </el-form-item>
        <el-form-item label="排序" prop="sortOrder">
          <el-input-number v-model="form.sortOrder" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getConfigs, saveConfig, updateConfig, deleteConfig } from '../../api/system'

const loading = ref(false)
const tableData = ref([])
const page = ref(1)
const size = ref(20)
const total = ref(0)

const searchForm = reactive({ group: '', keyword: '' })

const dialogVisible = ref(false)
const dialogTitle = ref('新增配置')
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  configKey: '',
  configValue: '',
  configType: 'STRING',
  configGroup: 'GENERAL',
  description: '',
  sortOrder: 0,
  enabled: 1
})

const rules = {
  configKey: [{ required: true, message: '请输入配置键', trigger: 'blur' }],
  configValue: [{ required: true, message: '请输入配置值', trigger: 'blur' }],
  configType: [{ required: true, message: '请选择配置类型', trigger: 'change' }],
  configGroup: [{ required: true, message: '请选择配置分组', trigger: 'change' }]
}

function resetForm() {
  formRef.value?.resetFields()
  form.id = null
  form.configKey = ''
  form.configValue = ''
  form.configType = 'STRING'
  form.configGroup = 'GENERAL'
  form.description = ''
  form.sortOrder = 0
  form.enabled = 1
}

function groupTagType(group) {
  const map = { GENERAL: '', LLM: 'warning', RAG: 'success', SECURITY: 'danger', EMAIL: 'info', STORAGE: 'primary' }
  return map[group] || ''
}

function maskSecret(key, value) {
  if (!value) return value
  const lower = key.toLowerCase()
  if (lower.includes('password') || lower.includes('secret') || lower.includes('api_key') || lower.includes('key')) {
    if (value.length <= 4) return '****'
    return value.substring(0, 2) + '****' + value.substring(value.length - 2)
  }
  return value
}

function truncate(text, len) {
  if (!text) return ''
  return text.length > len ? text.substring(0, len) + '...' : text
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getConfigs({ group: searchForm.group || undefined, keyword: searchForm.keyword || undefined, page: page.value, size: size.value })
    tableData.value = res.data.records
    total.value = res.data.total
  } catch (e) {
    ElMessage.error('获取配置列表失败')
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  searchForm.group = ''
  searchForm.keyword = ''
  page.value = 1
  fetchData()
}

function handleAdd() {
  isEdit.value = false
  dialogTitle.value = '新增配置'
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row) {
  isEdit.value = true
  dialogTitle.value = '编辑配置'
  form.id = row.id
  form.configKey = row.configKey
  form.configValue = row.configValue
  form.configType = row.configType
  form.configGroup = row.configGroup
  form.description = row.description || ''
  form.sortOrder = row.sortOrder || 0
  form.enabled = row.enabled
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateConfig(form.id, { ...form })
      ElMessage.success('更新成功')
    } else {
      await saveConfig({ ...form })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除配置 "${row.configKey}" 吗？`, '确认删除', { type: 'warning' })
  try {
    await deleteConfig(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(fetchData)
</script>

<style scoped>
.system-config {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.search-form {
  margin-bottom: 16px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
.json-value {
  font-family: monospace;
  font-size: 12px;
}
</style>