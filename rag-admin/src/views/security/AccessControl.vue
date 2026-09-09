<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-select v-model="filterType" clearable placeholder="类型" style="width: 120px">
          <el-option label="黑名单" value="BLACK" />
          <el-option label="白名单" value="WHITE" />
        </el-select>
        <el-button type="primary" @click="showAddDialog">新增规则</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="ipAddress" label="IP地址" />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.type === 'BLACK' ? 'danger' : 'success'">
              {{ row.type === 'BLACK' ? '黑名单' : '白名单' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" show-overflow-tooltip />
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

    <el-dialog :title="editingRule?.id ? '编辑规则' : '新增规则'" v-model="dialogVisible" width="500px" @closed="resetForm">
      <el-form :model="form" ref="formRef" label-width="80px">
        <el-form-item label="IP地址" prop="ipAddress">
          <el-input v-model="form.ipAddress" placeholder="如 192.168.1.100" />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-radio-group v-model="form.type">
            <el-radio value="BLACK">黑名单</el-radio>
            <el-radio value="WHITE">白名单</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="原因" prop="reason">
          <el-input v-model="form.reason" type="textarea" :rows="2" />
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
import { ref, reactive, watch, onMounted } from 'vue'
import { getAccessControls, saveAccessControl, deleteAccessControl as deleteRuleApi } from '../../api/security'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const filterType = ref('')
const page = ref(1)
const total = ref(0)
const dialogVisible = ref(false)
const editingRule = ref(null)
const formRef = ref(null)

const form = reactive({ ipAddress: '', type: 'BLACK', reason: '', enabled: 1 })

const resetForm = () => {
  form.ipAddress = ''; form.type = 'BLACK'; form.reason = ''; form.enabled = 1
}

const loadData = async () => {
  loading.value = true
  try {
    const params = { pageNum: page.value, pageSize: 10 }
    if (filterType.value) params.type = filterType.value
    const res = await getAccessControls(params)
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
  Object.assign(form, { ipAddress: row.ipAddress, type: row.type, reason: row.reason || '', enabled: row.enabled })
  dialogVisible.value = true
}

const submitForm = async () => {
  try {
    const data = { ...form }
    if (editingRule.value?.id) {
      data.id = editingRule.value.id
    }
    await saveAccessControl(data)
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

watch(filterType, () => { page.value = 1; loadData() })
onMounted(loadData)
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; }
</style>