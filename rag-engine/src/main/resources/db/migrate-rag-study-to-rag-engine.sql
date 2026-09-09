-- ============================================
-- 数据迁移: rag_study_db.sys_user → rag_engine.sys_user
-- 将 Python 后端之前注册的用户迁移到统一数据库
-- ============================================

-- 1. 将 rag_study_db 中不存在于 rag_engine 的用户迁移过去
INSERT INTO rag_engine.sys_user (username, password, display_name, status, create_time, update_time)
SELECT 
    u.username,
    u.password,
    COALESCE(u.display_name, u.username) AS display_name,
    COALESCE(u.status, 1) AS status,
    u.create_time,
    u.update_time
FROM rag_study_db.sys_user u
LEFT JOIN rag_engine.sys_user su ON u.username = su.username
WHERE su.id IS NULL;

-- 2. 检查迁移结果
SELECT 
    'rag_study_db' AS source,
    COUNT(*) AS user_count
FROM rag_study_db.sys_user
UNION ALL
SELECT 
    'rag_engine' AS target,
    COUNT(*) AS user_count
FROM rag_engine.sys_user;

-- 3. 确认数据无误后，可删除旧数据库
-- DROP DATABASE IF EXISTS rag_study_db;