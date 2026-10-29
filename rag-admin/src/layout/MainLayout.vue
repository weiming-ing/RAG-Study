<template>
  <el-container class="main-layout">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <h2>RAG 管理后台</h2>
      </div>
      <el-menu :default-active="activeMenu" router :collapse="false" background-color="#304156" text-color="#bfcbd9" active-text-color="#409EFF">
        <template v-if="menuTree.length > 0">
          <!-- 侧边栏由 sys_menu + 角色-菜单授权驱动：目录渲染为子菜单，叶子渲染为菜单项；
               visible=0 的是带路径参数的钻取页（文档详情/分块列表），不进侧边栏 -->
          <template v-for="item in menuTree" :key="item.id">
            <el-sub-menu v-if="item.children && item.children.length > 0" :index="String(item.id)">
              <template #title>
                <el-icon><component :is="resolveIcon(item.icon)" /></el-icon>
                <span>{{ item.menuName }}</span>
              </template>
              <el-menu-item v-for="child in item.children" :key="child.id" :index="child.path">
                {{ child.menuName }}
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="item.path">
              <el-icon><component :is="resolveIcon(item.icon)" /></el-icon>
              <span>{{ item.menuName }}</span>
            </el-menu-item>
          </template>
        </template>
        <template v-else>
          <!-- 菜单接口不可达时的兜底：至少保证登录用户能进入核心页面 -->
          <el-menu-item index="/dashboard">
            <el-icon><DataAnalysis /></el-icon>
            <span>监控大盘</span>
          </el-menu-item>
          <el-menu-item index="/kb">
            <el-icon><Collection /></el-icon>
            <span>知识库管理</span>
          </el-menu-item>
          <el-menu-item index="/conversations">
            <el-icon><ChatDotRound /></el-icon>
            <span>对话记录</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentTitle">{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-dropdown>
            <span class="user-info">
              <el-icon><UserFilled /></el-icon>
              {{ authStore.userInfo?.username || '管理员' }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getUserMenus } from '../api/menu'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const currentTitle = computed(() => route.meta?.title || '')
const activeMenu = computed(() => route.path)

const menuTree = ref([])
const loaded = ref(false)

const filterVisible = (nodes) => {
  return (nodes || [])
    .filter(n => n.visible !== 0)
    .map(n => ({ ...n, children: filterVisible(n.children) }))
}

const resolveIcon = (name) => name || 'Menu'

onMounted(async () => {
  try {
    const res = await getUserMenus()
    menuTree.value = filterVisible(Array.isArray(res.data) ? res.data : [])
  } catch (e) {
    console.warn('加载用户菜单失败，侧边栏使用兜底项', e)
    menuTree.value = []
  } finally {
    loaded.value = true
  }
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
}
.sidebar {
  background-color: #304156;
  overflow-y: auto;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #2b3a4a;
}
.logo h2 {
  color: #fff;
  font-size: 18px;
  margin: 0;
}
.header {
  background: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 60px;
}
.header-right {
  display: flex;
  align-items: center;
}
.user-info {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}
.main-content {
  background: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
</style>
