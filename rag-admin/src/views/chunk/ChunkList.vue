<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-select v-model="filterKbId" clearable placeholder="筛选知识库" style="width: 200px">
          <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
        </el-select>
        <el-input v-model="search" placeholder="搜索分块内容" style="width: 260px" clearable />
        <el-button type="success" @click="rebuildDialogVisible = true">重建向量索引</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="docName" label="文档" width="180" show-overflow-tooltip />
        <el-table-column prop="content" label="内容" show-overflow-tooltip>
          <template #default="{ row }">{{ (row.content || '').substring(0, 120) }}{{ (row.content || '').length > 120 ? '...' : '' }}</template>
        </el-table-column>
        <el-table-column prop="chunkIndex" label="索引" width="80" />
        <el-table-column prop="tokenCount" label="Token数" width="100" />
        <el-table-column prop="createTime" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editChunk(row)">编辑</el-button>
            <el-button size="small" type="warning" @click="splitChunk(row)">拆分</el-button>
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

    <el-dialog title="编辑分块" v-model="dialogVisible" width="600px">
      <el-form :model="form" ref="formRef" label-width="80px">
        <el-form-item label="内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog title="拆分分块" v-model="splitVisible" width="500px">
      <el-form :model="splitForm" ref="splitFormRef" label-width="100px">
        <el-form-item label="拆分位置" prop="position">
          <el-input-number v-model="splitForm.position" :min="1" :max="(form.content || '').length" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="splitVisible = false">取消</el-button>
        <el-button type="primary" @click="submitSplit">确认拆分</el-button>
      </template>
    </el-dialog>

    <el-dialog title="重建向量索引" v-model="rebuildDialogVisible" width="400px">
      <p>选择要重建向量索引的知识库：</p>
      <el-select v-model="rebuildKbId" placeholder="选择知识库" style="width: 100%">
        <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
      </el-select>
      <template #footer>
        <el-button @click="rebuildDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="rebuilding" @click="rebuild">确认重建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { getChunks, updateChunk, splitChunk as splitChunkApi, rebuildKbVectors } from '../../api/chunk'
import { getKbs } from '../../api/kb'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const search = ref('')
const filterKbId = ref(null)
const page = ref(1)
const total = ref(0)
const kbList = ref([])
const dialogVisible = ref(false)
const editingChunk = ref(null)
const formRef = ref(null)
const splitVisible = ref(false)
const splitFormRef = ref(null)
const rebuildDialogVisible = ref(false)
const rebuildKbId = ref(null)
const rebuilding = ref(false)

const form = reactive({ content: '' })
const splitForm = reactive({ position: 1 })

const loadKbList = async () => {
  try {
    const res = await getKbs({ size: 1000 })
    kbList.value = Array.isArray(res.data) ? res.data : (res.data?.records || [])
  } catch (e) { console.error(e) }
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getChunks({ pageNum: page.value, pageSize: 10, keyword: search.value || undefined, kbId: filterKbId.value || undefined })
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

const editChunk = (row) => {
  editingChunk.value = row
  form.content = row.content || ''
  dialogVisible.value = true
}

const submitForm = async () => {
  try {
    await updateChunk(editingChunk.value.id, { content: form.content })
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadData()
  } catch (e) { ElMessage.error('保存失败') }
}

const splitChunk = (row) => {
  editingChunk.value = row
  form.content = row.content || ''
  splitForm.position = Math.floor((row.content || '').length / 2)
  splitVisible.value = true
}

const submitSplit = async () => {
  try {
    await splitChunkApi(editingChunk.value.id, { position: splitForm.position })
    ElMessage.success('拆分成功')
    splitVisible.value = false
    loadData()
  } catch (e) { ElMessage.error('拆分失败') }
}

const rebuild = async () => {
  if (!rebuildKbId.value) { ElMessage.warning('请选择知识库'); return }
  rebuilding.value = true
  try {
    await rebuildKbVectors(rebuildKbId.value)
    ElMessage.success('向量索引重建已触发')
    rebuildDialogVisible.value = false
  } catch (e) { ElMessage.error('重建失败') }
  finally { rebuilding.value = false }
}

watch([search, filterKbId], () => { page.value = 1; loadData() })
onMounted(() => { loadKbList(); loadData() })
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; }
</style>