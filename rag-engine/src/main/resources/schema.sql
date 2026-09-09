-- RAG知识库引擎 - 数据库初始化脚本
-- 执行前请先创建数据库: CREATE DATABASE rag_engine DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE rag_engine;

-- 知识库文档表
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
    status VARCHAR(20) NOT NULL DEFAULT 'processing' COMMENT '状态: processing/indexed/failed',
    summary TEXT DEFAULT NULL COMMENT '文档摘要',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_kb_id (kb_id),
    INDEX idx_department (department),
    INDEX idx_category (category),
    INDEX idx_status (status),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档表';

-- 知识库分块表
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