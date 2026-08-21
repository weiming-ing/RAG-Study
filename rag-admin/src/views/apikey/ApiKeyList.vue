<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索密钥名称" style="width: 200px" clearable />
        <el-button type="primary" @click="showAddDialog">生成密钥</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="keyName" label="密钥名称" />
        <el-table-column prop="apiKey" label="API Key" show-overflow-tooltip min-width="200" />
        <el-table-column prop="enabled" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled === 1 ? 'success' : 'danger'">{{ row.enabled === 1 ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rateLimit" label="频率限制" width="100">
          <template #default="{ row }">{{ row.rateLimit }} 次/分</template>
        </el-table-column>
        <el-table-column prop="dailyLimit" label="每日限制" width="100">
          <template #default="{ row }">{{ row.dailyLimit }} 次</template>
        </el-table-column>
        <el-table-column prop="totalCalls" label="总调用" width="100" />
        <el-table-column prop="lastUsedTime" label="最后使用" width="180" />
        <el-table-column prop="expireTime" label="过期时间" width="180">
          <template #default="{ row }">
            <span v-if="!row.expireTime" style="color: #67c23a">永不过期</span>
            <span v-else :style="{ color: new Date(row.expireTime) < new Date() ? 'red' : '#606266' }">{{ row.expireTime }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editKey(row)">编辑</el-button>
            <el-button size="small" :type="row.enabled === 1 ? 'warning' : 'success'" @click="toggleKey(row)">
              {{ row.enabled === 1 ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" @click="deleteKey(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        style="margin-top: 16px; justify-content: flex-end"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadData"
      />
    </el-card>

    <el-dialog :title="editingKey?.id ? '编辑密钥' : '生成密钥'" v-model="dialogVisible" width="500px" @closed="resetForm">
      <el-form :model="form" ref="formRef" label-width="100px">
        <el-form-item label="密钥名称" prop="keyName">
          <el-input v-model="form.keyName" />
        </el-form-item>
        <el-form-item label="频率限制(次/分)" prop="rateLimit">
          <el-input-number v-model="form.rateLimit" :min="1" :max="100000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="每日限制" prop="dailyLimit">
          <el-input-number v-model="form.dailyLimit" :min="1" :max="1000000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="过期时间" prop="expireTime">
          <el-date-picker v-model="form.expireTime" type="datetime" placeholder="留空为永不过期" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { getApiKeys, generateApiKey, updateApiKey, deleteApiKey as deleteKeyApi } from '../../api/apikey'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const search = ref('')
const page = ref(1)
const total = ref(0)
const dialogVisible = ref(false)
const editingKey = ref(null)
const formRef = ref(null)

const form = reactive({ keyName: '', rateLimit: 1000, dailyLimit: 10000, expireTime: null, description: '' })

const resetForm = () => {
  form.keyName = ''; form.rateLimit = 1000; form.dailyLimit = 10000; form.expireTime = null; form.description = ''
}

const loadData = async () => {
  loading.value = true
  try {
    const params = { pageNum: page.value, pageSize: 10, keyword: search.value || undefined }
    const res = await getApiKeys(params)
    if (res.data?.records) {
      tableData.value = res.data.records
      total.value = res.data.total || 0
    } else {
      tableData.value = Array.isArray(res.data) ? res.data : []
      total.value = tableData.value.length
    }
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

const showAddDialog = () => { editingKey.value = null; resetForm(); dialogVisible.value = true }

const editKey = (row) => {
  editingKey.value = row
  Object.assign(form, {
    keyName: row.keyName, rateLimit: row.rateLimit || 1000,
    dailyLimit: row.dailyLimit || 10000, expireTime: row.expireTime || null,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const submitForm = async () => {
  try {
    const data = {
      keyName: form.keyName, rateLimit: form.rateLimit, dailyLimit: form.dailyLimit,
      expireTime: form.expireTime, description: form.description,
      userId: 1, kbIds: '[]', permissions: '["read","search"]'
    }
    if (editingKey.value?.id) {
      await updateApiKey(editingKey.value.id, data)
    } else {
      const res = await generateApiKey(data)
      ElMessage.success('密钥生成成功: ' + (res.data?.apiKey || ''))
    }
    dialogVisible.value = false
    loadData()
  } catch (e) { ElMessage.error('操作失败') }
}

const toggleKey = async (row) => {
  try {
    await updateApiKey(row.id, { enabled: row.enabled === 1 ? 0 : 1 })
    ElMessage.success('操作成功')
    loadData()
  } catch (e) { ElMessage.error('操作失败') }
}

const deleteKey = async (id) => {
  await ElMessageBox.confirm('确定删除该密钥? 删除后相关API将无法使用', '提示', { type: 'warning' })
  try {
    await deleteKeyApi(id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

watch(search, () => { page.value = 1; loadData() })
onMounted(loadData)
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; }
</style>