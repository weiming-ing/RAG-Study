import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/login/Login.vue'),
    meta: { noAuth: true }
  },
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/dashboard/Dashboard.vue'), meta: { title: '监控大盘' } },
      { path: 'users', name: 'UserList', component: () => import('../views/system/UserList.vue'), meta: { title: '用户管理' } },
      { path: 'roles', name: 'RoleList', component: () => import('../views/system/RoleList.vue'), meta: { title: '角色管理' } },
      { path: 'menus', name: 'MenuList', component: () => import('../views/system/MenuList.vue'), meta: { title: '菜单管理' } },
      { path: 'kb', name: 'KbList', component: () => import('../views/kb/KbList.vue'), meta: { title: '知识库管理' } },
      { path: 'kb/:id/config', name: 'KbConfig', component: () => import('../views/kb/KbConfig.vue'), meta: { title: '知识库配置' } },
      { path: 'documents', name: 'DocList', component: () => import('../views/document/DocList.vue'), meta: { title: '文档管理' } },
      { path: 'documents/:kbId/:docId', name: 'DocDetail', component: () => import('../views/document/DocDetail.vue'), meta: { title: '文档详情' } },
      { path: 'chunks', name: 'ChunkList', component: () => import('../views/chunk/ChunkList.vue'), meta: { title: '分块管理' } },
      { path: 'debug', name: 'DebugConsole', component: () => import('../views/debug/DebugConsole.vue'), meta: { title: '调试控制台' } },
      { path: 'conversations', name: 'ConversationList', component: () => import('../views/conversation/ConversationList.vue'), meta: { title: '对话记录' } },
      { path: 'conversations/:userId', name: 'ConversationDetail', component: () => import('../views/conversation/ConversationDetail.vue'), meta: { title: '对话详情' } },
      { path: 'audit', name: 'AuditLogList', component: () => import('../views/audit/AuditLogList.vue'), meta: { title: '审计日志' } },
      { path: 'security/sensitive-words', name: 'SensitiveWords', component: () => import('../views/security/SensitiveWords.vue'), meta: { title: '敏感词管理' } },
      { path: 'security/rate-limits', name: 'RateLimits', component: () => import('../views/security/RateLimits.vue'), meta: { title: '限流管控' } },
      { path: 'security/access-control', name: 'AccessControl', component: () => import('../views/security/AccessControl.vue'), meta: { title: '访问控制' } },
      { path: 'system-config', name: 'SystemConfig', component: () => import('../views/system/SystemConfig.vue'), meta: { title: '系统配置' } },
      { path: 'system-logs', name: 'SystemLog', component: () => import('../views/system/SystemLog.vue'), meta: { title: '系统日志' } },
      { path: 'api-keys', name: 'ApiKeyList', component: () => import('../views/apikey/ApiKeyList.vue'), meta: { title: 'API密钥' } }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.noAuth) {
    next()
  } else if (!token) {
    next('/login')
  } else {
    next()
  }
})

export default router