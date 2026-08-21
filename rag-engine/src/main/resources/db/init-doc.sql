-- ============================================
-- RAG Engine - 文档/任务管理模块初始化 SQL
-- ============================================

-- 解析任务表
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

-- 为 knowledge_document 表添加缺失字段 (如果已有表)
ALTER TABLE knowledge_document ADD COLUMN IF NOT EXISTS kb_id BIGINT COMMENT '所属知识库ID';
ALTER TABLE knowledge_document ADD COLUMN IF NOT EXISTS tags VARCHAR(255) COMMENT '标签';
ALTER TABLE knowledge_document ADD COLUMN IF NOT EXISTS expire_time DATETIME COMMENT '过期时间';
ALTER TABLE knowledge_document MODIFY COLUMN status VARCHAR(32) COMMENT '状态: PENDING/PARSING/CHUNKING/VECTORIZING/READY/FAILED';

-- 如果 knowledge_document 表的 id 列是 VARCHAR(64) 类型（旧版本），需要执行以下语句修复:
-- 注意：执行前请确保备份数据！UUID 类型的 id 值无法迁移，需要清空旧数据。
-- ALTER TABLE knowledge_document MODIFY COLUMN id BIGINT AUTO_INCREMENT;