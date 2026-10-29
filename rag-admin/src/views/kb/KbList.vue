<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索知识库" style="width: 200px" clearable />
        <el-button type="primary" @click="dialogVisible = true; editingKb = null; resetForm()">新增知识库</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="知识库名称" />
        <el-table-column label="访问级别" width="110">
          <template #default="{ row }">
            <el-tag :type="visibilityTagType(row.visibilityLevel)">
              {{ visibilityText(row.visibilityLevel) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="embeddingModel" label="嵌入模型" width="150" />
        <el-table-column prop="docCount" label="文档数" width="100" />
        <el-table-column prop="createTime" label="创建时间" width="180" />
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="$router.push(`/kb/${row.id}/documents`)">文档</el-button>
            <el-button size="small" @click="editKb(row)">编辑</el-button>
            <el-button size="small" type="success" @click="$router.push(`/kb/${row.id}/config`)">配置</el-button>
            <el-button size="small" type="danger" @click="deleteKb(row.id)">删除</el-button>
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

    <el-dialog :title="editingKb?.id ? '编辑知识库' : '新增知识库'" v-model="dialogVisible" width="600px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="访问级别" prop="visibility">
          <el-select v-model="form.visibility" style="width: 100%">
            <el-option label="公共级（所有人，含访客）" value="PUBLIC" />
            <el-option label="员工级（所有登录用户）" value="EMPLOYEE" />
            <el-option label="管理级（仅授权用户）" value="MANAGEMENT" />
          </el-select>
          <div class="form-tip">管理级知识库需在"配置 → 访问权限"中给具体用户授权后方可检索</div>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="嵌入模型" prop="embeddingModel">
          <el-select v-model="form.embeddingModel" style="width: 100%">
            <el-option label="text-embedding-ada-002" value="text-embedding-ada-002" />
            <el-option label="bge-large-zh" value="bge-large-zh" />
            <el-option label="m3e-base" value="m3e-base" />
          </el-select>
        </el-form-item>
        <el-form-item label="分块大小" prop="chunkSize">
          <el-input-number v-model="form.chunkSize" :min="100" :max="5000" :step="100" />
        </el-form-item>
        <el-form-item label="分块重叠" prop="chunkOverlap">
          <el-input-number v-model="form.chunkOverlap" :min="0" :max="1000" :step="10" />
        </el-form-item>
        <el-form-item label="Top K" prop="topK">
          <el-input-number v-model="form.topK" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="相似度阈值" prop="similarityThreshold">
          <el-slider v-model="form.similarityThreshold" :min="0" :max="1" :step="0.05" show-input />
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
import { getKbs, createKb, updateKb, deleteKb as deleteKbApi } from '../../api/kb'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const search = ref('')
const page = ref(1)
const total = ref(0)
const dialogVisible = ref(false)
const editingKb = ref(null)
const formRef = ref(null)

const form = reactive({
  name: '', description: '', embeddingModel: 'text-embedding-ada-002',
  visibility: 'EMPLOYEE',
  chunkSize: 500, chunkOverlap: 50, topK: 5, similarityThreshold: 0.7
})

const rules = {
  name: [{ required: true, message: '请输入知识库名称', trigger: 'blur' }]
}

// 三级可见级别展示（与 Java KnowledgeBaseManageService.VIS_* 对应）
const visibilityText = (v) => ({ PUBLIC: '公共级', EMPLOYEE: '员工级', MANAGEMENT: '管理级' }[v] || v || '员工级')
const visibilityTagType = (v) => ({ PUBLIC: 'success', EMPLOYEE: '', MANAGEMENT: 'danger' }[v] || 'info')

const resetForm = () => {
  form.name = ''; form.description = ''; form.embeddingModel = 'text-embedding-ada-002'
  form.visibility = 'EMPLOYEE'
  form.chunkSize = 500; form.chunkOverlap = 50; form.topK = 5; form.similarityThreshold = 0.7
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getKbs({ pageNum: page.value, pageSize: 10, keyword: search.value || undefined })
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

const editKb = (row) => {
  editingKb.value = row
  Object.assign(form, {
    name: row.name, description: row.description || '', embeddingModel: row.embeddingModel || 'text-embedding-ada-002',
    visibility: row.visibilityLevel || 'EMPLOYEE',
    chunkSize: row.chunkSize || 500, chunkOverlap: row.chunkOverlap || 50, topK: row.topK || 5, similarityThreshold: row.similarityThreshold || 0.7
  })
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    if (editingKb.value?.id) {
      await updateKb(editingKb.value.id, { ...form })
    } else {
      await createKb({ ...form })
    }
    ElMessage.success('操作成功')
    dialogVisible.value = false
    loadData()
  } catch (e) { ElMessage.error('操作失败') }
}

const deleteKb = async (id) => {
  await ElMessageBox.confirm('确定删除该知识库? 关联文档也会被删除', '提示', { type: 'warning' })
  try {
    await deleteKbApi(id)
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
.form-tip { font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px; }
</style>