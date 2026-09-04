-- ============================================
-- RAG Engine - 完整数据库初始化脚本
-- 由 docker-compose 自动执行
-- ============================================

CREATE DATABASE IF NOT EXISTS rag_engine DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE rag_engine;

-- ============================================
-- 1. 文档与切片
-- ============================================

CREATE TABLE IF NOT EXISTS knowledge_document (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    file_name VARCHAR(500) NOT NULL COMMENT '原始文件名',
    file_type VARCHAR(50) NOT NULL COMMENT '文件类型(txt/md/pdf/docx)',
    file_size BIGINT NOT NULL DEFAULT 0 COMMENT '文件大小(字节)',
    kb_id BIGINT DEFAULT NULL COMMENT '所属知识库ID',
    department VARCHAR(100) DEFAULT NULL COMMENT '所属部门',
    category VARCHAR(100) DEFAULT NULL COMMENT '文档分类',
    tags VARCHAR(255) DEFAULT NULL COMMENT '标签',
    total_chunks INT NOT NULL DEFAULT 0 COMMENT '子块总数',
    total_parent_chunks INT NOT NULL DEFAULT 0 COMMENT '父块总数',
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '状态: PENDING/PARSING/CHUNKING/VECTORIZING/READY/FAILED',
    summary TEXT DEFAULT NULL COMMENT '文档摘要',
    expire_time DATETIME DEFAULT NULL COMMENT '过期时间',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_kb_id (kb_id),
    INDEX idx_department (department),
    INDEX idx_category (category),
    INDEX idx_status (status),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档表';

CREATE TABLE IF NOT EXISTS knowledge_chunk (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    document_id BIGINT NOT NULL COMMENT '所属文档ID',
    chunk_id VARCHAR(100) NOT NULL COMMENT '子块唯一标识',
    chunk_index INT NOT NULL DEFAULT 0 COMMENT '子块序号',
    content TEXT NOT NULL COMMENT '子块内容',
    content_length INT NOT NULL DEFAULT 0 COMMENT '内容长度',
    parent_chunk_id VARCHAR(100) NOT NULL COMMENT '父块唯一标识',
    parent_chunk_index INT NOT NULL DEFAULT 0 COMMENT '父块序号',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_chunk_id (chunk_id),
    INDEX idx_document_id (document_id),
    INDEX idx_parent_chunk_id (parent_chunk_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库分块表';

-- ============================================
-- 2. 知识库管理
-- ============================================

CREATE TABLE IF NOT EXISTS kb_knowledge_base (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '知识库ID(自增)',
    name VARCHAR(128) NOT NULL COMMENT '知识库名称',
    description TEXT COMMENT '知识库描述',
    category VARCHAR(64) COMMENT '分类',
    tags TEXT COMMENT '标签(JSON数组)',
    cover_url VARCHAR(255) COMMENT '封面URL',
    owner_id BIGINT COMMENT '创建者用户ID',
    department VARCHAR(64) COMMENT '所属部门',
    is_public TINYINT DEFAULT 1 COMMENT '是否公开: 1-公开 0-私有',
    status VARCHAR(16) DEFAULT 'ENABLED' COMMENT '状态: ENABLED/DISABLED/ARCHIVED',
    chunk_size INT DEFAULT 300 COMMENT '切片大小',
    chunk_overlap INT DEFAULT 50 COMMENT '切片重叠',
    embedding_model VARCHAR(64) DEFAULT 'default' COMMENT 'Embedding模型',
    top_k INT DEFAULT 10 COMMENT '默认召回条数',
    similarity_threshold DOUBLE DEFAULT 0.6 COMMENT '相似度阈值',
    vector_weight DOUBLE DEFAULT 0.7 COMMENT '向量检索权重',
    bm25_weight DOUBLE DEFAULT 0.3 COMMENT 'BM25检索权重',
    enable_rerank TINYINT DEFAULT 1 COMMENT '是否开启重排',
    filter_low_score TINYINT DEFAULT 0 COMMENT '是否过滤低分片段',
    prompt_template TEXT COMMENT '知识库专属Prompt模板',
    blacklist_words TEXT COMMENT '黑名单词库(JSON)',
    whitelist_words TEXT COMMENT '白名单词库(JSON)',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted TINYINT DEFAULT 0 COMMENT '逻辑删除',
    INDEX idx_owner_id (owner_id),
    INDEX idx_category (category),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库表';

CREATE TABLE IF NOT EXISTS kb_user_access (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    kb_id BIGINT NOT NULL COMMENT '知识库ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    access_level VARCHAR(16) NOT NULL DEFAULT 'READ' COMMENT '权限级别: READ/EDIT/ADMIN',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uk_kb_user (kb_id, user_id),
    INDEX idx_kb_id (kb_id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库用户权限表';

-- ============================================
-- 3. 解析任务
-- ============================================

CREATE TABLE IF NOT EXISTS parse_task (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id VARCHAR(64) NOT NULL COMMENT '文档ID',
    task_type VARCHAR(32) DEFAULT 'PARSE' COMMENT '任务类型: PARSE/CHUNK/VECTORIZE/REBUILD',
    status VARCHAR(16) DEFAULT 'PENDING' COMMENT '状态: PENDING/RUNNING/SUCCESS/FAILED',
    progress INT DEFAULT 0 COMMENT '进度 0-100',
    error_msg TEXT COMMENT '错误信息',
    retry_count INT DEFAULT 0 COMMENT '重试次数',
    max_retry INT DEFAULT 3 COMMENT '最大重试次数',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    start_time DATETIME COMMENT '开始时间',
    end_time DATETIME COMMENT '结束时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_document_id (document_id),
    INDEX idx_status (status),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='解析任务表';

-- ============================================
-- 4. RBAC 权限系统
-- ============================================

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

CREATE TABLE IF NOT EXISTS sys_role (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(64) NOT NULL COMMENT '角色名称',
    role_code VARCHAR(64) NOT NULL UNIQUE COMMENT '角色编码',
    description VARCHAR(255) COMMENT '角色描述',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_role_code (role_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统角色表';

CREATE TABLE IF NOT EXISTS sys_user_role (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    role_id BIGINT NOT NULL COMMENT '角色ID',
    UNIQUE KEY uk_user_role (user_id, role_id),
    INDEX idx_user_id (user_id),
    INDEX idx_role_id (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户角色关联表';

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

CREATE TABLE IF NOT EXISTS sys_role_menu (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    role_id BIGINT NOT NULL COMMENT '角色ID',
    menu_id BIGINT NOT NULL COMMENT '菜单ID',
    UNIQUE KEY uk_role_menu (role_id, menu_id),
    INDEX idx_role_id (role_id),
    INDEX idx_menu_id (menu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色菜单关联表';

-- ============================================
-- 5. 对话日志与审计
-- ============================================

CREATE TABLE IF NOT EXISTS conversation_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL COMMENT '会话ID',
    user_id BIGINT COMMENT '用户ID',
    question TEXT NOT NULL COMMENT '用户提问',
    answer TEXT COMMENT 'AI回答',
    referenced_chunks TEXT COMMENT '引用的切片信息(JSON)',
    kb_id VARCHAR(64) COMMENT '知识库ID',
    status VARCHAR(16) DEFAULT 'SUCCESS' COMMENT '状态: SUCCESS/FAILED/TIMEOUT',
    feedback TINYINT DEFAULT 0 COMMENT '反馈: 0-无, 1-点赞, -1-点踩',
    feedback_comment VARCHAR(500) COMMENT '反馈备注',
    feedback_reason VARCHAR(100) COMMENT '反馈原因',
    latency_ms INT DEFAULT 0 COMMENT '耗时(毫秒)',
    token_count INT DEFAULT 0 COMMENT 'Token消耗',
    ip_address VARCHAR(64) COMMENT 'IP地址',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_kb_id (kb_id),
    INDEX idx_feedback (feedback),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话日志表';

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT COMMENT '操作用户ID',
    username VARCHAR(64) COMMENT '操作用户名',
    operation VARCHAR(64) NOT NULL COMMENT '操作类型',
    target_type VARCHAR(32) COMMENT '目标类型',
    target_id VARCHAR(64) COMMENT '目标ID',
    target_name VARCHAR(255) COMMENT '目标名称',
    detail TEXT COMMENT '操作详情(JSON)',
    result VARCHAR(16) DEFAULT 'SUCCESS' COMMENT '操作结果: SUCCESS/FAILED',
    error_msg TEXT COMMENT '错误信息',
    ip_address VARCHAR(64) COMMENT 'IP地址',
    user_agent VARCHAR(500) COMMENT 'User-Agent',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_operation (operation),
    INDEX idx_target_type (target_type),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='操作审计日志表';

-- ============================================
-- 6. 系统配置与日志
-- ============================================

CREATE TABLE IF NOT EXISTS sys_config (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    config_key VARCHAR(128) NOT NULL COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    config_type VARCHAR(32) DEFAULT 'STRING' COMMENT '配置类型: STRING/NUMBER/BOOLEAN/JSON',
    config_group VARCHAR(64) DEFAULT 'GENERAL' COMMENT '配置分组',
    description VARCHAR(255) COMMENT '配置描述',
    enabled TINYINT DEFAULT 1 COMMENT '是否启用: 1-启用 0-禁用',
    sort_order INT DEFAULT 0 COMMENT '排序',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_config_key (config_key),
    INDEX idx_config_group (config_group),
    INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置表';

CREATE TABLE IF NOT EXISTS sys_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    log_level VARCHAR(16) NOT NULL DEFAULT 'INFO' COMMENT '日志级别: DEBUG/INFO/WARN/ERROR',
    log_module VARCHAR(64) COMMENT '日志模块',
    log_message TEXT COMMENT '日志内容',
    log_detail TEXT COMMENT '日志详情(JSON)',
    trace_id VARCHAR(64) COMMENT '追踪ID',
    user_id BIGINT COMMENT '用户ID',
    username VARCHAR(64) COMMENT '用户名',
    ip_address VARCHAR(64) COMMENT 'IP地址',
    duration_ms BIGINT DEFAULT 0 COMMENT '执行耗时(毫秒)',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_log_level (log_level),
    INDEX idx_log_module (log_module),
    INDEX idx_trace_id (trace_id),
    INDEX idx_user_id (user_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统日志表';

-- ============================================
-- 7. 监控统计
-- ============================================

CREATE TABLE IF NOT EXISTS api_call_stat (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    kb_id VARCHAR(64) COMMENT '知识库ID',
    api_path VARCHAR(200) COMMENT 'API路径',
    call_count BIGINT DEFAULT 0 COMMENT '调用次数',
    success_count BIGINT DEFAULT 0 COMMENT '成功次数',
    fail_count BIGINT DEFAULT 0 COMMENT '失败次数',
    avg_latency_ms DOUBLE DEFAULT 0 COMMENT '平均耗时(毫秒)',
    stat_date DATE NOT NULL COMMENT '统计日期',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_kb_path_date (kb_id, api_path, stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API调用统计';

CREATE TABLE IF NOT EXISTS token_usage_stat (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    kb_id VARCHAR(64) COMMENT '知识库ID',
    user_id BIGINT COMMENT '用户ID',
    prompt_tokens BIGINT DEFAULT 0 COMMENT '提示词Token数',
    completion_tokens BIGINT DEFAULT 0 COMMENT '生成Token数',
    total_tokens BIGINT DEFAULT 0 COMMENT '总Token数',
    stat_date DATE NOT NULL COMMENT '统计日期',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_kb_user_date (kb_id, user_id, stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Token消耗统计';

CREATE TABLE IF NOT EXISTS doc_hot_stat (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id VARCHAR(64) NOT NULL COMMENT '文档ID',
    doc_name VARCHAR(255) COMMENT '文档名称',
    kb_id VARCHAR(64) COMMENT '知识库ID',
    search_count BIGINT DEFAULT 0 COMMENT '检索次数',
    hit_count BIGINT DEFAULT 0 COMMENT '命中次数',
    question_count BIGINT DEFAULT 0 COMMENT '提问次数',
    unique_visitors BIGINT DEFAULT 0 COMMENT '独立访客数',
    stat_date DATE NOT NULL COMMENT '统计日期',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_doc_date (document_id, stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档热度统计';

CREATE TABLE IF NOT EXISTS chunk_hot_stat (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    chunk_id VARCHAR(128) NOT NULL COMMENT '切片ID',
    document_id VARCHAR(64) COMMENT '文档ID',
    kb_id VARCHAR(64) COMMENT '知识库ID',
    hit_count BIGINT DEFAULT 0 COMMENT '命中次数',
    last_hit_time DATETIME COMMENT '最后命中时间',
    stat_date DATE NOT NULL COMMENT '统计日期',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_chunk_date (chunk_id, stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='切片热度统计';

CREATE TABLE IF NOT EXISTS task_monitor (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_type VARCHAR(32) NOT NULL COMMENT '任务类型: PARSE/CHUNK/VECTORIZE/REBUILD',
    status VARCHAR(16) DEFAULT 'PENDING' COMMENT '状态: PENDING/RUNNING/SUCCESS/FAILED',
    kb_id VARCHAR(64) COMMENT '知识库ID',
    document_id VARCHAR(64) COMMENT '文档ID',
    total_items INT DEFAULT 0 COMMENT '总任务数',
    completed_items INT DEFAULT 0 COMMENT '已完成数',
    failed_items INT DEFAULT 0 COMMENT '失败数',
    progress INT DEFAULT 0 COMMENT '进度 0-100',
    error_msg TEXT COMMENT '错误信息',
    start_time DATETIME COMMENT '开始时间',
    end_time DATETIME COMMENT '结束时间',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务监控';

CREATE TABLE IF NOT EXISTS system_alert (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    alert_type VARCHAR(32) NOT NULL COMMENT '告警类型',
    alert_level VARCHAR(16) DEFAULT 'WARN' COMMENT '告警级别: INFO/WARN/ERROR/CRITICAL',
    title VARCHAR(200) NOT NULL COMMENT '告警标题',
    detail TEXT COMMENT '告警详情',
    source VARCHAR(200) COMMENT '告警来源',
    status VARCHAR(16) DEFAULT 'ACTIVE' COMMENT '状态: ACTIVE/RESOLVED/ACKNOWLEDGED',
    resolved_time DATETIME COMMENT '解决时间',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统告警';

CREATE TABLE IF NOT EXISTS dashboard_stat (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stat_date DATE NOT NULL COMMENT '统计日期',
    total_kb_count INT DEFAULT 0 COMMENT '知识库总数',
    total_doc_count INT DEFAULT 0 COMMENT '文档总数',
    total_chunk_count INT DEFAULT 0 COMMENT '切片总数',
    total_question_count INT DEFAULT 0 COMMENT '提问总数',
    total_api_calls INT DEFAULT 0 COMMENT 'API调用总数',
    total_token_usage BIGINT DEFAULT 0 COMMENT 'Token消耗总量',
    active_user_count INT DEFAULT 0 COMMENT '活跃用户数',
    new_user_count INT DEFAULT 0 COMMENT '新增用户数',
    avg_latency_ms DOUBLE DEFAULT 0 COMMENT '平均响应时间',
    success_rate DOUBLE DEFAULT 0 COMMENT '成功率(%)',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日大盘统计';

-- ============================================
-- 8. 安全风控
-- ============================================

CREATE TABLE IF NOT EXISTS sensitive_word (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    word VARCHAR(100) NOT NULL COMMENT '敏感词',
    category VARCHAR(32) DEFAULT 'GENERAL' COMMENT '分类: GENERAL/POLITICAL/PORNOGRAPHY/VIOLENCE/CUSTOM',
    level VARCHAR(16) DEFAULT 'BLOCK' COMMENT '处理级别: BLOCK/WARN/REVIEW',
    kb_id VARCHAR(64) COMMENT '关联知识库ID(NULL表示全局)',
    enabled TINYINT DEFAULT 1 COMMENT '是否启用',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_word_kb (word, kb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='敏感词库';

CREATE TABLE IF NOT EXISTS rate_limit_rule (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL COMMENT '规则名称',
    target_type VARCHAR(32) NOT NULL COMMENT '限流目标: USER/IP/API_KEY/GLOBAL',
    target_value VARCHAR(200) COMMENT '目标值(用户ID/IP地址/API-Key)',
    limit_type VARCHAR(32) DEFAULT 'QPS' COMMENT '限流类型: QPS/TPM/TPD',
    limit_count INT DEFAULT 100 COMMENT '限制数量',
    window_seconds INT DEFAULT 60 COMMENT '时间窗口(秒)',
    enabled TINYINT DEFAULT 1 COMMENT '是否启用',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='限流规则';

CREATE TABLE IF NOT EXISTS rate_limit_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT COMMENT '用户ID',
    ip_address VARCHAR(64) COMMENT 'IP地址',
    api_key VARCHAR(128) COMMENT 'API-Key',
    api_path VARCHAR(200) COMMENT 'API路径',
    request_count INT DEFAULT 0 COMMENT '请求次数',
    blocked_count INT DEFAULT 0 COMMENT '被拦截次数',
    window_start DATETIME COMMENT '窗口开始时间',
    window_end DATETIME COMMENT '窗口结束时间',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='限流记录';

CREATE TABLE IF NOT EXISTS access_control (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    rule_type VARCHAR(16) NOT NULL COMMENT '规则类型: WHITELIST/BLACKLIST',
    ip_address VARCHAR(64) COMMENT 'IP地址',
    ip_range VARCHAR(64) COMMENT 'IP范围(CIDR)',
    user_id BIGINT COMMENT '用户ID',
    api_key VARCHAR(128) COMMENT 'API-Key',
    reason VARCHAR(255) COMMENT '原因说明',
    enabled TINYINT DEFAULT 1 COMMENT '是否启用',
    expire_time DATETIME COMMENT '过期时间',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='访问控制';

-- ============================================
-- 9. API密钥管理
-- ============================================

CREATE TABLE IF NOT EXISTS api_key (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    key_name VARCHAR(100) NOT NULL COMMENT '密钥名称',
    api_key VARCHAR(128) NOT NULL UNIQUE COMMENT 'API密钥',
    secret_key VARCHAR(128) COMMENT '密钥Secret',
    user_id BIGINT COMMENT '所属用户ID',
    kb_ids TEXT COMMENT '可访问的知识库ID列表(JSON数组)',
    permissions TEXT COMMENT '权限列表(JSON数组)',
    enabled TINYINT DEFAULT 1 COMMENT '是否启用',
    rate_limit INT DEFAULT 1000 COMMENT '调用频率限制(次/分钟)',
    daily_limit INT DEFAULT 10000 COMMENT '每日调用限制',
    total_calls BIGINT DEFAULT 0 COMMENT '总调用次数',
    last_used_time DATETIME COMMENT '最后使用时间',
    expire_time DATETIME COMMENT '过期时间',
    description VARCHAR(255) COMMENT '描述',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API密钥';

CREATE TABLE IF NOT EXISTS api_key_usage_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    api_key_id BIGINT COMMENT '密钥ID',
    api_key VARCHAR(128) COMMENT 'API密钥',
    api_path VARCHAR(200) COMMENT '调用路径',
    kb_id VARCHAR(64) COMMENT '知识库ID',
    ip_address VARCHAR(64) COMMENT '调用IP',
    result VARCHAR(16) DEFAULT 'SUCCESS' COMMENT '调用结果: SUCCESS/FAILED/BLOCKED',
    error_msg TEXT COMMENT '错误信息',
    latency_ms INT DEFAULT 0 COMMENT '耗时(毫秒)',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API密钥调用日志';

-- ============================================
-- 10. 调试测试用例
-- ============================================

CREATE TABLE IF NOT EXISTS debug_test_case (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL COMMENT '案例名称',
    query_text TEXT NOT NULL COMMENT '检索问题',
    top_k INT DEFAULT 5 COMMENT '召回数量',
    similarity_threshold FLOAT DEFAULT 0.5 COMMENT '相似度阈值',
    enable_hybrid TINYINT DEFAULT 1 COMMENT '是否混合检索',
    vector_weight FLOAT DEFAULT 0.7 COMMENT '向量检索权重',
    keyword_weight FLOAT DEFAULT 0.3 COMMENT '关键词检索权重',
    kb_id VARCHAR(64) COMMENT '关联知识库ID',
    expected_doc_ids TEXT COMMENT '期望召回的文档ID列表(JSON数组)',
    tags VARCHAR(255) COMMENT '标签',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_kb_id (kb_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='检索调试测试案例';

-- ============================================
-- 默认数据初始化
-- ============================================

-- 默认角色
INSERT IGNORE INTO sys_role (id, role_name, role_code, description) VALUES
(1, '超级管理员', 'ROLE_ADMIN', '拥有所有权限'),
(2, '知识库管理员', 'ROLE_KB_ADMIN', '可以管理知识库和文档'),
(3, '普通查看者', 'ROLE_VIEWER', '只能查看知识库内容'),
(4, '只读访客', 'ROLE_GUEST', '只读访问');

-- 默认菜单(一级菜单)
INSERT IGNORE INTO sys_menu (id, parent_id, menu_name, menu_type, path, component, icon, sort_order, permission_code, visible) VALUES
(1, 0, '监控大盘', 'MENU', '/dashboard', 'dashboard/Dashboard', 'Odometer', 1, 'dashboard:view', 1),
(2, 0, '系统管理', 'MENU', '/system', NULL, 'Setting', 2, NULL, 1),
(3, 0, '知识库管理', 'MENU', '/kb', NULL, 'Collection', 3, NULL, 1),
(4, 0, '检索调试', 'MENU', '/search-debug', 'search/SearchDebug', 'Search', 4, 'search-debug:view', 1),
(5, 0, '运营管理', 'MENU', '/operations', NULL, 'DataAnalysis', 5, NULL, 1);

-- 二级菜单 - 系统管理
INSERT IGNORE INTO sys_menu (id, parent_id, menu_name, menu_type, path, component, icon, sort_order, permission_code, visible) VALUES
(21, 2, '用户管理', 'MENU', '/system/users', 'system/UserManage', 'User', 1, 'system:user:view', 1),
(22, 2, '角色管理', 'MENU', '/system/roles', 'system/RoleManage', 'Avatar', 2, 'system:role:view', 1),
(23, 2, '菜单管理', 'MENU', '/system/menus', 'system/MenuManage', 'Menu', 3, 'system:menu:view', 1);

-- 二级菜单 - 知识库管理
INSERT IGNORE INTO sys_menu (id, parent_id, menu_name, menu_type, path, component, icon, sort_order, permission_code, visible) VALUES
(31, 3, '知识库列表', 'MENU', '/kb/list', 'kb/KnowledgeBaseList', 'Notebook', 1, 'kb:view', 1),
(32, 3, '文档管理', 'MENU', '/kb/:kbId/documents', 'kb/DocumentList', 'Document', 2, 'kb:document:view', 1),
(33, 3, '切片管理', 'MENU', '/kb/:kbId/chunks/:docId', 'kb/ChunkList', 'Files', 3, 'kb:chunk:view', 1),
(34, 3, '知识库配置', 'MENU', '/kb/:kbId/config', 'kb/KbConfig', 'Tools', 4, 'kb:config:view', 1),
(35, 3, '权限授权', 'MENU', '/kb/:kbId/access', 'kb/KbAccess', 'Lock', 5, 'kb:access:view', 1),
(36, 3, '敏感词管理', 'MENU', '/kb/:kbId/sensitive-words', 'kb/SensitiveWords', 'Warn', 6, 'kb:sensitive:view', 1);

-- 二级菜单 - 运营管理
INSERT IGNORE INTO sys_menu (id, parent_id, menu_name, menu_type, path, component, icon, sort_order, permission_code, visible) VALUES
(51, 5, '对话日志', 'MENU', '/operations/conversations', 'operations/ConversationLog', 'ChatLineRound', 1, 'operations:conversation:view', 1),
(52, 5, '审计日志', 'MENU', '/operations/audit-logs', 'operations/AuditLog', 'DocumentChecked', 2, 'operations:audit:view', 1),
(53, 5, 'API密钥', 'MENU', '/operations/api-keys', 'operations/ApiKeyManage', 'Key', 3, 'operations:apikey:view', 1),
(54, 5, '任务监控', 'MENU', '/operations/tasks', 'operations/TaskMonitor', 'Monitor', 4, 'operations:task:view', 1);

-- 为超级管理员分配所有菜单
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT 1, id FROM sys_menu;

-- 为知识库管理员分配知识库相关菜单
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT 2, id FROM sys_menu WHERE id IN (1, 3, 31, 32, 33, 34, 35, 36, 4, 5, 51, 54);

-- 为普通查看者分配查看菜单
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT 3, id FROM sys_menu WHERE id IN (1, 3, 31, 32, 33, 4);

-- 为只读访客分配基本查看菜单
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT 4, id FROM sys_menu WHERE id IN (1, 3, 31, 32);

-- 默认系统配置
INSERT IGNORE INTO sys_config (config_key, config_value, config_type, config_group, description, sort_order) VALUES
('system.name', 'RAG知识库管理系统', 'STRING', 'GENERAL', '系统名称', 1),
('system.version', '1.0.0', 'STRING', 'GENERAL', '系统版本号', 2),
('system.language', 'zh_CN', 'STRING', 'GENERAL', '系统默认语言', 4),
('system.timezone', 'Asia/Shanghai', 'STRING', 'GENERAL', '系统时区', 5),
('system.max_file_size', '50', 'NUMBER', 'GENERAL', '最大上传文件大小(MB)', 10),
('llm.default_model', 'deepseek-chat', 'STRING', 'LLM', '默认LLM模型', 20),
('llm.default_temperature', '0.7', 'NUMBER', 'LLM', '默认温度参数', 21),
('llm.max_tokens', '4096', 'NUMBER', 'LLM', '最大Token数', 22),
('rag.default_top_k', '5', 'NUMBER', 'RAG', '默认召回条数', 30),
('rag.default_similarity', '0.7', 'NUMBER', 'RAG', '默认相似度阈值', 31),
('rag.default_chunk_size', '500', 'NUMBER', 'RAG', '默认分块大小', 32),
('rag.default_chunk_overlap', '50', 'NUMBER', 'RAG', '默认分块重叠', 33),
('rag.enable_rerank', 'true', 'BOOLEAN', 'RAG', '是否启用重排序', 35),
('security.login_max_attempts', '5', 'NUMBER', 'SECURITY', '最大登录尝试次数', 40),
('security.login_lock_minutes', '30', 'NUMBER', 'SECURITY', '登录锁定时间(分钟)', 41),
('security.session_timeout', '7200', 'NUMBER', 'SECURITY', '会话超时时间(秒)', 42);