<template>
  <div class="page">
    <el-card v-loading="loading">
      <template #header>
        <div style="display: flex; align-items: center; gap: 12px">
          <el-button @click="$router.back()" :icon="'ArrowLeft'">返回</el-button>
          <span style="font-size: 16px; font-weight: bold">知识库配置 - {{ kbName }}</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" v-if="!loading">
        <el-tab-pane label="基础配置" name="config">
          <el-form :model="form" ref="formRef" label-width="120px" style="max-width: 600px; margin-top: 16px">
            <el-form-item label="嵌入模型">
              <el-select v-model="form.embeddingModel" style="width: 300px">
                <el-option label="text-embedding-ada-002" value="text-embedding-ada-002" />
                <el-option label="bge-large-zh" value="bge-large-zh" />
                <el-option label="m3e-base" value="m3e-base" />
              </el-select>
            </el-form-item>
            <el-form-item label="分块大小">
              <el-input-number v-model="form.chunkSize" :min="100" :max="5000" :step="100" />
            </el-form-item>
            <el-form-item label="分块重叠">
              <el-input-number v-model="form.chunkOverlap" :min="0" :max="1000" :step="10" />
            </el-form-item>
            <el-form-item label="Top K">
              <el-input-number v-model="form.topK" :min="1" :max="20" />
            </el-form-item>
            <el-form-item label="相似度阈值">
              <el-slider v-model="form.similarityThreshold" :min="0" :max="1" :step="0.05" show-input style="width: 300px" />
            </el-form-item>
            <el-form-item label="检索策略">
              <el-select v-model="form.retrievalStrategy" style="width: 300px">
                <el-option label="语义检索" value="semantic" />
                <el-option label="关键词检索" value="keyword" />
                <el-option label="混合检索" value="hybrid" />
              </el-select>
            </el-form-item>
            <el-form-item label="系统提示词">
              <el-input v-model="form.systemPrompt" type="textarea" :rows="4" placeholder="可自定义知识库的系统提示词" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveConfig">保存配置</el-button>
              <el-button type="success" @click="rebuildVectors" :loading="rebuilding">重建向量索引</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="访问权限" name="access">
          <div style="margin-top: 16px">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
              <span style="font-size: 14px; color: #606266">已授权用户列表（{{ authorizedUsers.length }} 人）</span>
              <el-button type="primary" size="small" @click="showGrantDialog = true">+ 添加用户</el-button>
            </div>

            <el-table :data="authorizedUsers" border stripe style="width: 100%">
              <el-table-column prop="userId" label="用户ID" width="80" />
              <el-table-column prop="username" label="用户名" width="150" />
              <el-table-column prop="displayName" label="显示名称" width="150" />
              <el-table-column prop="accessLevel" label="权限级别" width="120">
                <template #default="{ row }">
                  <el-tag :type="row.accessLevel === 'ADMIN' ? 'danger' : row.accessLevel === 'EDIT' ? 'warning' : 'info'">
                    {{ row.accessLevel === 'ADMIN' ? '管理员' : row.accessLevel === 'EDIT' ? '编辑者' : '只读' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="createTime" label="授权时间" width="180" />
              <el-table-column label="操作" width="120" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="danger" link @click="handleRevoke(row)">撤销</el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-empty v-if="authorizedUsers.length === 0" description="暂无授权用户" style="margin-top: 40px" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog title="添加用户授权" v-model="showGrantDialog" width="500px" @closed="resetGrantForm">
      <el-form :model="grantForm" label-width="100px">
        <el-form-item label="选择用户">
          <el-select v-model="grantForm.userIds" multiple filterable style="width: 100%" placeholder="请选择要授权的用户">
            <el-option
              v-for="user in availableUsers"
              :key="user.id"
              :label="user.displayName || user.username"
              :value="user.id"
              :disabled="isAlreadyAuthorized(user.id)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="权限级别">
          <el-radio-group v-model="grantForm.accessLevel">
            <el-radio value="EDIT">编辑者</el-radio>
            <el-radio value="READ">只读</el-radio>
          </el-radio-group>
          <div style="font-size: 12px; color: #909399; margin-top: 4px">
            管理员权限默认为知识库创建者，不可在此处授予
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGrantDialog = false">取消</el-button>
        <el-button type="primary" @click="handleGrant" :loading="granting">确定授权</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getKbConfig, updateKbConfig, getAuthorizedUsers, grantAccess, revokeAccess, getAvailableUsers } from '../../api/kb'
import { rebuildKbVectors } from '../../api/chunk'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const kbId = route.params.id
const loading = ref(true)
const kbName = ref('')
const rebuilding = ref(false)
const formRef = ref(null)
const activeTab = ref('config')

const form = reactive({
  embeddingModel: 'text-embedding-ada-002',
  chunkSize: 500, chunkOverlap: 50, topK: 5,
  similarityThreshold: 0.7, retrievalStrategy: 'semantic', systemPrompt: ''
})

const authorizedUsers = ref([])
const showGrantDialog = ref(false)
const granting = ref(false)
const availableUsers = ref([])
const grantForm = reactive({
  userIds: [],
  accessLevel: 'READ'
})

const isAlreadyAuthorized = (userId) => {
  return authorizedUsers.value.some(u => u.userId === userId)
}

const resetGrantForm = () => {
  grantForm.userIds = []
  grantForm.accessLevel = 'READ'
}

const loadConfig = async () => {
  try {
    const res = await getKbConfig(kbId)
    const data = res.data || {}
    kbName.value = data.name || data.kbName || ''
    Object.assign(form, {
      embeddingModel: data.embeddingModel || 'text-embedding-ada-002',
      chunkSize: data.chunkSize || 500, chunkOverlap: data.chunkOverlap || 50,
      topK: data.topK || 5, similarityThreshold: data.similarityThreshold || 0.7,
      retrievalStrategy: data.retrievalStrategy || 'semantic', systemPrompt: data.systemPrompt || ''
    })
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

const loadAuthorizedUsers = async () => {
  try {
    const res = await getAuthorizedUsers(kbId)
    authorizedUsers.value = res.data || []
  } catch (e) {
    console.error(e)
    authorizedUsers.value = []
  }
}

const loadAvailableUsers = async () => {
  try {
    const res = await getAvailableUsers()
    availableUsers.value = res.data || []
  } catch (e) {
    console.error(e)
    availableUsers.value = []
  }
}

const saveConfig = async () => {
  try {
    await updateKbConfig(kbId, { ...form })
    ElMessage.success('配置保存成功')
  } catch (e) { ElMessage.error('保存失败') }
}

const rebuildVectors = async () => {
  rebuilding.value = true
  try {
    await rebuildKbVectors(kbId)
    ElMessage.success('向量索引重建已触发')
  } catch (e) { ElMessage.error('重建失败') }
  finally { rebuilding.value = false }
}

const handleGrant = async () => {
  if (grantForm.userIds.length === 0) {
    ElMessage.warning('请选择至少一个用户')
    return
  }
  granting.value = true
  try {
    await grantAccess(kbId, {
      userIds: grantForm.userIds,
      accessLevel: grantForm.accessLevel
    })
    ElMessage.success('授权成功')
    showGrantDialog.value = false
    await loadAuthorizedUsers()
  } catch (e) { ElMessage.error('授权失败') }
  finally { granting.value = false }
}

const handleRevoke = async (row) => {
  await ElMessageBox.confirm(
    `确定撤销用户「${row.displayName || row.username}」的访问权限？`,
    '提示',
    { type: 'warning' }
  )
  try {
    await revokeAccess(kbId, row.userId)
    ElMessage.success('撤销成功')
    await loadAuthorizedUsers()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('撤销失败')
  }
}

onMounted(async () => {
  await loadConfig()
  await loadAuthorizedUsers()
  await loadAvailableUsers()
})
</script>

<style scoped>
.page { width: 100%; }
</style>