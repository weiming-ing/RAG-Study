-- ============================================
-- RAG Engine - RBAC 权限系统初始化 SQL
-- ============================================

-- 系统用户表
CREATE TABLE IF NOT EXISTS sys_user (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(32) NOT NULL UNIQUE COMMENT '用户名',
    password VARCHAR(255) NOT NULL COMMENT '密码(BCrypt)',
    display_name VARCHAR(64) COMMENT '显示名称',
    email VARCHAR(128) COMMENT '邮箱',
    phone VARCHAR(20) COMMENT '手机号',
    avatar VARCHAR(255) COMMENT '头像URL',
    status TINYINT DEFAULT 1 COMMENT '状态: 1-启用 0-禁用',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted TINYINT DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_username (username),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统用户表';

-- 系统角色表
CREATE TABLE IF NOT EXISTS sys_role (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(64) NOT NULL COMMENT '角色名称',
    role_code VARCHAR(64) NOT NULL UNIQUE COMMENT '角色编码',
    description VARCHAR(255) COMMENT '角色描述',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_role_code (role_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统角色表';

-- 用户角色关联表
CREATE TABLE IF NOT EXISTS sys_user_role (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    role_id BIGINT NOT NULL COMMENT '角色ID',
    UNIQUE KEY uk_user_role (user_id, role_id),
    INDEX idx_user_id (user_id),
    INDEX idx_role_id (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户角色关联表';

-- 系统菜单/权限表
CREATE TABLE IF NOT EXISTS sys_menu (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    parent_id BIGINT DEFAULT 0 COMMENT '父菜单ID',
    menu_name VARCHAR(64) NOT NULL COMMENT '菜单名称',
    menu_type VARCHAR(16) NOT NULL DEFAULT 'MENU' COMMENT '类型: MENU-菜单 BUTTON-按钮',
    path VARCHAR(255) COMMENT '路由路径',
    component VARCHAR(255) COMMENT '前端组件路径',
    icon VARCHAR(64) COMMENT '图标',
    sort_order INT DEFAULT 0 COMMENT '排序',
    permission_code VARCHAR(128) COMMENT '权限标识',
    visible TINYINT DEFAULT 1 COMMENT '是否可见: 1-可见 0-隐藏',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_parent_id (parent_id),
    INDEX idx_sort_order (sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统菜单权限表';

-- 角色菜单关联表
CREATE TABLE IF NOT EXISTS sys_role_menu (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    role_id BIGINT NOT NULL COMMENT '角色ID',
    menu_id BIGINT NOT NULL COMMENT '菜单ID',
    UNIQUE KEY uk_role_menu (role_id, menu_id),
    INDEX idx_role_id (role_id),
    INDEX idx_menu_id (menu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色菜单关联表';

-- ============================================
-- 初始化默认数据
-- ============================================

-- 默认角色
INSERT INTO sys_role (role_name, role_code, description) VALUES
('超级管理员', 'ROLE_ADMIN', '拥有所有权限'),
('知识库管理员', 'ROLE_KB_ADMIN', '可以管理知识库和文档'),
('普通查看者', 'ROLE_VIEWER', '只能查看知识库内容'),
('只读访客', 'ROLE_GUEST', '只读访问');

-- 默认菜单(一级菜单)
INSERT INTO sys_menu (id, parent_id, menu_name, menu_type, path, component, icon, sort_order, permission_code, visible) VALUES
(1, 0, '监控大盘', 'MENU', '/dashboard', 'dashboard/Dashboard', 'Odometer', 1, 'dashboard:view', 1),
(2, 0, '系统管理', 'MENU', '/system', NULL, 'Setting', 2, NULL, 1),
(3, 0, '知识库管理', 'MENU', '/kb', NULL, 'Collection', 3, NULL, 1),
(4, 0, '检索调试', 'MENU', '/search-debug', 'search/SearchDebug', 'Search', 4, 'search-debug:view', 1),
(5, 0, '运营管理', 'MENU', '/operations', NULL, 'DataAnalysis', 5, NULL, 1);

-- 二级菜单 - 系统管理
INSERT INTO sys_menu (id, parent_id, menu_name, menu_type, path, component, icon, sort_order, permission_code, visible) VALUES
(21, 2, '用户管理', 'MENU', '/system/users', 'system/UserManage', 'User', 1, 'system:user:view', 1),
(22, 2, '角色管理', 'MENU', '/system/roles', 'system/RoleManage', 'Avatar', 2, 'system:role:view', 1),
(23, 2, '菜单管理', 'MENU', '/system/menus', 'system/MenuManage', 'Menu', 3, 'system:menu:view', 1);

-- 二级菜单 - 知识库管理
INSERT INTO sys_menu (id, parent_id, menu_name, menu_type, path, component, icon, sort_order, permission_code, visible) VALUES
(31, 3, '知识库列表', 'MENU', '/kb/list', 'kb/KnowledgeBaseList', 'Notebook', 1, 'kb:view', 1),
(32, 3, '文档管理', 'MENU', '/kb/:kbId/documents', 'kb/DocumentList', 'Document', 2, 'kb:document:view', 1),
(33, 3, '切片管理', 'MENU', '/kb/:kbId/chunks/:docId', 'kb/ChunkList', 'Files', 3, 'kb:chunk:view', 1),
(34, 3, '知识库配置', 'MENU', '/kb/:kbId/config', 'kb/KbConfig', 'Tools', 4, 'kb:config:view', 1),
(35, 3, '权限授权', 'MENU', '/kb/:kbId/access', 'kb/KbAccess', 'Lock', 5, 'kb:access:view', 1),
(36, 3, '敏感词管理', 'MENU', '/kb/:kbId/sensitive-words', 'kb/SensitiveWords', 'Warn', 6, 'kb:sensitive:view', 1);

-- 二级菜单 - 运营管理
INSERT INTO sys_menu (id, parent_id, menu_name, menu_type, path, component, icon, sort_order, permission_code, visible) VALUES
(51, 5, '对话日志', 'MENU', '/operations/conversations', 'operations/ConversationLog', 'ChatLineRound', 1, 'operations:conversation:view', 1),
(52, 5, '审计日志', 'MENU', '/operations/audit-logs', 'operations/AuditLog', 'DocumentChecked', 2, 'operations:audit:view', 1),
(53, 5, 'API密钥', 'MENU', '/operations/api-keys', 'operations/ApiKeyManage', 'Key', 3, 'operations:apikey:view', 1),
(54, 5, '任务监控', 'MENU', '/operations/tasks', 'operations/TaskMonitor', 'Monitor', 4, 'operations:task:view', 1);

-- 为超级管理员分配所有菜单
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 1, id FROM sys_menu;

-- 为知识库管理员分配知识库相关菜单
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 2, id FROM sys_menu WHERE id IN (1, 3, 31, 32, 33, 34, 35, 36, 4, 5, 51, 54);

-- 为普通查看者分配查看菜单
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 3, id FROM sys_menu WHERE id IN (1, 3, 31, 32, 33, 4);

-- 为只读访客分配基本查看菜单
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 4, id FROM sys_menu WHERE id IN (1, 3, 31, 32);

-- 创建默认管理员用户 (密码: admin123, BCrypt加密)
-- 注意: 需要先启动应用注册用户，或手动执行此SQL
-- INSERT INTO sys_user (username, password, display_name, status) VALUES
-- ('admin', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iAt6Z5Eh', '系统管理员', 1);
-- INSERT INTO sys_user_role (user_id, role_id) VALUES (1, 1);