<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-button type="primary" @click="dialogVisible = true; editingMenu = null; resetForm()">新增菜单</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px" row-key="id" default-expand-all>
        <el-table-column prop="name" label="菜单名称" />
        <el-table-column prop="code" label="编码" />
        <el-table-column prop="path" label="路由路径" />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.type === 0 ? '' : row.type === 1 ? 'success' : 'warning'">
              {{ row.type === 0 ? '目录' : row.type === 1 ? '菜单' : '按钮' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="80" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editMenu(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteMenu(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog :title="editingMenu?.id ? '编辑菜单' : '新增菜单'" v-model="dialogVisible" width="500px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="上级菜单" prop="parentId">
          <el-tree-select v-model="form.parentId" :data="tableData" :props="{ label: 'name', value: 'id', children: 'children' }" check-strictly clearable placeholder="空为顶级菜单" style="width: 100%" />
        </el-form-item>
        <el-form-item label="菜单名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="路由路径" prop="path">
          <el-input v-model="form.path" />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-radio-group v-model="form.type">
            <el-radio :value="0">目录</el-radio>
            <el-radio :value="1">菜单</el-radio>
            <el-radio :value="2">按钮</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="图标" prop="icon">
          <el-input v-model="form.icon" placeholder="Element Plus 图标名" />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" />
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
import { getMenus, createMenu, updateMenu, deleteMenu as deleteMenuApi } from '../../api/menu'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const editingMenu = ref(null)
const formRef = ref(null)

const form = reactive({ parentId: null, name: '', code: '', path: '', type: 1, icon: '', sort: 0 })
const rules = {
  name: [{ required: true, message: '请输入菜单名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }]
}

const buildTree = (items, parentId = null) => {
  return items
    .filter(i => i.parentId === parentId)
    .sort((a, b) => (a.sort || 0) - (b.sort || 0))
    .map(i => ({ ...i, children: buildTree(items, i.id) }))
}

const resetForm = () => {
  form.parentId = null; form.name = ''; form.code = ''; form.path = ''; form.type = 1; form.icon = ''; form.sort = 0
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getMenus()
    const items = Array.isArray(res.data) ? res.data : []
    tableData.value = buildTree(items)
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

const editMenu = (row) => {
  editingMenu.value = row
  Object.assign(form, { parentId: row.parentId, name: row.name, code: row.code, path: row.path || '', type: row.type === 0 ? 0 : row.type === 1 ? 1 : 2, icon: row.icon || '', sort: row.sort || 0 })
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    const data = { ...form }
    if (editingMenu.value?.id) {
      await updateMenu(editingMenu.value.id, data)
    } else {
      await createMenu(data)
    }
    ElMessage.success('操作成功')
    dialogVisible.value = false
    loadData()
  } catch (e) { ElMessage.error('操作失败') }
}

const deleteMenu = async (id) => {
  await ElMessageBox.confirm('确定删除该菜单? 子菜单也会被删除', '提示', { type: 'warning' })
  try {
    await deleteMenuApi(id)
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