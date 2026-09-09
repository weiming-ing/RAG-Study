<template>
  <div class="system-log">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>系统日志</span>
          <div class="header-actions">
            <el-button @click="handleCleanLogs" :disabled="!hasLogs">清理过期日志</el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="日志级别">
          <el-select v-model="searchForm.level" placeholder="全部" clearable>
            <el-option label="DEBUG" value="DEBUG" />
            <el-option label="INFO" value="INFO" />
            <el-option label="WARN" value="WARN" />
            <el-option label="ERROR" value="ERROR" />
          </el-select>
        </el-form-item>
        <el-form-item label="模块">
          <el-input v-model="searchForm.module" placeholder="如: Auth" clearable />
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="searchForm.keyword" placeholder="搜索日志内容" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="tableData" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="logLevel" label="级别" width="90">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.logLevel)" size="small">{{ row.logLevel }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="logModule" label="模块" width="120" />
        <el-table-column prop="logMessage" label="日志内容" min-width="250" show-overflow-tooltip />
        <el-table-column prop="traceId" label="Trace ID" width="160" />
        <el-table-column prop="username" label="用户" width="120" />
        <el-table-column prop="ipAddress" label="IP地址" width="140" />
        <el-table-column prop="durationMs" label="耗时(ms)" width="100" />
        <el-table-column prop="createTime" label="时间" width="170" />
        <el-table-column label="操作" width="60" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
        class="pagination"
      />
    </el-card>

    <el-dialog v-model="detailVisible" title="日志详情" width="600px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="ID">{{ detailRow.id }}</el-descriptions-item>
        <el-descriptions-item label="级别">
          <el-tag :type="levelTagType(detailRow.logLevel)" size="small">{{ detailRow.logLevel }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="模块">{{ detailRow.logModule }}</el-descriptions-item>
        <el-descriptions-item label="日志内容">{{ detailRow.logMessage }}</el-descriptions-item>
        <el-descriptions-item label="Trace ID">{{ detailRow.traceId }}</el-descriptions-item>
        <el-descriptions-item label="用户">{{ detailRow.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ detailRow.ipAddress || '-' }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ detailRow.durationMs ? detailRow.durationMs + 'ms' : '-' }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ detailRow.createTime }}</el-descriptions-item>
        <el-descriptions-item v-if="detailRow.logDetail" label="详情">
          <pre class="log-detail">{{ detailRow.logDetail }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getLogs, cleanExpiredLogs } from '../../api/system'

const loading = ref(false)
const tableData = ref([])
const page = ref(1)
const size = ref(20)
const total = ref(0)
const hasLogs = ref(false)

const searchForm = reactive({ level: '', module: '', keyword: '' })

const detailVisible = ref(false)
const detailRow = ref({})

function levelTagType(level) {
  const map = { DEBUG: 'info', INFO: '', WARN: 'warning', ERROR: 'danger' }
  return map[level] || 'info'
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getLogs({ level: searchForm.level || undefined, module: searchForm.module || undefined, keyword: searchForm.keyword || undefined, page: page.value, size: size.value })
    tableData.value = res.data.records
    total.value = res.data.total
    hasLogs.value = total.value > 0
  } catch (e) {
    ElMessage.error('获取日志列表失败')
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  searchForm.level = ''
  searchForm.module = ''
  searchForm.keyword = ''
  page.value = 1
  fetchData()
}

function showDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

async function handleCleanLogs() {
  const { value: days } = await ElMessageBox.prompt('请输入保留天数', '清理过期日志', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputValue: '90',
    inputPattern: /^\d+$/,
    inputErrorMessage: '请输入有效天数'
  })
  if (!days) return
  try {
    const res = await cleanExpiredLogs(parseInt(days))
    ElMessage.success(`清理完成，共删除 ${res.data.cleanedCount} 条日志`)
    fetchData()
  } catch (e) {
    ElMessage.error('清理失败')
  }
}

onMounted(fetchData)
</script>

<style scoped>
.system-log {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.search-form {
  margin-bottom: 16px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
.log-detail {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: monospace;
  font-size: 12px;
  margin: 0;
  max-height: 300px;
  overflow-y: auto;
}
</style>