-- ============================================
-- 数据迁移: users 表 → sys_user 表
-- 将 Python 后端使用的 users 表合并到 Java 后端的 sys_user 表
-- ============================================

-- 1. 将 users 表中不存在于 sys_user 的数据迁移过去
INSERT INTO sys_user (username, password, display_name, status, create_time, update_time)
SELECT 
    u.username,
    u.password_hash AS password,
    COALESCE(u.display_name, u.username) AS display_name,
    1 AS status,
    u.created_at AS create_time,
    u.updated_at AS update_time
FROM users u
LEFT JOIN sys_user su ON u.username = su.username
WHERE su.id IS NULL;

-- 2. 检查迁移结果
SELECT 
    '迁移结果' AS info,
    (SELECT COUNT(*) FROM users) AS users_count,
    (SELECT COUNT(*) FROM sys_user) AS sys_user_count;

-- 3. 确认数据无误后，手动执行以下语句删除旧表:
-- DROP TABLE IF EXISTS users;