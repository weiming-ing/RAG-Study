<template>
  <div class="page">
    <el-card>
      <template #header><span>RAG 检索调试</span></template>
      <el-form :model="form" label-width="100px">
        <el-form-item label="知识库">
          <el-select v-model="form.kbId" placeholder="选择知识库" style="width: 300px">
            <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="检索策略">
          <el-select v-model="form.strategy" style="width: 200px">
            <el-option label="语义检索" value="semantic" />
            <el-option label="关键词检索" value="keyword" />
            <el-option label="混合检索" value="hybrid" />
          </el-select>
        </el-form-item>
        <el-form-item label="Top K">
          <el-input-number v-model="form.topK" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="查询内容">
          <el-input v-model="form.query" type="textarea" :rows="3" placeholder="输入查询内容" @keyup.ctrl.enter="search" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search" :loading="searching">检索</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top: 20px" v-if="results.length > 0">
      <template #header><span>检索结果 ({{ results.length }})</span></template>
      <div v-for="(item, idx) in results" :key="idx" class="result-item">
        <div class="result-header">
          <el-tag size="small" type="success">{{ item.docName || '文档' + (item.docId || '') }}</el-tag>
          <span class="score">相似度: {{ (item.score || 0).toFixed(4) }}</span>
        </div>
        <div class="result-content">{{ item.content }}</div>
      </div>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header><span>测试用例</span></template>
      <div class="toolbar">
        <el-button type="primary" @click="testCaseVisible = true">新增用例</el-button>
        <el-button type="success" @click="runAll" :loading="runningAll">运行全部</el-button>
      </div>
      <el-table :data="testCases" style="margin-top: 16px" size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="用例名称" />
        <el-table-column prop="query" label="查询内容" show-overflow-tooltip />
        <el-table-column prop="expectedCount" label="期望数量" width="100" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="applyTestCase(row)">加载</el-button>
            <el-button size="small" type="danger" @click="deleteTestCase(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog title="新增测试用例" v-model="testCaseVisible" width="500px">
      <el-form :model="tcForm" ref="tcFormRef" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="tcForm.name" />
        </el-form-item>
        <el-form-item label="知识库" prop="kbId">
          <el-select v-model="tcForm.kbId" style="width: 100%">
            <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="查询内容" prop="query">
          <el-input v-model="tcForm.query" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="期望数量" prop="expectedCount">
          <el-input-number v-model="tcForm.expectedCount" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testCaseVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTestCase">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { debugSearch, getTestCases, saveTestCase as saveTestCaseApi, deleteTestCase as deleteTestCaseApi, runAllTestCases } from '../../api/debug'
import { getKbs } from '../../api/kb'
import { ElMessage } from 'element-plus'

const kbList = ref([])
const searching = ref(false)
const results = ref([])
const testCases = ref([])
const testCaseVisible = ref(false)
const tcFormRef = ref(null)
const runningAll = ref(false)

const form = reactive({ kbId: null, strategy: 'semantic', topK: 5, query: '' })
const tcForm = reactive({ name: '', kbId: null, query: '', expectedCount: 5 })

const loadKbList = async () => {
  try {
    const res = await getKbs({ size: 1000 })
    kbList.value = Array.isArray(res.data) ? res.data : (res.data?.records || [])
  } catch (e) { console.error(e) }
}

const search = async () => {
  if (!form.query) { ElMessage.warning('请输入查询内容'); return }
  searching.value = true
  try {
    const res = await debugSearch({ ...form })
    results.value = res.data || []
  } catch (e) { ElMessage.error('检索失败') }
  finally { searching.value = false }
}

const applyTestCase = (row) => {
  form.kbId = row.kbId
  form.query = row.query
  form.topK = row.expectedCount || 5
}

const loadTestCases = async () => {
  try {
    const res = await getTestCases()
    testCases.value = Array.isArray(res.data) ? res.data : (res.data?.records || [])
  } catch (e) { console.error(e) }
}

const saveTestCase = async () => {
  try {
    await saveTestCaseApi({ ...tcForm })
    ElMessage.success('保存成功')
    testCaseVisible.value = false
    loadTestCases()
  } catch (e) { ElMessage.error('保存失败') }
}

const deleteTestCase = async (id) => {
  try {
    await deleteTestCaseApi(id)
    ElMessage.success('删除成功')
    loadTestCases()
  } catch (e) { ElMessage.error('删除失败') }
}

const runAll = async () => {
  runningAll.value = true
  try {
    await runAllTestCases({})
    ElMessage.success('测试用例执行完成')
    loadTestCases()
  } catch (e) { ElMessage.error('执行失败') }
  finally { runningAll.value = false }
}

onMounted(() => { loadKbList(); loadTestCases() })
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; }
.result-item { padding: 12px; border-bottom: 1px solid #ebeef5; }
.result-item:last-child { border-bottom: none; }
.result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.score { color: #909399; font-size: 13px; }
.result-content { background: #f5f7fa; padding: 12px; border-radius: 4px; font-size: 13px; line-height: 1.6; }
</style>