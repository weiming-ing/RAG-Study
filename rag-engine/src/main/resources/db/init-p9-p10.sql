-- ============================================
-- RAG Engine - P9/P10 模块初始化 SQL
-- P9: 监控统计
-- P10: 安全风控
-- ============================================

-- ==========================================
-- P9: 监控统计
-- ==========================================

-- API调用统计表
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
) COMMENT 'API调用统计';

-- Token消耗统计表
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
) COMMENT 'Token消耗统计';

-- 文档热度统计表
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
) COMMENT '文档热度统计';

-- 切片热度统计表
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
) COMMENT '切片热度统计';

-- 任务监控表
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
) COMMENT '任务监控';

-- 系统告警表
CREATE TABLE IF NOT EXISTS system_alert (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    alert_type VARCHAR(32) NOT NULL COMMENT '告警类型: QUEUE_BACKLOG/PARSE_FAILURE/DB_CONNECTION/VECTOR_STORE/TOKEN_LIMIT',
    alert_level VARCHAR(16) DEFAULT 'WARN' COMMENT '告警级别: INFO/WARN/ERROR/CRITICAL',
    title VARCHAR(200) NOT NULL COMMENT '告警标题',
    detail TEXT COMMENT '告警详情',
    source VARCHAR(200) COMMENT '告警来源',
    status VARCHAR(16) DEFAULT 'ACTIVE' COMMENT '状态: ACTIVE/RESOLVED/ACKNOWLEDGED',
    resolved_time DATETIME COMMENT '解决时间',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT '系统告警';

-- 每日大盘统计表
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
) COMMENT '每日大盘统计';

-- ==========================================
-- P10: 安全风控
-- ==========================================

-- 敏感词库表
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
) COMMENT '敏感词库';

-- 限流规则表
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
) COMMENT '限流规则';

-- 限流记录表
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
) COMMENT '限流记录';

-- 访问控制表(IP白名单/黑名单)
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
) COMMENT '访问控制';

-- ==========================================
-- P12: 接口密钥管理
-- ==========================================

-- API密钥表
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
) COMMENT 'API密钥';

-- API密钥调用日志
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
) COMMENT 'API密钥调用日志';