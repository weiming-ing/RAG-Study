<template>
  <div class="page">
    <el-card>
      <!-- 用户信息分隔区 -->
      <div class="user-section">
        <el-button text @click="goBack" class="back-btn">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
        <div class="user-banner">
          <el-avatar :size="56" :style="{ backgroundColor: avatarColor }">{{ username.charAt(0).toUpperCase() }}</el-avatar>
          <div class="user-banner-info">
            <div class="user-banner-name">{{ username }}</div>
            <div class="user-banner-meta">
              <span>用户 ID：{{ userId ?? '未知' }}</span>
              <el-divider direction="vertical" />
              <span>共 {{ totalCount }} 轮对话</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 对话记录列表 -->
      <div v-loading="loading" style="min-height: 200px;">
        <div v-if="!loading && list.length === 0" style="text-align: center; padding: 40px; color: #909399;">
          暂无详细对话记录
        </div>
        <div v-for="(item, index) in list" :key="item.id" class="detail-item">
          <div class="detail-header-row">
            <span class="detail-index">#{{ index + 1 }}</span>
            <span class="detail-time">{{ item.createTime || '' }}</span>
            <span v-if="item.kbName" class="detail-kb">{{ item.kbName }}</span>
            <span v-if="item.tokenCount" class="detail-token">{{ item.tokenCount }} tokens</span>
          </div>
          <div class="detail-qa">
            <div class="detail-q">
              <span class="label label-q">Q</span>
              <span>{{ item.question }}</span>
            </div>
            <div class="detail-a">
              <span class="label label-a">A</span>
              <span>{{ (item.answer || '').substring(0, 300) }}{{ (item.answer || '').length > 300 ? '...' : '' }}</span>
            </div>
          </div>
          <div class="detail-footer">
            <el-radio-group v-model="item.feedback" size="small" @change="updateFeedback(item)" style="margin-left: 32px;">
              <el-radio-button :value="1">好评</el-radio-button>
              <el-radio-button :value="0">无</el-radio-button>
              <el-radio-button :value="-1">差评</el-radio-button>
            </el-radio-group>
            <el-button size="small" text type="primary" @click="showChunkTrace(item)" style="margin-left: auto;">
              <el-icon><Document /></el-icon> 查看引用
            </el-button>
          </div>
        </div>
      </div>
      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        :total="total"
        :page-size="pageSize"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: center"
        @current-change="loadData"
      />
    </el-card>

    <!-- 引用追溯对话框：对话→切片→文档 -->
    <el-dialog v-model="chunkTraceVisible" title="引用追溯" width="700px" top="5vh">
      <div v-if="chunkTraceLoading" style="text-align: center; padding: 40px;">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <p style="margin-top: 12px; color: #909399;">加载中...</p>
      </div>
      <div v-else-if="chunkTraceList.length === 0" style="text-align: center; padding: 40px; color: #909399;">
        暂无引用数据
      </div>
      <el-timeline v-else>
        <el-timeline-item
          v-for="(item, idx) in chunkTraceList"
          :key="idx"
          :timestamp="item.docName || '未知文档'"
          placement="top"
          color="#409EFF"
        >
          <div class="trace-item">
            <div class="trace-meta">
              <el-tag size="small" type="info">chunk: {{ item.chunkId }}</el-tag>
              <el-tag v-if="item.kbName" size="small" type="success">{{ item.kbName }}</el-tag>
              <el-tag v-if="item.chunkIndex !== null && item.chunkIndex !== undefined" size="small">
                切片 #{{ item.chunkIndex }}
              </el-tag>
            </div>
            <div class="trace-content" v-if="item.chunkContent">
              {{ item.chunkContent }}
            </div>
            <div class="trace-content" v-else style="color: #e6a23c;">
              (切片内容已删除)
            </div>
            <div class="trace-doc-link" v-if="item.docId">
              <el-link type="primary" :href="`/documents?docId=${item.docId}`" target="_blank">
                查看文档详情 →
              </el-link>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getConversations, updateFeedback as updateFeedbackApi, getConversationChunkTrace } from '../../api/conversation'
import { ElMessage } from 'element-plus'
import { Document, Loading } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const userId = computed(() => {
  const id = Number(route.params.userId)
  return isNaN(id) ? null : id
})
const username = computed(() => route.query.username || '用户#' + (userId.value ?? ''))
const avatarColor = computed(() => {
  const colors = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#9B59B6', '#1ABC9C', '#E74C3C', '#3498DB']
  const idx = (userId.value ?? 0) % colors.length
  return colors[idx]
})

const loading = ref(false)
const list = ref([])
const page = ref(1)
const pageSize = 10
const total = ref(0)
const totalCount = ref(0)

const loadData = async () => {
  // 如果 userId 无效，不发起请求
  if (userId.value === null) {
    list.value = []
    total.value = 0
    totalCount.value = 0
    return
  }

  loading.value = true
  try {
    const params = { pageNum: page.value, pageSize: pageSize, userId: userId.value }
    const res = await getConversations(params)
    if (res.data?.records) {
      list.value = res.data.records
      total.value = res.data.total || 0
      totalCount.value = res.data.total || 0
    } else {
      list.value = []
      total.value = 0
      totalCount.value = 0
    }
  } catch (e) {
    console.error('加载对话详情失败:', e)
    ElMessage.error('加载对话记录失败')
    list.value = []
  } finally {
    loading.value = false
  }
}

// 监听路由参数变化，重新加载数据（处理用户切换、直接访问等情况）
watch(
  () => route.params.userId,
  (newUserId) => {
    page.value = 1
    loadData()
  },
  { immediate: true }
)

const updateFeedback = async (item) => {
  try {
    const fb = item.feedback === 0 ? null : item.feedback
    await updateFeedbackApi(item.id, { feedback: fb })
    ElMessage.success('反馈更新成功')
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

// 引用追溯：对话→切片→文档
const chunkTraceVisible = ref(false)
const chunkTraceLoading = ref(false)
const chunkTraceList = ref([])

const showChunkTrace = async (item) => {
  chunkTraceVisible.value = true
  chunkTraceLoading.value = true
  chunkTraceList.value = []
  try {
    const res = await getConversationChunkTrace(item.id)
    if (res.data) {
      chunkTraceList.value = res.data
    }
  } catch (e) {
    console.error('加载引用追溯失败:', e)
    ElMessage.error('加载引用追溯失败')
  } finally {
    chunkTraceLoading.value = false
  }
}

const goBack = () => {
  router.push('/conversations')
}

</script>

<style scoped>
.page { width: 100%; }

/* 用户分隔区 */
.user-section {
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 2px solid #e4e7ed;
}
.back-btn {
  font-size: 14px;
  color: #606266;
  padding: 8px 12px;
  border-radius: 6px;
  transition: all 0.2s;
  margin-bottom: 12px;
}
.back-btn:hover {
  background: #f0f2f5;
  color: #409EFF;
}
.user-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f0f5ff 0%, #e6f7ff 100%);
  border-radius: 12px;
  border: 1px solid #d6e4ff;
}
.user-banner-info {
  flex: 1;
}
.user-banner-name {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}
.user-banner-meta {
  font-size: 13px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 对话记录卡片 */
.detail-item {
  border: 1px solid #e6e6e6;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  background: #fafafa;
  transition: box-shadow 0.2s;
}
.detail-item:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.detail-header-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #909399;
}
.detail-index {
  font-weight: bold;
  color: #409EFF;
}
.detail-kb {
  background: #ecf5ff;
  color: #409EFF;
  padding: 2px 8px;
  border-radius: 4px;
}
.detail-token {
  color: #e6a23c;
}
.detail-qa {
  margin-left: 0;
}
.detail-q, .detail-a {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 14px;
  line-height: 1.6;
}
.label {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  color: #fff;
}
.label-q { background: #409EFF; }
.label-a { background: #67C23A; }
.detail-footer {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

/* 引用追溯对话框 */
.trace-item {
  padding: 4px 0;
}
.trace-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.trace-content {
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
  background: #f5f7fa;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 6px;
  max-height: 100px;
  overflow-y: auto;
}
.trace-doc-link {
  text-align: right;
}
</style>