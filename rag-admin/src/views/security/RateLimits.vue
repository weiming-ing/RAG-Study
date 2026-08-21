<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-button type="primary" @click="showAddDialog">新增限流规则</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="规则名称" />
        <el-table-column prop="targetType" label="目标类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.targetType === 'USER' ? 'success' : row.targetType === 'IP' ? 'warning' : 'info'">
              {{ row.targetType === 'USER' ? '用户' : row.targetType === 'IP' ? 'IP' : 'API-Key' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="targetValue" label="目标值" />
        <el-table-column prop="requestLimit" label="请求限制" width="120">
          <template #default="{ row }">{{ row.requestLimit }} 次/分</template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled === 1 ? 'success' : 'danger'">{{ row.enabled === 1 ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="180" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editRule(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteRule(row.id)">删除</el-button>
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

    <el-dialog :title="editingRule?.id ? '编辑限流规则' : '新增限流规则'" v-model="dialogVisible" width="500px" @closed="resetForm">
      <el-form :model="form" ref="formRef" label-width="100px">
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="目标类型" prop="targetType">
          <el-select v-model="form.targetType" style="width: 100%">
            <el-option label="用户" value="USER" />
            <el-option label="IP" value="IP" />
            <el-option label="API-Key" value="API_KEY" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标值" prop="targetValue">
          <el-input v-model="form.targetValue" :placeholder="form.targetType === 'IP' ? '如 192.168.1.1' : form.targetType === 'USER' ? '用户ID' : 'API-Key'" />
        </el-form-item>
        <el-form-item label="请求限制(次/分)" prop="requestLimit">
          <el-input-number v-model="form.requestLimit" :min="1" :max="100000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
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
import { ref, reactive, onMounted } from 'vue'
import { getRateLimits, saveRateLimit, deleteRateLimit as deleteRuleApi } from '../../api/security'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const page = ref(1)
const total = ref(0)
const dialogVisible = ref(false)
const editingRule = ref(null)
const formRef = ref(null)

const form = reactive({ name: '', targetType: 'USER', targetValue: '', requestLimit: 100, enabled: 1 })

const resetForm = () => {
  form.name = ''; form.targetType = 'USER'; form.targetValue = ''; form.requestLimit = 100; form.enabled = 1
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getRateLimits({ pageNum: page.value, pageSize: 10 })
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

const showAddDialog = () => { editingRule.value = null; resetForm(); dialogVisible.value = true }
const editRule = (row) => {
  editingRule.value = row
  Object.assign(form, { name: row.name, targetType: row.targetType, targetValue: row.targetValue, requestLimit: row.requestLimit, enabled: row.enabled })
  dialogVisible.value = true
}

const submitForm = async () => {
  try {
    const data = { ...form }
    if (editingRule.value?.id) {
      data.id = editingRule.value.id
    }
    await saveRateLimit(data)
    ElMessage.success('操作成功')
    dialogVisible.value = false
    loadData()
  } catch (e) { ElMessage.error('操作失败') }
}

const deleteRule = async (id) => {
  await ElMessageBox.confirm('确定删除该规则?', '提示', { type: 'warning' })
  try {
    await deleteRuleApi(id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

onMounted(loadData)
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; }
</style>