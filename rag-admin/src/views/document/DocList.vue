<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-button v-if="scopedKbId !== null" @click="$router.push('/kb')">← 返回知识库</el-button>
        <el-select v-model="filterKbId" :disabled="scopedKbId !== null" clearable placeholder="筛选知识库" style="width: 200px">
          <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
        </el-select>
        <el-input v-model="search" placeholder="搜索文档" style="width: 200px" clearable />
        <el-button type="primary" @click="showUpload">上传文档</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="文档名称" show-overflow-tooltip />
        <el-table-column prop="kbName" label="知识库" width="150" />
        <el-table-column prop="fileType" label="类型" width="80" />
        <el-table-column prop="fileSize" label="大小" width="100">
          <template #default="{ row }">{{ formatFileSize(row.fileSize) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunkCount" label="分块数" width="100" />
        <el-table-column prop="createTime" label="上传时间" width="180" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewContent(row)">内容</el-button>
            <el-button size="small" type="primary" @click="viewChunks(row)">分块</el-button>
            <el-button size="small" type="warning" @click="reparse(row)">重新解析</el-button>
            <el-button size="small" type="danger" @click="deleteDoc(row)">删除</el-button>
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

    <el-dialog title="上传文档" v-model="uploadVisible" width="500px">
      <el-upload
        ref="uploadRef"
        drag
        :action="uploadUrl"
        :headers="uploadHeaders"
        :data="uploadData"
        :on-success="onUploadSuccess"
        :on-error="onUploadError"
        :before-upload="beforeUpload"
        multiple
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 PDF, Word, PPT, Excel, TXT, Markdown, HTML 等格式（Docling 解析）</div>
        </template>
      </el-upload>
      <div style="margin-top: 12px">
        <el-select v-model="uploadKbId" placeholder="选择知识库" style="width: 100%">
          <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
        </el-select>
      </div>
    </el-dialog>

    <el-dialog title="文档内容" v-model="contentVisible" width="700px">
      <div v-html="renderedContent" style="max-height: 500px; overflow-y: auto; white-space: pre-wrap; font-family: monospace; font-size: 13px; background: #f5f5f5; padding: 16px; border-radius: 4px;"></div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDocs, getDocsAll, uploadDoc, deleteDoc as deleteDocApi, reparseDoc, getDocContent } from '../../api/doc'
import { getKbs } from '../../api/kb'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
// 钻取模式：从知识库列表进入时带 kbId 路由参数，KB 选择锁定
const scopedKbId = route.params.kbId ? Number(route.params.kbId) : null

const loading = ref(false)
const tableData = ref([])
const search = ref('')
const filterKbId = ref(scopedKbId)
const page = ref(1)
const total = ref(0)
const kbList = ref([])
const uploadVisible = ref(false)
const uploadKbId = ref(null)
const uploadRef = ref(null)
const contentVisible = ref(false)
const renderedContent = ref('')

const uploadUrl = computed(() => `/api/knowledge/${uploadKbId.value || 0}/documents/upload`)
const uploadHeaders = { Authorization: `Bearer ${localStorage.getItem('token') || ''}` }
const uploadData = reactive({})

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++ }
  return size.toFixed(1) + ' ' + units[i]
}

const isCompleted = (status) => status === 'READY' || status === 'indexed' || status === 'COMPLETED'
const isProcessing = (status) => status === 'PARSING' || status === 'processing' || status === 'PROCESSING'
// 未提取到正文（典型为扫描件 PDF）：文档已入库但内容为空，检索不到，需要 OCR
const isNeedsOcr = (status) => status === 'NEEDS_OCR' || status === 'needs_ocr'
const statusTagType = (status) => {
  if (isCompleted(status)) return 'success'
  if (isProcessing(status) || isNeedsOcr(status)) return 'warning'
  return 'danger'
}
const statusText = (status) => {
  if (isNeedsOcr(status)) return '需OCR'
  if (isCompleted(status)) return '已完成'
  if (isProcessing(status)) return '处理中'
  if (status === 'FAILED' || status === 'failed') return '失败'
  return status || '未知'
}

const loadKbList = async () => {
  try {
    const res = await getKbs({ size: 1000 })
    kbList.value = Array.isArray(res.data) ? res.data : (res.data?.records || [])
  } catch (e) {
    console.error('获取知识库列表失败:', e)
    ElMessage.error('获取知识库列表失败，请检查后端服务是否正常')
  }
}

const loadData = async () => {
  const kbId = filterKbId.value ?? (kbList.value[0]?.id ?? null)
  if (kbId === null) { tableData.value = []; total.value = 0; return }
  loading.value = true
  try {
    const params = { pageNum: page.value, pageSize: 10, keyword: search.value || undefined }
    let res
    if (kbId === 0) {
      // kbId=0 表示"全部知识库"，调用不带 kbId 的接口
      res = await getDocsAll(params)
    } else {
      res = await getDocs(kbId, params)
    }
    if (res.data?.records) {
      tableData.value = res.data.records
      total.value = res.data.total || 0
    } else {
      tableData.value = Array.isArray(res.data) ? res.data : []
      total.value = tableData.value.length
    }
  } catch (e) {
    console.error('获取文档列表失败:', e)
    ElMessage.error('获取文档列表失败，请刷新重试')
    tableData.value = []
    total.value = 0
  } finally { loading.value = false }
}

const showUpload = () => {
  if (scopedKbId !== null) uploadKbId.value = scopedKbId
  uploadVisible.value = true
}
const viewChunks = (row) => {
  const kbId = row.kbId ?? scopedKbId ?? filterKbId.value
  router.push(`/kb/${kbId}/documents/${row.id}/chunks`)
}
const beforeUpload = () => { return !!uploadKbId.value }
const onUploadSuccess = () => {
  // 上传接口已改为异步处理：立即返回 PARSING，后台完成切片/向量化/索引
  ElMessage.success('上传成功，文档解析中，完成后状态自动更新')
  uploadVisible.value = false
  loadData()
  startStatusPolling()
}
const onUploadError = (err) => {
  console.error('上传失败:', err)
  const msg = err?.response?.data?.message || err?.message || '服务器异常'
  ElMessage.error('上传失败: ' + msg)
}

// ===== 解析状态轮询：列表中存在处理中的文档时每 3s 刷新，全部到终态后停止 =====
let pollTimer = null
const hasProcessingDocs = () => tableData.value.some((d) => isProcessing(d.status))
const startStatusPolling = () => {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    if (!hasProcessingDocs()) { stopStatusPolling(); return }
    await loadData()
    if (!hasProcessingDocs()) stopStatusPolling()
  }, 3000)
}
const stopStatusPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}
onBeforeUnmount(stopStatusPolling)

const deleteDoc = async (row) => {
  await ElMessageBox.confirm('确定删除该文档?', '提示', { type: 'warning' })
  try {
    await deleteDocApi(row.kbId || filterKbId.value, row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除失败:', e)
      const msg = e?.response?.data?.message || e?.message || '未知错误'
      ElMessage.error('删除失败: ' + msg)
    }
  }
}

const reparse = async (row) => {
  try {
    await reparseDoc(row.kbId || filterKbId.value, row.id)
    ElMessage.success('重新解析已触发，请稍后刷新查看')
    loadData()
  } catch (e) {
    console.error('重新解析失败:', e)
    const msg = e?.response?.data?.message || e?.message || '未知错误'
    ElMessage.error('重新解析失败: ' + msg)
  }
}

const viewContent = async (row) => {
  try {
    const res = await getDocContent(row.kbId || filterKbId.value, row.id)
    renderedContent.value = res.data?.content || res.data || '无内容'
    contentVisible.value = true
  } catch (e) {
    console.error('获取内容失败:', e)
    const msg = e?.response?.data?.message || e?.message || '未知错误'
    ElMessage.error('获取文档内容失败: ' + msg)
  }
}

watch([search, filterKbId], () => { page.value = 1; loadData() })
onMounted(async () => {
  await loadKbList()
  loadData().then(() => { if (hasProcessingDocs()) startStatusPolling() })
})
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; }
</style>