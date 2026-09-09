<template>
  <el-container class="main-layout">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <h2>RAG 管理后台</h2>
      </div>
      <el-menu :default-active="activeMenu" router :collapse="false" background-color="#304156" text-color="#bfcbd9" active-text-color="#409EFF">
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>监控大盘</span>
        </el-menu-item>
        <el-sub-menu index="system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/users">用户管理</el-menu-item>
          <el-menu-item index="/roles">角色管理</el-menu-item>
          <el-menu-item index="/menus">菜单管理</el-menu-item>
          <el-menu-item index="/system-config">系统配置</el-menu-item>
          <el-menu-item index="/system-logs">系统日志</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/kb">
          <el-icon><Collection /></el-icon>
          <span>知识库管理</span>
        </el-menu-item>
        <el-menu-item index="/documents">
          <el-icon><Document /></el-icon>
          <span>文档管理</span>
        </el-menu-item>
        <el-menu-item index="/chunks">
          <el-icon><Grid /></el-icon>
          <span>分块管理</span>
        </el-menu-item>
        <el-menu-item index="/debug">
          <el-icon><Monitor /></el-icon>
          <span>调试控制台</span>
        </el-menu-item>
        <el-menu-item index="/conversations">
          <el-icon><ChatDotRound /></el-icon>
          <span>对话记录</span>
        </el-menu-item>
        <el-menu-item index="/audit">
          <el-icon><Tickets /></el-icon>
          <span>审计日志</span>
        </el-menu-item>
        <el-sub-menu index="security">
          <template #title>
            <el-icon><Lock /></el-icon>
            <span>安全风控</span>
          </template>
          <el-menu-item index="/security/sensitive-words">敏感词管理</el-menu-item>
          <el-menu-item index="/security/rate-limits">限流管控</el-menu-item>
          <el-menu-item index="/security/access-control">访问控制</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/api-keys">
          <el-icon><Key /></el-icon>
          <span>API密钥</span>
        </el-menu-item>
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
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const currentTitle = computed(() => route.meta?.title || '')
const activeMenu = computed(() => route.path)

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