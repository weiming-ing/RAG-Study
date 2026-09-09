-- ============================================
-- 数据库迁移：取消所有 UUID，改用自增 ID
-- 说明：UUID 值无法转为 BIGINT，需要删除旧数据重建
-- ============================================

-- 1. 删除依赖表（先子后父）
DROP TABLE IF EXISTS knowledge_chunk;
DROP TABLE IF EXISTS knowledge_document;
DROP TABLE IF EXISTS kb_user_access;
DROP TABLE IF EXISTS kb_knowledge_base;

-- 2. 重建 kb_knowledge_base（id: BIGINT AUTO_INCREMENT）
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

-- 3. 重建 kb_user_access（kb_id: BIGINT）
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

-- 4. 重建 knowledge_document（id: BIGINT AUTO_INCREMENT, kb_id: BIGINT）
CREATE TABLE IF NOT EXISTS knowledge_document (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    file_name VARCHAR(500) NOT NULL COMMENT '原始文件名',
    file_type VARCHAR(50) NOT NULL COMMENT '文件类型(txt/md/pdf/docx)',
    file_size BIGINT NOT NULL DEFAULT 0 COMMENT '文件大小(字节)',
    kb_id BIGINT DEFAULT NULL COMMENT '所属知识库ID',
    department VARCHAR(100) DEFAULT NULL COMMENT '所属部门',
    category VARCHAR(100) DEFAULT NULL COMMENT '文档分类',
    total_chunks INT NOT NULL DEFAULT 0 COMMENT '子块总数',
    total_parent_chunks INT NOT NULL DEFAULT 0 COMMENT '父块总数',
    status VARCHAR(20) NOT NULL DEFAULT 'processing' COMMENT '状态: PENDING/PARSING/CHUNKING/VECTORIZING/READY/FAILED',
    summary TEXT COMMENT '摘要',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标志',
    INDEX idx_kb_id (kb_id),
    INDEX idx_department (department),
    INDEX idx_category (category),
    INDEX idx_status (status),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档表';

-- 5. 重建 knowledge_chunk（id: BIGINT AUTO_INCREMENT）
CREATE TABLE IF NOT EXISTS knowledge_chunk (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id BIGINT NOT NULL COMMENT '所属文档ID',
    chunk_id VARCHAR(100) NOT NULL COMMENT '分块标识',
    chunk_index INT NOT NULL DEFAULT 0 COMMENT '分块序号',
    content TEXT NOT NULL COMMENT '分块内容',
    content_length INT NOT NULL DEFAULT 0 COMMENT '内容长度',
    parent_chunk_id VARCHAR(100) NOT NULL DEFAULT '' COMMENT '父块ID',
    parent_chunk_index INT NOT NULL DEFAULT 0 COMMENT '父块序号',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除',
    INDEX idx_document_id (document_id),
    INDEX idx_chunk_id (chunk_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档分块表';

-- 6. 重置自增起始值
ALTER TABLE kb_knowledge_base AUTO_INCREMENT = 1;
ALTER TABLE kb_user_access AUTO_INCREMENT = 1;
ALTER TABLE knowledge_document AUTO_INCREMENT = 1;
ALTER TABLE knowledge_chunk AUTO_INCREMENT = 1;

-- 完成
SELECT 'Migration completed successfully!' AS result;