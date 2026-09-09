<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <h1 class="dashboard-title">监控大盘</h1>
      <div class="dashboard-actions">
        <el-radio-group v-model="days" size="small" @change="loadData">
          <el-radio-button :value="7">近7天</el-radio-button>
          <el-radio-button :value="14">近14天</el-radio-button>
          <el-radio-button :value="30">近30天</el-radio-button>
        </el-radio-group>
        <el-button size="small" @click="loadData" :icon="'Refresh'" circle />
      </div>
    </div>

    <!-- 指标卡片 -->
    <div class="stat-cards">
      <div class="stat-card" v-for="item in statCards" :key="item.key">
        <div class="stat-card-icon" :style="{ background: item.bg }">
          <span class="stat-icon">{{ item.icon }}</span>
        </div>
        <div class="stat-card-body">
          <div class="stat-value">{{ formatNumber(item.value) }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </div>
      </div>
    </div>

    <!-- 对话趋势 + 反馈分布 -->
    <div class="chart-row">
      <div class="chart-card chart-card-wide">
        <div class="chart-header">
          <h3>对话趋势</h3>
          <span class="chart-subtitle">近{{ days }}天每日对话量</span>
        </div>
        <v-chart class="chart" :option="conversationTrendOption" autoresize />
      </div>
      <div class="chart-card">
        <div class="chart-header">
          <h3>用户反馈</h3>
          <span class="chart-subtitle">近{{ days }}天反馈分布</span>
        </div>
        <v-chart class="chart chart-donut" :option="feedbackOption" autoresize />
      </div>
    </div>

    <!-- 文档引用排行 + 活跃用户 -->
    <div class="chart-row">
      <div class="chart-card">
        <div class="chart-header">
          <h3>文档引用排行</h3>
          <span class="chart-subtitle">近{{ days }}天被引用次数</span>
        </div>
        <el-table :data="docRefRank" size="small" style="width: 100%" stripe v-if="docRefRank.length > 0">
          <el-table-column type="index" label="#" width="40" />
          <el-table-column prop="doc_name" label="文档名称" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.doc_id" class="doc-link" @click="goDocDetail(row)">{{ row.doc_name || '未知文档' }}</span>
              <span v-else>{{ row.doc_name || '未知文档' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="cnt" label="引用次数" width="100" align="center">
            <template #default="{ row }">
              <el-tag type="primary" effect="plain" size="small">{{ row.cnt }}次</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无文档引用数据" :image-size="70" />
      </div>
      <div class="chart-card">
        <div class="chart-header">
          <h3>活跃用户 Top 10</h3>
          <span class="chart-subtitle">近{{ days }}天对话次数排名</span>
        </div>
        <el-table :data="activeUsers" size="small" style="width: 100%" stripe v-if="activeUsers.length > 0">
          <el-table-column type="index" label="#" width="40" />
          <el-table-column prop="username" label="用户" min-width="100" show-overflow-tooltip />
          <el-table-column prop="cnt" label="对话次数" width="90" align="center" />
          <el-table-column label="最后活跃" width="110" align="center">
            <template #default="{ row }">
              <span class="time-text">{{ formatTime(row.last_time) }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无活跃用户数据" :image-size="70" />
      </div>
    </div>

    <!-- 最近对话 -->
    <div class="chart-row">
      <div class="chart-card chart-card-full">
        <div class="chart-header">
          <h3>最近对话</h3>
          <span class="chart-subtitle">最新 10 条对话记录</span>
        </div>
        <el-table :data="recentConversations" size="small" style="width: 100%" stripe v-if="recentConversations.length > 0">
          <el-table-column type="index" label="#" width="40" />
          <el-table-column prop="username" label="用户" width="100" show-overflow-tooltip />
          <el-table-column prop="question" label="提问" min-width="200" show-overflow-tooltip />
          <el-table-column label="反馈" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="feedbackTag(row.feedback)" size="small" effect="plain">
                {{ feedbackLabel(row.feedback) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="160" align="center">
            <template #default="{ row }">
              <span class="time-text">{{ formatTime(row.create_time) }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无对话记录" :image-size="70" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'

import { getDashboard } from '../../api/dashboard'
import {
  getFeedbackDistribution, getTopKbStats, getDailyTrend,
  getActiveUserRank, getRecentConversations, getTodayStats,
  getDocRefRank
} from '../../api/conversation'

use([
  CanvasRenderer, LineChart, PieChart, BarChart,
  GridComponent, TooltipComponent, LegendComponent, TitleComponent
])

const router = useRouter()

const goDocDetail = (item) => {
  if (item.doc_id && item.kb_id) {
    router.push(`/documents/${item.kb_id}/${item.doc_id}`)
  }
}

// ==================== 状态 ====================
const days = ref(7)
const overview = ref({})
const todayStats = ref({})
const feedbackDist = ref({})
const docRefRank = ref([])
const dailyTrend = ref({})
const activeUsers = ref([])
const recentConversations = ref([])

// ==================== 指标卡 ====================
const statCards = computed(() => [
  { key: 'totalKbCount', label: '知识库', value: overview.value.totalKbCount, icon: '📚', bg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' },
  { key: 'totalDocCount', label: '文档数', value: overview.value.totalDocCount, icon: '📄', bg: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' },
  { key: 'totalChunkCount', label: '分块数', value: overview.value.totalChunkCount, icon: '🧩', bg: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' },
  { key: 'totalQuestionCount', label: '总对话', value: overview.value.totalQuestionCount, icon: '💬', bg: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)' },
  { key: 'totalUserCount', label: '用户数', value: overview.value.totalUserCount, icon: '👥', bg: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)' },
  { key: 'today', label: '今日对话', value: todayStats.value.today, icon: '📅', bg: 'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)' },
])

// ==================== 工具函数 ====================
const formatNumber = (num) => {
  if (num == null) return 0
  if (num >= 10000) return (num / 10000).toFixed(1) + 'w'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
  return num
}

const formatTime = (str) => {
  if (!str) return '-'
  const d = new Date(str)
  if (isNaN(d.getTime())) return str
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  if (diff < 172800000) return '昨天'
  return str.slice(0, 16).replace('T', ' ')
}

const feedbackTag = (v) => {
  if (v === 1) return 'success'
  if (v === -1) return 'danger'
  return 'info'
}

const feedbackLabel = (v) => {
  if (v === 1) return '好评'
  if (v === -1) return '差评'
  return '未评'
}

// ==================== 图表选项 ====================

const conversationTrendOption = computed(() => {
  const trend = dailyTrend.value?.conversationTrend || []
  const dates = trend.map(t => t.stat_date ? t.stat_date.slice(5) : '')
  const values = trend.map(t => t.total || 0)

  return {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(255,255,255,0.95)', borderWidth: 0 },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category', data: dates,
      axisLine: { lineStyle: { color: '#e0e0e0' } },
      axisLabel: { color: '#909399' }
    },
    yAxis: {
      type: 'value', minInterval: 1,
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
      axisLabel: { color: '#909399' }
    },
    series: [{
      data: values, type: 'line', smooth: true, symbol: 'circle', symbolSize: 6,
      lineStyle: { width: 3, color: '#409EFF' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(64,158,255,0.25)' },
            { offset: 1, color: 'rgba(64,158,255,0.02)' }
          ]
        }
      },
      itemStyle: { color: '#409EFF' }
    }]
  }
})

const feedbackOption = computed(() => {
  const d = feedbackDist.value
  const positive = d?.positive_count || 0
  const negative = d?.negative_count || 0
  const neutral = d?.neutral_count || 0
  const total = positive + negative + neutral
  const rate = total > 0 ? ((positive / total) * 100).toFixed(1) : '0.0'

  if (total === 0) {
    return {
      title: {
        text: '暂无反馈数据',
        left: 'center', top: 'center',
        textStyle: { color: '#C0C4CC', fontSize: 14, fontWeight: 'normal' }
      }
    }
  }

  return {
    tooltip: {
      trigger: 'item',
      formatter: ({ name, value, percent }) => `${name}: ${value} 次 (${percent}%)`
    },
    series: [{
      type: 'pie', radius: ['55%', '75%'], avoidLabelOverlap: true,
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' }
      },
      data: [
        { value: positive, name: '好评', itemStyle: { color: '#67C23A' } },
        { value: negative, name: '差评', itemStyle: { color: '#F56C6C' } },
        { value: neutral, name: '未反馈', itemStyle: { color: '#C0C4CC' } }
      ].filter(d => d.value > 0)
    }],
    graphic: [
      { type: 'text', left: 'center', top: 'center', style: { text: `${rate}%`, textAlign: 'center', fill: '#303133', fontSize: 24, fontWeight: 'bold' } },
      { type: 'text', left: 'center', top: '55%', style: { text: '好评率', textAlign: 'center', fill: '#909399', fontSize: 12 } }
    ]
  }
})

// ==================== 数据加载 ====================
const loadData = async () => {
  try {
    const [
      overviewRes, todayRes, feedbackRes, docRefRes,
      trendRes, userRankRes, recentRes
    ] = await Promise.all([
      getDashboard(),
      getTodayStats(),
      getFeedbackDistribution(days.value),
      getDocRefRank(days.value, 10),
      getDailyTrend(days.value),
      getActiveUserRank(days.value, 10),
      getRecentConversations(10)
    ])

    overview.value = overviewRes.data || {}
    todayStats.value = todayRes.data || {}
    feedbackDist.value = feedbackRes.data || {}
    docRefRank.value = docRefRes.data || []
    dailyTrend.value = trendRes.data || {}
    activeUsers.value = userRankRes.data || []
    recentConversations.value = recentRes.data || []
  } catch (e) {
    console.error('加载大盘数据失败', e)
    ElMessage.error('加载大盘数据失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.dashboard {
  padding: 0 4px 24px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.dashboard-title {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.dashboard-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 指标卡 */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 12px;
  padding: 20px 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  transition: transform 0.2s, box-shadow 0.2s;
  cursor: default;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-card-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 14px;
  flex-shrink: 0;
}

.stat-icon {
  font-size: 22px;
  line-height: 1;
}

.stat-card-body {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  line-height: 1.3;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 2px;
}

/* 图表行 */
.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.chart-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.chart-card-wide {
  grid-column: span 1;
}

.chart-card-full {
  grid-column: 1 / -1;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.chart-subtitle {
  font-size: 12px;
  color: #C0C4CC;
}

.chart {
  width: 100%;
  height: 300px;
}

.chart-donut {
  height: 280px;
}

.time-text {
  font-size: 12px;
  color: #909399;
}

.rank-list {
  max-height: 380px;
  overflow-y: auto;
}

.rank-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 8px;
  transition: background 0.15s;
}

.rank-item:hover {
  background: #f5f7fa;
}

.rank-clickable {
  cursor: pointer;
}

.rank-clickable:hover {
  background: #ecf5ff;
}

.rank-clickable:hover .rank-name {
  color: #409EFF;
}

.rank-item + .rank-item {
  border-top: 1px solid #f0f0f0;
}

.rank-badge {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: #C0C4CC;
  flex-shrink: 0;
  margin-right: 10px;
}

.rank-badge.rank-1 { background: linear-gradient(135deg, #F56C6C, #E6A23C); }
.rank-badge.rank-2 { background: linear-gradient(135deg, #E6A23C, #F2C94C); }
.rank-badge.rank-3 { background: linear-gradient(135deg, #F2C94C, #67C23A); }

.rank-name {
  flex: 1;
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.rank-count {
  font-size: 13px;
  font-weight: 600;
  color: #409EFF;
  flex-shrink: 0;
  margin-left: 12px;
  background: #ecf5ff;
  padding: 2px 10px;
  border-radius: 10px;
}

@media (max-width: 1200px) {
  .stat-cards {
    grid-template-columns: repeat(3, 1fr);
  }
}

.doc-link {
  color: #409EFF;
  cursor: pointer;
  text-decoration: none;
}

.doc-link:hover {
  color: #337ECC;
  text-decoration: underline;
}

@media (max-width: 900px) {
  .chart-row {
    grid-template-columns: 1fr;
  }
  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>