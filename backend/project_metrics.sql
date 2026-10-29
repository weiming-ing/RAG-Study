-- ============================================================
-- RAG 助手 — 项目数据衡量指标 SQL 查询集
-- ============================================================
-- 使用方法：
--   1. 连接到 rag_engine 数据库
--   2. 逐段执行以下查询
--   3. 将结果填入 generate_report.py 的对应字段
-- ============================================================

-- ==========================================
-- 一、概要统计
-- ==========================================
SELECT
    (SELECT COUNT(*) FROM kb_knowledge_base)          AS 知识库总数,
    (SELECT COUNT(*) FROM knowledge_document WHERE deleted = 0) AS 文档总数,
    (SELECT COUNT(*) FROM knowledge_chunk WHERE deleted = 0)    AS 切片总数,
    (SELECT COUNT(*) FROM conversation_log)            AS 对话总数,
    (SELECT COUNT(*) FROM sys_user)                    AS 用户总数;

-- ==========================================
-- 二、文档分析
-- ==========================================
-- 2.1 文档类型分布
SELECT file_type, COUNT(*) AS cnt
FROM knowledge_document
WHERE deleted = 0
GROUP BY file_type
ORDER BY cnt DESC;

-- 2.2 文档状态分布
SELECT status, COUNT(*) AS cnt
FROM knowledge_document
WHERE deleted = 0
GROUP BY status;

-- 2.3 平均每文档切片数
SELECT
    COUNT(*) AS total_docs,
    ROUND(AVG(total_chunks), 1) AS avg_chunks_per_doc,
    ROUND(AVG(file_size / 1024), 1) AS avg_size_kb
FROM knowledge_document
WHERE deleted = 0 AND total_chunks > 0;

-- ==========================================
-- 三、对话质量（用户反馈）
-- ==========================================
-- 3.1 用户满意度
SELECT
    COUNT(*) AS total_feedbacks,
    SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END)    AS likes,
    SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END)   AS dislikes,
    SUM(CASE WHEN feedback = 0 OR feedback IS NULL THEN 1 ELSE 0 END) AS neutral,
    ROUND(SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN feedback IN (1, -1) THEN 1 ELSE 0 END), 0) * 100, 1)
        AS satisfaction_rate_pct
FROM conversation_log;

-- 3.2 点踩原因分布
SELECT feedback_reason, COUNT(*) AS cnt
FROM conversation_log
WHERE feedback = -1 AND feedback_reason IS NOT NULL
GROUP BY feedback_reason
ORDER BY cnt DESC;

-- 3.3 每日反馈趋势
SELECT
    DATE(create_time) AS stat_date,
    COUNT(*) AS total,
    SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) AS likes,
    SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) AS dislikes
FROM conversation_log
WHERE create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(create_time)
ORDER BY stat_date;

-- ==========================================
-- 四、性能指标
-- ==========================================
-- 4.1 响应延迟分布
SELECT
    COUNT(*) AS total_samples,
    ROUND(AVG(latency_ms), 0)       AS avg_latency_ms,
    ROUND(MIN(latency_ms), 0)       AS min_latency_ms,
    ROUND(MAX(latency_ms), 0)       AS max_latency_ms,
    -- 百分位数近似
    ROUND(AVG(CASE WHEN rn <= total * 0.50 THEN latency_ms END), 0) AS p50_ms,
    ROUND(AVG(CASE WHEN rn <= total * 0.90 THEN latency_ms END), 0) AS p90_ms,
    ROUND(AVG(CASE WHEN rn <= total * 0.95 THEN latency_ms END), 0) AS p95_ms,
    ROUND(AVG(CASE WHEN rn <= total * 0.99 THEN latency_ms END), 0) AS p99_ms
FROM (
    SELECT
        latency_ms,
        ROW_NUMBER() OVER (ORDER BY latency_ms) AS rn,
        COUNT(*) OVER () AS total
    FROM conversation_log
    WHERE latency_ms IS NOT NULL AND latency_ms > 0 AND latency_ms < 60000
) t;

-- 4.2 Token 消耗统计
SELECT
    SUM(total_tokens)                   AS total_tokens,
    ROUND(AVG(prompt_tokens), 0)        AS avg_prompt_tokens,
    ROUND(AVG(completion_tokens), 0)    AS avg_completion_tokens,
    ROUND(AVG(total_tokens), 0)         AS avg_total_tokens
FROM token_usage_stat;

-- 4.3 API 调用统计汇总
SELECT
    COUNT(DISTINCT api_path)        AS unique_apis,
    SUM(call_count)                 AS total_calls,
    ROUND(AVG(success_count * 100.0 / NULLIF(call_count, 0)), 1) AS avg_success_rate_pct,
    ROUND(AVG(avg_latency_ms), 0)   AS avg_latency_ms
FROM api_call_stat;

-- ==========================================
-- 五、使用趋势
-- ==========================================
-- 5.1 每日对话量（近30天）
SELECT
    DATE(create_time) AS stat_date,
    COUNT(*) AS daily_conversations
FROM conversation_log
WHERE create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(create_time)
ORDER BY stat_date;

-- 5.2 活跃用户数（近30天）
SELECT
    COUNT(DISTINCT user_id) AS active_users_30d
FROM conversation_log
WHERE user_id IS NOT NULL
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY);

-- 5.3 日均对话量
SELECT
    ROUND(COUNT(*) / NULLIF(DATEDIFF(NOW(), MIN(DATE(create_time))), 0), 1) AS avg_daily_conversations
FROM conversation_log;

-- ==========================================
-- 六、文档热度和利用率
-- ==========================================
-- 6.1 被引用过的文档比例
SELECT
    (SELECT COUNT(*) FROM knowledge_document WHERE deleted = 0)           AS total_docs,
    COUNT(DISTINCT document_id)                                           AS referenced_docs,
    ROUND(COUNT(DISTINCT document_id) * 100.0
          / NULLIF((SELECT COUNT(*) FROM knowledge_document WHERE deleted = 0), 0), 1)
        AS utilization_rate_pct
FROM doc_hot_stat
WHERE hit_count > 0;

-- 6.2 热门文档 Top 10
SELECT doc_name, SUM(hit_count) AS total_hits
FROM doc_hot_stat
GROUP BY doc_name
ORDER BY total_hits DESC
LIMIT 10;

-- 6.3 知识库热度排行
SELECT kb_id, document_id, SUM(hit_count) AS total_hits
FROM doc_hot_stat
GROUP BY kb_id, document_id
ORDER BY total_hits DESC
LIMIT 10;

-- ==========================================
-- 七、工程规模
-- ==========================================
-- 7.1 数据库表总数
SELECT COUNT(*) AS total_tables
FROM information_schema.tables
WHERE table_schema = 'rag_engine'
  AND table_type = 'BASE TABLE';

-- 7.2 各表数据量
SELECT
    table_name,
    table_rows,
    ROUND(data_length / 1024 / 1024, 2) AS data_mb
FROM information_schema.tables
WHERE table_schema = 'rag_engine'
  AND table_type = 'BASE TABLE'
ORDER BY table_rows DESC;

-- ==========================================
-- 八、知识库分布
-- ==========================================
SELECT
    kb.name                                                  AS 知识库名称,
    COALESCE(dc.doc_count, 0)                                AS 文档数,
    COALESCE(cc.chunk_count, 0)                              AS 切片数,
    COALESCE(cl.conv_count, 0)                               AS 对话数
FROM kb_knowledge_base kb
LEFT JOIN (
    SELECT kb_id, COUNT(*) AS doc_count
    FROM knowledge_document
    WHERE deleted = 0
    GROUP BY kb_id
) dc ON kb.id = dc.kb_id
LEFT JOIN (
    SELECT d.kb_id, COUNT(*) AS chunk_count
    FROM knowledge_chunk c
    JOIN knowledge_document d ON c.document_id = d.id
    WHERE c.deleted = 0 AND d.deleted = 0
    GROUP BY d.kb_id
) cc ON kb.id = cc.kb_id
LEFT JOIN (
    SELECT kb_id, COUNT(*) AS conv_count
    FROM conversation_log
    WHERE kb_id IS NOT NULL
    GROUP BY kb_id
) cl ON kb.id = cl.kb_id
ORDER BY COALESCE(cl.conv_count, 0) DESC;