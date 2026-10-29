<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-button type="primary" @click="dialogVisible = true; editingMenu = null; resetForm()">新增菜单</el-button>
        <span class="tip">菜单保存后，需在"角色管理"中给角色分配菜单，用户重新登录后侧边栏生效</span>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px" row-key="id" default-expand-all>
        <el-table-column prop="menuName" label="菜单名称" />
        <el-table-column prop="permissionCode" label="权限编码" />
        <el-table-column prop="path" label="路由路径" />
        <el-table-column prop="menuType" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.menuType === 'DIRECTORY' ? '' : row.menuType === 'MENU' ? 'success' : 'warning'">
              {{ menuTypeText(row.menuType) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="visible" label="可见" width="80">
          <template #default="{ row }">
            <el-tag :type="row.visible === 0 ? 'info' : 'success'">{{ row.visible === 0 ? '隐藏' : '显示' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sortOrder" label="排序" width="80" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editMenu(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteMenu(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog :title="editingMenu?.id ? '编辑菜单' : '新增菜单'" v-model="dialogVisible" width="500px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="上级菜单" prop="parentId">
          <el-tree-select v-model="form.parentId" :data="tableData" :props="{ label: 'menuName', value: 'id', children: 'children' }" check-strictly clearable placeholder="空为顶级菜单" style="width: 100%" />
        </el-form-item>
        <el-form-item label="菜单名称" prop="menuName">
          <el-input v-model="form.menuName" />
        </el-form-item>
        <el-form-item label="权限编码" prop="permissionCode">
          <el-input v-model="form.permissionCode" placeholder="如 kb:view，可为空" />
        </el-form-item>
        <el-form-item label="路由路径" prop="path">
          <el-input v-model="form.path" placeholder="如 /users，目录可空" />
        </el-form-item>
        <el-form-item label="组件路径" prop="component">
          <el-input v-model="form.component" placeholder="如 system/UserList，可空" />
        </el-form-item>
        <el-form-item label="类型" prop="menuType">
          <el-radio-group v-model="form.menuType">
            <el-radio value="DIRECTORY">目录</el-radio>
            <el-radio value="MENU">菜单</el-radio>
            <el-radio value="BUTTON">按钮</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="图标" prop="icon">
          <el-input v-model="form.icon" placeholder="Element Plus 图标名" />
        </el-form-item>
        <el-form-item label="排序" prop="sortOrder">
          <el-input-number v-model="form.sortOrder" :min="0" />
        </el-form-item>
        <el-form-item label="侧边栏可见" prop="visible">
          <el-switch v-model="form.visible" :active-value="1" :inactive-value="0" />
          <span class="tip" style="margin-left: 8px">隐藏用于带路径参数的详情页（不进侧边栏，仅作权限归属）</span>
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
// 字段与后端 MenuCreateRequest/MenuVO 对齐（menuName/permissionCode/menuType/
// sortOrder/visible）。旧版发送 name/code/type/sort，导致 INSERT 时 menu_name
// 无值直接 SQL 报错——这就是"菜单管理跑不通"的根因。
import { ref, reactive, onMounted } from 'vue'
import { getMenus, createMenu, updateMenu, deleteMenu as deleteMenuApi } from '../../api/menu'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const editingMenu = ref(null)
const formRef = ref(null)

const form = reactive({
  parentId: null, menuName: '', permissionCode: '', path: '', component: '',
  menuType: 'MENU', icon: '', sortOrder: 0, visible: 1
})
const rules = {
  menuName: [{ required: true, message: '请输入菜单名称', trigger: 'blur' }]
}

const menuTypeText = (t) => ({ DIRECTORY: '目录', MENU: '菜单', BUTTON: '按钮' }[t] || t || '菜单')

const resetForm = () => {
  form.parentId = null; form.menuName = ''; form.permissionCode = ''; form.path = ''
  form.component = ''; form.menuType = 'MENU'; form.icon = ''; form.sortOrder = 0; form.visible = 1
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getMenus()
    // 后端返回的就是树（MenuVO.children），空 children 置 undefined 以免树表格误渲染
    tableData.value = (Array.isArray(res.data) ? res.data : []).map(n => ({
      ...n,
      children: (n.children && n.children.length > 0) ? n.children : undefined
    }))
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

const editMenu = (row) => {
  editingMenu.value = row
  Object.assign(form, {
    parentId: row.parentId || null, menuName: row.menuName || '',
    permissionCode: row.permissionCode || '', path: row.path || '', component: row.component || '',
    menuType: row.menuType || 'MENU', icon: row.icon || '', sortOrder: row.sortOrder ?? 0,
    visible: row.visible ?? 1
  })
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    const data = { ...form, parentId: form.parentId ?? 0 }
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
.tip { font-size: 12px; color: #909399; }
</style>
