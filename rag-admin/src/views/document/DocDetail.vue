<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="card-header">
          <el-button text @click="$router.back()">
            <el-icon><ArrowLeft /></el-icon>
            返回
          </el-button>
          <span class="title">{{ docInfo.fileName || '文档详情' }}</span>
        </div>
      </template>

      <div v-loading="loading">
        <el-descriptions :column="2" border v-if="!loading">
          <el-descriptions-item label="文档ID">{{ docInfo.id }}</el-descriptions-item>
          <el-descriptions-item label="文件类型">{{ docInfo.fileType || '-' }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ formatFileSize(docInfo.fileSize) }}</el-descriptions-item>
          <el-descriptions-item label="分块数">{{ docInfo.totalChunks || 0 }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTag(docInfo.status)">{{ statusLabel(docInfo.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="部门">{{ docInfo.department || '-' }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ docInfo.category || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ docInfo.createTime || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">文档内容</el-divider>
        <div
          v-if="content"
          v-html="renderedContent"
          class="doc-content"
        ></div>
        <el-empty v-else description="暂无内容" :image-size="60" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { getDocContent } from '../../api/doc'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'

const route = useRoute()
const loading = ref(true)
const docInfo = ref({})
const content = ref('')

const renderedContent = computed(() => {
  if (!content.value) return ''
  return marked(content.value)
})

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++ }
  return size.toFixed(1) + ' ' + units[i]
}

const statusTag = (status) => {
  if (status === 'READY' || status === 'indexed' || status === 'COMPLETED') return 'success'
  if (status === 'PARSING' || status === 'processing' || status === 'PROCESSING') return 'warning'
  if (status === 'NEEDS_OCR' || status === 'needs_ocr') return 'warning'
  if (status === 'FAILED' || status === 'failed') return 'danger'
  return 'info'
}

// 状态文案：NEEDS_OCR 必须给出可操作解释，而不是把原始枚举直接丢给用户
const statusLabel = (status) => {
  if (status === 'NEEDS_OCR' || status === 'needs_ocr') {
    return '需OCR（扫描件无文本层，当前版本无法检索其内容）'
  }
  if (status === 'READY' || status === 'indexed' || status === 'COMPLETED') return '已完成'
  if (status === 'PARSING' || status === 'processing' || status === 'PROCESSING') return '处理中'
  if (status === 'FAILED' || status === 'failed') return '失败'
  return status || '-'
}

onMounted(async () => {
  const kbId = route.params.kbId
  const docId = route.params.docId
  const load = async () => {
    try {
      const res = await getDocContent(kbId, docId)
      if (res.data) {
        docInfo.value = res.data
        content.value = res.data.content || ''
      }
      return res.data
    } catch (e) {
      console.error('获取文档详情失败:', e)
      ElMessage.error('获取文档详情失败')
      return null
    } finally {
      loading.value = false
    }
  }
  const info = await load()
  // 文档还在后台解析时轮询状态，到终态（含内容就绪）后停止
  const isProcessing = (s) => s === 'PARSING' || s === 'processing' || s === 'PROCESSING'
  if (info && isProcessing(info.status)) {
    const timer = setInterval(async () => {
      const updated = await load()
      if (!updated || !isProcessing(updated.status)) clearInterval(timer)
    }, 3000)
    onBeforeUnmount(() => clearInterval(timer))
  }
})
</script>

<style scoped>
.page { width: 100%; }
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
.doc-content {
  max-height: 600px;
  overflow-y: auto;
  padding: 24px;
  background: #fafbfc;
  border: 1px solid #e8eaed;
  border-radius: 6px;
  line-height: 1.8;
  font-size: 14px;
  color: #24292e;
}

.doc-content :deep(h1) {
  font-size: 1.8em;
  font-weight: 600;
  margin: 24px 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e8eaed;
}

.doc-content :deep(h2) {
  font-size: 1.4em;
  font-weight: 600;
  margin: 20px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e8eaed;
}

.doc-content :deep(h3) {
  font-size: 1.15em;
  font-weight: 600;
  margin: 16px 0 8px;
}

.doc-content :deep(p) {
  margin: 8px 0;
}

.doc-content :deep(ul),
.doc-content :deep(ol) {
  padding-left: 24px;
  margin: 8px 0;
}

.doc-content :deep(li) {
  margin: 4px 0;
}

.doc-content :deep(code) {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.9em;
}

.doc-content :deep(pre) {
  background: #f4f5f7;
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 12px 0;
}

.doc-content :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 13px;
}

.doc-content :deep(blockquote) {
  border-left: 4px solid #dfe2e5;
  margin: 12px 0;
  padding: 4px 16px;
  color: #6a737d;
}

.doc-content :deep(table) {
  border-collapse: collapse;
  margin: 12px 0;
  width: 100%;
}

.doc-content :deep(th),
.doc-content :deep(td) {
  border: 1px solid #dfe2e5;
  padding: 8px 12px;
  text-align: left;
}

.doc-content :deep(th) {
  background: #f4f5f7;
  font-weight: 600;
}

.doc-content :deep(tr:nth-child(even)) {
  background: #fafbfc;
}

.doc-content :deep(a) {
  color: #409eff;
  text-decoration: none;
}

.doc-content :deep(a:hover) {
  text-decoration: underline;
}

.doc-content :deep(hr) {
  border: none;
  border-top: 1px solid #e8eaed;
  margin: 20px 0;
}

.doc-content :deep(img) {
  max-width: 100%;
  border-radius: 4px;
}
</style>