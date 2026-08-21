-- ============================================
-- P3: 系统配置管理模块初始化 SQL
-- ============================================

-- 系统配置表
CREATE TABLE IF NOT EXISTS sys_config (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    config_key VARCHAR(128) NOT NULL COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    config_type VARCHAR(32) DEFAULT 'STRING' COMMENT '配置类型: STRING/NUMBER/BOOLEAN/JSON',
    config_group VARCHAR(64) DEFAULT 'GENERAL' COMMENT '配置分组: GENERAL/LLM/RAG/SECURITY/EMAIL/STORAGE',
    description VARCHAR(255) COMMENT '配置描述',
    enabled TINYINT DEFAULT 1 COMMENT '是否启用: 1-启用 0-禁用',
    sort_order INT DEFAULT 0 COMMENT '排序',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_config_key (config_key),
    INDEX idx_config_group (config_group),
    INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置表';

-- 系统日志表
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

-- 初始化默认配置
INSERT INTO sys_config (config_key, config_value, config_type, config_group, description, sort_order) VALUES
('system.name', 'RAG知识库管理系统', 'STRING', 'GENERAL', '系统名称', 1),
('system.version', '1.0.0', 'STRING', 'GENERAL', '系统版本号', 2),
('system.logo', '', 'STRING', 'GENERAL', '系统Logo URL', 3),
('system.language', 'zh_CN', 'STRING', 'GENERAL', '系统默认语言', 4),
('system.timezone', 'Asia/Shanghai', 'STRING', 'GENERAL', '系统时区', 5),
('system.max_file_size', '50', 'NUMBER', 'GENERAL', '最大上传文件大小(MB)', 10),
('system.allowed_file_types', '["txt","md","pdf","docx","xlsx","csv","html"]', 'JSON', 'GENERAL', '允许上传的文件类型', 11),

('llm.default_model', 'gpt-3.5-turbo', 'STRING', 'LLM', '默认LLM模型', 20),
('llm.default_temperature', '0.7', 'NUMBER', 'LLM', '默认温度参数', 21),
('llm.max_tokens', '4096', 'NUMBER', 'LLM', '最大Token数', 22),
('llm.api_key', '', 'STRING', 'LLM', 'LLM API Key', 23),
('llm.base_url', 'https://api.openai.com/v1', 'STRING', 'LLM', 'LLM API基础URL', 24),

('rag.default_top_k', '5', 'NUMBER', 'RAG', '默认召回条数', 30),
('rag.default_similarity', '0.7', 'NUMBER', 'RAG', '默认相似度阈值', 31),
('rag.default_chunk_size', '500', 'NUMBER', 'RAG', '默认分块大小', 32),
('rag.default_chunk_overlap', '50', 'NUMBER', 'RAG', '默认分块重叠', 33),
('rag.default_embedding_model', 'text-embedding-ada-002', 'STRING', 'RAG', '默认嵌入模型', 34),
('rag.enable_rerank', 'true', 'BOOLEAN', 'RAG', '是否启用重排序', 35),
('rag.enable_multi_hop', 'false', 'BOOLEAN', 'RAG', '是否启用多跳检索', 36),

('security.login_max_attempts', '5', 'NUMBER', 'SECURITY', '最大登录尝试次数', 40),
('security.login_lock_minutes', '30', 'NUMBER', 'SECURITY', '登录锁定时间(分钟)', 41),
('security.session_timeout', '7200', 'NUMBER', 'SECURITY', '会话超时时间(秒)', 42),
('security.enable_captcha', 'false', 'BOOLEAN', 'SECURITY', '是否启用验证码', 43),
('security.enable_csrf', 'true', 'BOOLEAN', 'SECURITY', '是否启用CSRF防护', 44),

('email.smtp_host', '', 'STRING', 'EMAIL', 'SMTP服务器地址', 50),
('email.smtp_port', '587', 'NUMBER', 'EMAIL', 'SMTP端口', 51),
('email.smtp_username', '', 'STRING', 'EMAIL', 'SMTP用户名', 52),
('email.smtp_password', '', 'STRING', 'EMAIL', 'SMTP密码', 53),
('email.from_address', '', 'STRING', 'EMAIL', '发件人地址', 54),
('email.enable', 'false', 'BOOLEAN', 'EMAIL', '是否启用邮件服务', 55),

('storage.type', 'local', 'STRING', 'STORAGE', '存储类型: local/oss/s3', 60),
('storage.local_path', './uploads', 'STRING', 'STORAGE', '本地存储路径', 61),
('storage.oss_endpoint', '', 'STRING', 'STORAGE', 'OSS Endpoint', 62),
('storage.oss_bucket', '', 'STRING', 'STORAGE', 'OSS Bucket', 63),
('storage.oss_access_key', '', 'STRING', 'STORAGE', 'OSS Access Key', 64),
('storage.oss_secret_key', '', 'STRING', 'STORAGE', 'OSS Secret Key', 65);