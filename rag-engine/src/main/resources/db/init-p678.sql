-- ============================================
-- RAG Engine - P6/P7/P8 模块初始化 SQL
-- P6: 切片/向量管理
-- P7: 检索调试工作台
-- P8: 对话运营/审计日志
-- ============================================

-- P7: 检索测试案例库
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

-- P8: 对话日志表
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
    feedback_reason VARCHAR(100) COMMENT '反馈原因: MISSING_DATA/CHUNK_ERROR/RETRIEVAL_ERROR/PROMPT_ERROR/OTHER',
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

-- P8: 操作审计日志表
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT COMMENT '操作用户ID',
    username VARCHAR(64) COMMENT '操作用户名',
    operation VARCHAR(64) NOT NULL COMMENT '操作类型: UPLOAD/DELETE/UPDATE/CONFIG/GRANT/REVOKE/REPARSE/REBUILD/EXPORT/etc',
    target_type VARCHAR(32) COMMENT '目标类型: KB/DOCUMENT/CHUNK/USER/ROLE/CONFIG',
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