-- ============================================
-- RAG Engine - 知识库管理模块初始化 SQL
-- ============================================

-- 知识库表
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

-- 知识库用户权限表
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