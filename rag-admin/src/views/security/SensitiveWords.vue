<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索敏感词" style="width: 200px" clearable />
        <el-select v-model="filterCategory" clearable placeholder="分类" style="width: 140px">
          <el-option label="通用" value="GENERAL" />
          <el-option label="政治" value="POLITICAL" />
          <el-option label="色情" value="PORNOGRAPHY" />
          <el-option label="暴力" value="VIOLENCE" />
          <el-option label="自定义" value="CUSTOM" />
        </el-select>
        <el-button type="primary" @click="showAddDialog">新增敏感词</el-button>
        <el-button type="warning" @click="showBatchDialog">批量导入</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="word" label="敏感词" />
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            <el-tag :type="row.category === 'POLITICAL' ? 'danger' : row.category === 'PORNOGRAPHY' ? 'warning' : row.category === 'VIOLENCE' ? 'danger' : 'info'">
              {{ row.category }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="处理级别" width="120">
          <template #default="{ row }">
            <el-tag :type="row.level === 'BLOCK' ? 'danger' : row.level === 'WARN' ? 'warning' : 'info'">
              {{ row.level === 'BLOCK' ? '拦截' : row.level === 'WARN' ? '警告' : '审核' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled === 1 ? 'success' : 'danger'">{{ row.enabled === 1 ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="180" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editWord(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteWord(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        style="margin-top: 16px; justify-content: flex-end"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadData"
      />
    </el-card>

    <el-dialog :title="editingWord?.id ? '编辑敏感词' : '新增敏感词'" v-model="dialogVisible" width="500px" @closed="resetForm">
      <el-form :model="form" ref="formRef" label-width="80px">
        <el-form-item label="敏感词" prop="word">
          <el-input v-model="form.word" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="form.category" style="width: 100%">
            <el-option label="通用" value="GENERAL" />
            <el-option label="政治" value="POLITICAL" />
            <el-option label="色情" value="PORNOGRAPHY" />
            <el-option label="暴力" value="VIOLENCE" />
            <el-option label="自定义" value="CUSTOM" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理级别" prop="level">
          <el-select v-model="form.level" style="width: 100%">
            <el-option label="拦截" value="BLOCK" />
            <el-option label="警告" value="WARN" />
            <el-option label="审核" value="REVIEW" />
          </el-select>
        </el-form-item>
        <el-form-item label="知识库">
          <el-select v-model="form.kbId" clearable placeholder="留空为全局" style="width: 100%">
            <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog title="批量导入敏感词" v-model="batchVisible" width="500px">
      <el-form :model="batchForm" ref="batchFormRef" label-width="80px">
        <el-form-item label="敏感词" prop="words">
          <el-input v-model="batchForm.words" type="textarea" :rows="8" placeholder="每行一个敏感词" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="batchForm.category" style="width: 100%">
            <el-option label="通用" value="GENERAL" />
            <el-option label="政治" value="POLITICAL" />
            <el-option label="色情" value="PORNOGRAPHY" />
            <el-option label="暴力" value="VIOLENCE" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理级别">
          <el-select v-model="batchForm.level" style="width: 100%">
            <el-option label="拦截" value="BLOCK" />
            <el-option label="警告" value="WARN" />
            <el-option label="审核" value="REVIEW" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchVisible = false">取消</el-button>
        <el-button type="primary" @click="submitBatch">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { getSensitiveWords, saveSensitiveWord, deleteSensitiveWord as deleteWordApi, batchImportWords } from '../../api/security'
import { getKbs } from '../../api/kb'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const search = ref('')
const filterCategory = ref('')
const page = ref(1)
const total = ref(0)
const kbList = ref([])
const dialogVisible = ref(false)
const editingWord = ref(null)
const formRef = ref(null)
const batchVisible = ref(false)
const batchFormRef = ref(null)

const form = reactive({ word: '', category: 'GENERAL', level: 'BLOCK', kbId: null, enabled: 1 })
const batchForm = reactive({ words: '', category: 'GENERAL', level: 'BLOCK' })

const resetForm = () => {
  form.word = ''; form.category = 'GENERAL'; form.level = 'BLOCK'; form.kbId = null; form.enabled = 1
}

const loadKbList = async () => {
  try {
    const res = await getKbs({ size: 1000 })
    kbList.value = Array.isArray(res.data) ? res.data : (res.data?.records || [])
  } catch (e) { console.error(e) }
}

const loadData = async () => {
  loading.value = true
  try {
    const params = { pageNum: page.value, pageSize: 10, keyword: search.value || undefined }
    if (filterCategory.value) params.category = filterCategory.value
    const res = await getSensitiveWords(params)
    if (res.data?.records) {
      tableData.value = res.data.records
      total.value = res.data.total || 0
    } else {
      tableData.value = Array.isArray(res.data) ? res.data : []
      total.value = tableData.value.length
    }
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

const showAddDialog = () => { editingWord.value = null; resetForm(); dialogVisible.value = true }
const editWord = (row) => {
  editingWord.value = row
  Object.assign(form, { word: row.word, category: row.category, level: row.level, kbId: row.kbId, enabled: row.enabled })
  dialogVisible.value = true
}

const submitForm = async () => {
  try {
    const data = { ...form, kbId: form.kbId || null }
    if (editingWord.value?.id) {
      data.id = editingWord.value.id
    }
    await saveSensitiveWord(data)
    ElMessage.success('操作成功')
    dialogVisible.value = false
    loadData()
  } catch (e) { ElMessage.error('操作失败') }
}

const deleteWord = async (id) => {
  await ElMessageBox.confirm('确定删除该敏感词?', '提示', { type: 'warning' })
  try {
    await deleteWordApi(id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

const showBatchDialog = () => { batchForm.words = ''; batchVisible.value = true }

const submitBatch = async () => {
  const words = batchForm.words.split('\n').map(w => w.trim()).filter(w => w)
  if (words.length === 0) { ElMessage.warning('请输入敏感词'); return }
  try {
    await batchImportWords({ words, category: batchForm.category, level: batchForm.level })
    ElMessage.success(`成功导入 ${words.length} 个敏感词`)
    batchVisible.value = false
    loadData()
  } catch (e) { ElMessage.error('导入失败') }
}

watch([search, filterCategory], () => { page.value = 1; loadData() })
onMounted(() => { loadKbList(); loadData() })
</script>

<style scoped>
.page { width: 100%; }
.toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
</style>