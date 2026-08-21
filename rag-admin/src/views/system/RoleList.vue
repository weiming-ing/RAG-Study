<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索角色名称" style="width: 200px" clearable />
        <el-button type="primary" @click="dialogVisible = true; editingRole = null; resetForm()">新增角色</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="roleName" label="角色名称" />
        <el-table-column prop="roleCode" label="角色编码" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="createTime" label="创建时间" width="180" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editRole(row)">编辑</el-button>
            <el-button size="small" type="success" @click="showMenus(row)">分配菜单</el-button>
            <el-button size="small" type="danger" @click="deleteRole(row.id)">删除</el-button>
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

    <el-dialog :title="editingRole?.id ? '编辑角色' : '新增角色'" v-model="dialogVisible" width="500px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="角色名称" prop="roleName">
          <el-input v-model="form.roleName" />
        </el-form-item>
        <el-form-item label="角色编码" prop="roleCode">
          <el-input v-model="form.roleCode" :disabled="!!editingRole?.id" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog title="分配菜单" v-model="menuVisible" width="400px">
      <el-tree ref="treeRef" :data="menuTree" show-checkbox node-key="id" :props="{ label: 'name', children: 'children' }" :default-checked-keys="checkedMenuIds" />
      <template #footer>
        <el-button @click="menuVisible = false">取消</el-button>
        <el-button type="primary" @click="submitMenus">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, nextTick } from 'vue'
import { getRoles, createRole, updateRole, deleteRole as deleteRoleApi, getRoleMenus, updateRoleMenus } from '../../api/role'
import { getMenus } from '../../api/menu'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const search = ref('')
const page = ref(1)
const total = ref(0)
const dialogVisible = ref(false)
const editingRole = ref(null)
const formRef = ref(null)
const menuVisible = ref(false)
const menuTree = ref([])
const checkedMenuIds = ref([])
const currentRoleId = ref(null)
const treeRef = ref(null)

const form = reactive({ roleName: '', roleCode: '', description: '' })
const rules = {
  roleName: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  roleCode: [{ required: true, message: '请输入角色编码', trigger: 'blur' }]
}

const resetForm = () => {
  form.roleName = ''; form.roleCode = ''; form.description = ''
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getRoles({ pageNum: page.value, pageSize: 10, keyword: search.value || undefined })
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

const editRole = (row) => {
  editingRole.value = row
  Object.assign(form, { roleName: row.roleName, roleCode: row.roleCode, description: row.description || '' })
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    if (editingRole.value?.id) {
      await updateRole(editingRole.value.id, { ...form })
    } else {
      await createRole({ ...form })
    }
    ElMessage.success('操作成功')
    dialogVisible.value = false
    loadData()
  } catch (e) { ElMessage.error('操作失败') }
}

const deleteRole = async (id) => {
  await ElMessageBox.confirm('确定删除该角色?', '提示', { type: 'warning' })
  try {
    await deleteRoleApi(id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

const showMenus = async (row) => {
  currentRoleId.value = row.id
  try {
    const [trees, rms] = await Promise.all([getMenus(), getRoleMenus(row.id)])
    menuTree.value = Array.isArray(trees.data) ? trees.data : []
    checkedMenuIds.value = Array.isArray(rms.data) ? rms.data : (rms.data?.menuIds || [])
  } catch (e) { console.error(e) }
  menuVisible.value = true
}

const submitMenus = async () => {
  const keys = treeRef.value.getCheckedKeys()
  const halfKeys = treeRef.value.getHalfCheckedKeys()
  try {
    await updateRoleMenus(currentRoleId.value, { menuIds: [...keys, ...halfKeys] })
    ElMessage.success('菜单分配成功')
    menuVisible.value = false
  } catch (e) { ElMessage.error('分配失败') }
}

watch(search, () => { page.value = 1; loadData() })
onMounted(loadData)
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; }
</style>