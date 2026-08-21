<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索用户名" style="width: 200px" clearable />
        <el-button type="primary" @click="dialogVisible = true; editingUser = null; resetForm()">新增用户</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="nickname" label="昵称" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="phone" label="手机号" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">{{ row.status === 1 ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="180" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editUser(row)">编辑</el-button>
            <el-button size="small" type="warning" @click="showResetPwd(row)">重置密码</el-button>
            <el-button size="small" type="danger" @click="deleteUser(row.id)">删除</el-button>
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

    <el-dialog :title="editingUser?.id ? '编辑用户' : '新增用户'" v-model="dialogVisible" width="500px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!editingUser?.id" />
        </el-form-item>
        <el-form-item label="密码" prop="password" v-if="!editingUser?.id">
          <el-input v-model="form.password" type="password" />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="form.nickname" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog title="重置密码" v-model="resetPwdVisible" width="400px">
      <el-form :model="pwdForm" ref="pwdFormRef" label-width="80px">
        <el-form-item label="新密码" prop="password" :rules="[{ required: true, message: '请输入新密码' }]">
          <el-input v-model="pwdForm.password" type="password" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdVisible = false">取消</el-button>
        <el-button type="primary" @click="submitResetPwd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { getUsers, createUser, updateUser, deleteUser as deleteUserApi, resetPassword } from '../../api/user'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const search = ref('')
const page = ref(1)
const total = ref(0)
const dialogVisible = ref(false)
const editingUser = ref(null)
const formRef = ref(null)
const resetPwdVisible = ref(false)
const resetPwdUserId = ref(null)
const pwdForm = reactive({ password: '' })
const pwdFormRef = ref(null)

const form = reactive({
  username: '', password: '', nickname: '', email: '', phone: '', status: 1
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur', min: 6 }],
  nickname: [{ required: true, message: '请输入昵称', trigger: 'blur' }]
}

const resetForm = () => {
  form.username = ''; form.password = ''; form.nickname = ''; form.email = ''; form.phone = ''; form.status = 1
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getUsers({ pageNum: page.value, pageSize: 10, keyword: search.value || undefined })
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

const editUser = (row) => {
  editingUser.value = row
  Object.assign(form, { username: row.username, nickname: row.nickname || '', email: row.email || '', phone: row.phone || '', status: row.status ?? 1 })
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    if (editingUser.value?.id) {
      await updateUser(editingUser.value.id, { ...form })
    } else {
      await createUser({ ...form })
    }
    ElMessage.success('操作成功')
    dialogVisible.value = false
    loadData()
  } catch (e) { ElMessage.error('操作失败') }
}

const deleteUser = async (id) => {
  await ElMessageBox.confirm('确定删除该用户?', '提示', { type: 'warning' })
  try {
    await deleteUserApi(id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

const showResetPwd = (row) => {
  resetPwdUserId.value = row.id
  pwdForm.password = ''
  resetPwdVisible.value = true
}

const submitResetPwd = async () => {
  const valid = await pwdFormRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    await resetPassword(resetPwdUserId.value, { password: pwdForm.password })
    ElMessage.success('密码重置成功')
    resetPwdVisible.value = false
  } catch (e) { ElMessage.error('重置失败') }
}

watch(search, () => { page.value = 1; loadData() })
onMounted(loadData)
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; }
</style>