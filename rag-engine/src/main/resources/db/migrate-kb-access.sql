-- 知识库三级访问隔离迁移（2026-10-24）
-- is_public 二值标志升级为 visibility 三级：
--   PUBLIC     公共级——所有人可见可检索，含访客
--   EMPLOYEE   员工级——任何登录用户可见可检索（默认）
--   MANAGEMENT 管理级——仅 kb_user_access 授权人 + KB owner + ROLE_ADMIN
-- 存量映射（忠实旧语义）：is_public=1 → PUBLIC；is_public=0 → MANAGEMENT。
-- is_public 列保留并与 visibility 同步维护（PUBLIC=1 其余=0），兼容未迁移读取点。

ALTER TABLE kb_knowledge_base
    ADD COLUMN visibility VARCHAR(16) NOT NULL DEFAULT 'EMPLOYEE'
    COMMENT '可见级别: PUBLIC-公共级 EMPLOYEE-员工级 MANAGEMENT-管理级';

UPDATE kb_knowledge_base SET visibility = 'PUBLIC' WHERE is_public = 1;
UPDATE kb_knowledge_base SET visibility = 'MANAGEMENT' WHERE is_public = 0;

CREATE INDEX idx_kb_visibility ON kb_knowledge_base (visibility);
