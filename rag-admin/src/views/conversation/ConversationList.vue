<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索用户或问题" style="width: 240px" clearable @input="onSearchInput" />
        <el-button type="primary" @click="loadData">
          <el-icon><Search /></el-icon> 搜索
        </el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="username" label="用户" width="120">
          <template #default="{ row }">
            <el-tag type="primary">{{ row.username || '用户#' + row.user_id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_count" label="对话轮次" width="100">
          <template #default="{ row }">
            <el-tag type="warning">{{ row.total_count || 0 }} 轮</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="latestQuestion" label="最新问题" show-overflow-tooltip min-width="250">
          <template #default="{ row }">{{ row.latestQuestion || '（无）' }}</template>
        </el-table-column>
        <el-table-column prop="latestAnswer" label="最新回答摘要" show-overflow-tooltip min-width="250">
          <template #default="{ row }">{{ (row.latestAnswer || '').substring(0, 120) }}{{ (row.latestAnswer || '').length > 120 ? '...' : '' }}</template>
        </el-table-column>
        <el-table-column prop="latest_time" label="最新对话时间" width="180">
          <template #default="{ row }">{{ row.latest_time || '' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && tableData.length === 0" description="暂无对话记录" style="padding: 40px 0" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getGroupedConversations } from '../../api/conversation'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const tableData = ref([])
const search = ref('')

let searchTimer = null
const onSearchInput = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadData(), 300)
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getGroupedConversations()
    let list = Array.isArray(res.data) ? res.data : []
    if (search.value) {
      const kw = search.value.toLowerCase()
      list = list.filter(item =>
        (item.username || '').toLowerCase().includes(kw) ||
        (item.latestQuestion || '').toLowerCase().includes(kw) ||
        String(item.user_id || '').includes(kw)
      )
    }
    tableData.value = list
  } catch (e) {
    console.error('对话记录加载失败:', e)
    ElMessage.error('对话记录加载失败，请检查后端服务是否正常运行')
    tableData.value = []
  } finally {
    loading.value = false
  }
}

const viewDetail = (row) => {
  router.push({
    name: 'ConversationDetail',
    params: { userId: row.user_id },
    query: { username: row.username || '' }
  })
}

onMounted(loadData)
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
</style>