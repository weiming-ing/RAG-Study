<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索操作描述" style="width: 200px" clearable />
        <el-select v-model="filterType" clearable placeholder="操作类型" style="width: 140px">
          <el-option label="创建" value="CREATE" />
          <el-option label="更新" value="UPDATE" />
          <el-option label="删除" value="DELETE" />
          <el-option label="查询" value="QUERY" />
          <el-option label="登录" value="LOGIN" />
        </el-select>
        <el-select v-model="filterResult" clearable placeholder="操作结果" style="width: 120px">
          <el-option label="成功" value="SUCCESS" />
          <el-option label="失败" value="FAIL" />
        </el-select>
        <el-input v-model="dateInput" placeholder="日期筛选（暂不可用）" style="width: 160px" disabled />
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="uniqueTag" label="唯一标识" width="200">
          <template #default="{ row }">
            <el-tag type="primary" style="font-family: monospace; font-size: 11px;">{{ row.uniqueTag || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="操作人" width="120" />
        <el-table-column prop="operation" label="操作类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.operation === 'DELETE' ? 'danger' : row.operation === 'CREATE' ? 'success' : row.operation === 'UPDATE' ? 'warning' : 'info'">
              {{ row.operation }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="操作描述" show-overflow-tooltip min-width="200" />
        <el-table-column prop="targetName" label="目标资源" width="150" />
        <el-table-column prop="ipAddress" label="IP地址" width="150" />
        <el-table-column prop="result" label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.result === 'SUCCESS' ? 'success' : 'danger'">{{ row.result === 'SUCCESS' ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="操作时间" width="180" />
      </el-table>
      <el-pagination
        v-model:current-page="page"
        style="margin-top: 16px; justify-content: flex-end"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { getAuditLogs } from '../../api/audit'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const search = ref('')
const filterType = ref('')
const filterResult = ref('')
const dateInput = ref('')
const page = ref(1)
const total = ref(0)

const loadData = async () => {
  loading.value = true
  try {
    const params = { pageNum: page.value, pageSize: 10, keyword: search.value || undefined }
    if (filterType.value) params.operation = filterType.value
    if (filterResult.value) params.result = filterResult.value
    const res = await getAuditLogs(params)
    if (res.data?.records) {
      tableData.value = res.data.records
      total.value = res.data.total || 0
    } else {
      tableData.value = Array.isArray(res.data) ? res.data : []
      total.value = tableData.value.length
    }
  } catch (e) {
    console.error('审计日志加载失败:', e)
    ElMessage.error('审计日志加载失败，请检查后端服务是否正常运行')
  }
  finally { loading.value = false }
}

watch([search, filterType, filterResult], () => { page.value = 1; loadData() })
onMounted(loadData)
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
</style>