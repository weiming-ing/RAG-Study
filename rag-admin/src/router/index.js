import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/login/Login.vue'),
    meta: { noAuth: true }
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('../views/error/Forbidden.vue'),
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
      // 知识管理：KB → 文档 → 分块 钻取式层级
      { path: 'kb', name: 'KbList', component: () => import('../views/kb/KbList.vue'), meta: { title: '知识库列表' } },
      { path: 'kb/:kbId/documents', name: 'DocList', component: () => import('../views/document/DocList.vue'), meta: { title: '文档列表' } },
      { path: 'kb/:kbId/documents/:docId', name: 'DocDetail', component: () => import('../views/document/DocDetail.vue'), meta: { title: '文档详情' } },
      { path: 'kb/:kbId/documents/:docId/chunks', name: 'ChunkList', component: () => import('../views/chunk/ChunkList.vue'), meta: { title: '分块列表' } },
      { path: 'kb/:kbId/config', name: 'KbConfig', component: () => import('../views/kb/KbConfig.vue'), meta: { title: '知识库配置' } },
      { path: 'debug', name: 'DebugConsole', component: () => import('../views/debug/DebugConsole.vue'), meta: { title: '检索调试' } },
      { path: 'conversations', name: 'ConversationList', component: () => import('../views/conversation/ConversationList.vue'), meta: { title: '对话记录' } },
      { path: 'conversations/:userId', name: 'ConversationDetail', component: () => import('../views/conversation/ConversationDetail.vue'), meta: { title: '对话详情' } },
      { path: 'audit', name: 'AuditLogList', component: () => import('../views/audit/AuditLogList.vue'), meta: { title: '审计日志' } },
      { path: 'security/sensitive-words', name: 'SensitiveWords', component: () => import('../views/security/SensitiveWords.vue'), meta: { title: '敏感词管理' } },
      { path: 'security/rate-limits', name: 'RateLimits', component: () => import('../views/security/RateLimits.vue'), meta: { title: '限流管控' } },
      { path: 'security/access-control', name: 'AccessControl', component: () => import('../views/security/AccessControl.vue'), meta: { title: '访问控制' } },
      { path: 'system-config', name: 'SystemConfig', component: () => import('../views/system/SystemConfig.vue'), meta: { title: '系统配置' } },
      { path: 'system-logs', name: 'SystemLog', component: () => import('../views/system/SystemLog.vue'), meta: { title: '系统日志' } },
      { path: 'api-keys', name: 'ApiKeyList', component: () => import('../views/apikey/ApiKeyList.vue'), meta: { title: 'API密钥' } },
      // 兼容旧入口：文档/分块不再有全局平铺页，重定向到钻取入口
      { path: 'documents', redirect: '/kb' },
      { path: 'chunks', redirect: '/kb' },
      { path: 'documents/:kbId/:docId', redirect: to => `/kb/${to.params.kbId}/documents/${to.params.docId}` }
    ]
  }
]

const router = createRouter({
  // 管理台部署在 /admin/ 子路径下（与员工聊天页共用同一个 Nginx 入口）。
  // import.meta.env.BASE_URL 取自 vite.config.js 的 base，改部署路径时只需改一处，
  // 否则会出现"资源在 /admin/ 下、路由却按根路径跳转"的错位。
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// 管理台准入角色：与 Python require_admin 的 ADMIN_ROLES 保持一致。
// 无管理角色的账号（普通员工）不允许进入控制台——此前任何登录用户
// 都能看到全部管理页面，角色形同虚设。
const CONSOLE_ROLES = ['ROLE_ADMIN', 'ROLE_KB_ADMIN']

router.beforeEach((to) => {
  const authStore = useAuthStore()
  if (to.meta.noAuth) {
    return true
  }
  if (!authStore.token) {
    return '/login'
  }
  const roles = authStore.userInfo?.roles
  // roles 字段存在才判权：字段缺失视为旧版本会话（store 启动时静默刷新，
  // 下次导航生效），避免刷新未落地时误伤；明确的无角色数组则直接 403
  if (Array.isArray(roles) && !roles.some(r => CONSOLE_ROLES.includes(r))) {
    return '/403'
  }
  return true
})

export default router
