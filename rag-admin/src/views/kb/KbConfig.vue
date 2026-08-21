<template>
  <div class="page">
    <el-card v-loading="loading">
      <template #header>
        <div style="display: flex; align-items: center; gap: 12px">
          <el-button @click="$router.back()" :icon="'ArrowLeft'">返回</el-button>
          <span style="font-size: 16px; font-weight: bold">知识库配置 - {{ kbName }}</span>
        </div>
      </template>
      <el-form :model="form" ref="formRef" label-width="120px" v-if="!loading">
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
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getKbConfig, updateKbConfig } from '../../api/kb'
import { rebuildKbVectors } from '../../api/chunk'
import { ElMessage } from 'element-plus'

const route = useRoute()
const kbId = route.params.id
const loading = ref(true)
const kbName = ref('')
const rebuilding = ref(false)
const formRef = ref(null)

const form = reactive({
  embeddingModel: 'text-embedding-ada-002',
  chunkSize: 500, chunkOverlap: 50, topK: 5,
  similarityThreshold: 0.7, retrievalStrategy: 'semantic', systemPrompt: ''
})

const loadConfig = async () => {
  try {
    const res = await getKbConfig(kbId)
    const data = res.data || {}
    kbName.value = data.name || ''
    Object.assign(form, {
      embeddingModel: data.embeddingModel || 'text-embedding-ada-002',
      chunkSize: data.chunkSize || 500, chunkOverlap: data.chunkOverlap || 50,
      topK: data.topK || 5, similarityThreshold: data.similarityThreshold || 0.7,
      retrievalStrategy: data.retrievalStrategy || 'semantic', systemPrompt: data.systemPrompt || ''
    })
  } catch (e) { console.error(e) }
  finally { loading.value = false }
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

onMounted(loadConfig)
</script>

<style scoped>
.page { width: 100%; }
</style>