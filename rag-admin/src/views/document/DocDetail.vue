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
            <el-tag :type="statusTag(docInfo.status)">{{ docInfo.status || '-' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="部门">{{ docInfo.department || '-' }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ docInfo.category || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ docInfo.createTime || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">文档内容</el-divider>
        <div
          v-if="content"
          v-html="content"
          class="doc-content"
        ></div>
        <el-empty v-else description="暂无内容" :image-size="60" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getDocContent } from '../../api/doc'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const route = useRoute()
const loading = ref(true)
const docInfo = ref({})
const content = ref('')

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
  if (status === 'FAILED' || status === 'failed') return 'danger'
  return 'info'
}

onMounted(async () => {
  try {
    const kbId = route.params.kbId
    const docId = route.params.docId
    const res = await getDocContent(kbId, docId)
    if (res.data) {
      docInfo.value = res.data
      content.value = res.data.content || ''
    }
  } catch (e) {
    console.error('获取文档详情失败:', e)
    ElMessage.error('获取文档详情失败')
  } finally {
    loading.value = false
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
  white-space: pre-wrap;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  background: #f5f7fa;
  padding: 16px;
  border-radius: 6px;
  line-height: 1.6;
}
</style>