"""
数据迁移脚本：将备份中的 UUID 数据转为新的 BIGINT 自增 ID

策略：
1. 创建临时数据库 rag_engine_temp
2. 在临时数据库中创建正确的表结构（包含 kb_id 字段）
3. 手动解析备份 SQL 中的 INSERT 语句，提取数据
4. 将数据从临时库迁移到主库（UUID → BIGINT 映射）
5. 删除临时数据库
"""
import pymysql
import re
import os

# 数据库配置（从环境变量读取，敏感信息不硬编码）
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USERNAME", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_DATABASE", "rag_engine"),
    "charset": "utf8mb4",
}

TEMP_DB = "rag_engine_temp"
BACKUP_FILE = r"D:\RAG-study\rag-engine\src\main\resources\db\backup_before_migration.sql"


def execute(conn, sql, args=None):
    cur = conn.cursor()
    cur.execute(sql, args)
    conn.commit()
    return cur


def parse_insert_values(sql_content, table_name):
    """解析备份 SQL 中指定表的 INSERT 语句，提取所有 VALUES 行"""
    # 匹配 INSERT INTO `table_name` VALUES (...),(...),...;
    pattern = re.compile(
        r"INSERT\s+INTO\s+`" + re.escape(table_name) + r"`\s+VALUES\s*"
        r"(\(.*?\))\s*;",
        re.DOTALL | re.IGNORECASE
    )
    matches = pattern.findall(sql_content)
    
    all_rows = []
    for match in matches:
        # 提取所有括号内的值元组
        values_str = match.strip()
        # 处理嵌套括号：逐个字符解析
        i = 0
        while i < len(values_str):
            if values_str[i] == '(':
                depth = 1
                j = i + 1
                while j < len(values_str) and depth > 0:
                    if values_str[j] == '(' and not (j > 0 and values_str[j-1] == '\\'):
                        depth += 1
                    elif values_str[j] == ')' and not (j > 0 and values_str[j-1] == '\\'):
                        depth -= 1
                    j += 1
                row_str = values_str[i+1:j-1]
                # 解析单个行的值
                row_values = parse_row_values(row_str)
                if row_values:
                    all_rows.append(row_values)
                i = j
            elif values_str[i] == ',':
                i += 1
            else:
                i += 1
    
    return all_rows


def parse_row_values(row_str):
    """解析单行 VALUES 中的各个字段值"""
    values = []
    i = 0
    current = ""
    in_string = False
    string_char = None
    
    while i < len(row_str):
        ch = row_str[i]
        
        if in_string:
            if ch == '\\' and i + 1 < len(row_str):
                # 处理转义字符
                next_ch = row_str[i + 1]
                if next_ch == 'n':
                    current += '\n'
                elif next_ch == 't':
                    current += '\t'
                elif next_ch == 'r':
                    current += '\r'
                elif next_ch == '\\':
                    current += '\\'
                elif next_ch == "'":
                    current += "'"
                elif next_ch == '"':
                    current += '"'
                else:
                    current += ch + next_ch
                i += 2
            elif ch == string_char:
                in_string = False
                i += 1
            else:
                current += ch
                i += 1
        else:
            if ch == "'" or ch == '"':
                in_string = True
                string_char = ch
                i += 1
            elif ch == ',':
                values.append(current.strip())
                current = ""
                i += 1
            elif ch == ' ' or ch == '\t' or ch == '\n' or ch == '\r':
                # 跳过空白
                i += 1
            else:
                current += ch
                i += 1
    
    if current.strip():
        values.append(current.strip())
    
    return values


def fix_garbled_chinese(text):
    """
    修复 PowerShell 重定向导致的"双重编码"问题：
    MySQL 输出 UTF-8 → PowerShell 用系统 ANSI 编码（Windows 中文版为 GBK）
    读取并转换为 UTF-16LE 写入文件
    
    修复方法：将文本用 mbcs（Windows 系统默认编码）编码回原始字节，
    再将字节按 UTF-8 解码，即可得到正确的中文。
    """
    # 统计非 ASCII 字符
    non_ascii = [c for c in text if ord(c) > 127]
    if len(non_ascii) < 2:
        return text
    
    # 检查是否包含已知的乱码模式
    garbled_markers = ['璐㈠', '姟鎶', 'ラ攢', '绠＄', '悊鍒', '跺害', '浼佷笟', '绠＄悊',
                       '淇濆瘑', '涓庡姙', '鍏徃', '浜嬪姟']
    has_garbled = any(marker in text for marker in garbled_markers)
    if not has_garbled:
        return text  # 没有乱码特征，无需修复
    
    # 使用 mbcs（Windows 系统默认 ANSI 编码，中文 Windows 上为 GBK）
    try:
        cleaned = text.replace('\ufeff', '')
        # mbcs 使用 Windows 系统默认代码页（中文 Windows = CP936/GBK）
        raw_bytes = cleaned.encode('mbcs')
        fixed = raw_bytes.decode('utf-8', errors='replace')
        print(f"  检测到编码问题（GBK/UTF-8 双重编码），已修复中文编码")
        return fixed
    except Exception as e:
        print(f"  编码修复失败: {e}")
        return text


def read_backup_sql():
    """读取备份 SQL 文件，处理编码"""
    # 二进制读取并检测 BOM
    with open(BACKUP_FILE, "rb") as f:
        raw = f.read()
    
    content = None
    encoding_used = None
    
    if raw.startswith(b'\xff\xfe'):
        content = raw.decode('utf-16-le')
        encoding_used = 'utf-16-le (BOM)'
    elif raw.startswith(b'\xfe\xff'):
        content = raw.decode('utf-16-be')
        encoding_used = 'utf-16-be (BOM)'
    elif raw.startswith(b'\xef\xbb\xbf'):
        content = raw.decode('utf-8-sig')
        encoding_used = 'utf-8-sig (BOM)'
    else:
        # 尝试常见编码
        for enc in ["utf-8", "gbk", "latin-1"]:
            try:
                content = raw.decode(enc)
                encoding_used = enc
                break
            except UnicodeDecodeError:
                continue
    
    if content is None:
        content = raw.decode('latin-1')
        encoding_used = 'latin-1 (fallback)'
    
    print(f"  使用编码: {encoding_used}")
    
    # 修复 PowerShell 导致的 GBK/UTF-8 双重编码问题
    content = fix_garbled_chinese(content)
    
    return content


def main():
    conn = pymysql.connect(**DB_CONFIG)
    conn.autocommit = True

    try:
        # 1. 创建临时数据库
        print("创建临时数据库...")
        execute(conn, f"DROP DATABASE IF EXISTS `{TEMP_DB}`")
        execute(conn, f"CREATE DATABASE `{TEMP_DB}` DEFAULT CHARSET utf8mb4")

        # 2. 在临时数据库中创建正确的表结构
        print("创建表结构...")
        execute(conn, f"USE `{TEMP_DB}`")
        
        # kb_knowledge_base（与备份一致）
        execute(conn, """
            CREATE TABLE `kb_knowledge_base` (
              `id` varchar(64) NOT NULL,
              `name` varchar(128) NOT NULL,
              `description` text,
              `category` varchar(64) DEFAULT NULL,
              `tags` text,
              `cover_url` varchar(255) DEFAULT NULL,
              `owner_id` bigint DEFAULT NULL,
              `department` varchar(64) DEFAULT NULL,
              `is_public` tinyint DEFAULT '1',
              `status` varchar(16) DEFAULT 'ENABLED',
              `chunk_size` int DEFAULT '300',
              `chunk_overlap` int DEFAULT '50',
              `embedding_model` varchar(64) DEFAULT 'default',
              `top_k` int DEFAULT '10',
              `similarity_threshold` double DEFAULT '0.6',
              `vector_weight` double DEFAULT '0.7',
              `bm25_weight` double DEFAULT '0.3',
              `enable_rerank` tinyint DEFAULT '1',
              `filter_low_score` tinyint DEFAULT '0',
              `prompt_template` text,
              `blacklist_words` text,
              `whitelist_words` text,
              `create_time` datetime DEFAULT NULL,
              `update_time` datetime DEFAULT NULL,
              `deleted` tinyint DEFAULT '0',
              PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # knowledge_document（补充 kb_id 字段）
        execute(conn, """
            CREATE TABLE `knowledge_document` (
              `id` varchar(64) NOT NULL,
              `file_name` varchar(500) NOT NULL,
              `file_type` varchar(50) NOT NULL,
              `file_size` bigint NOT NULL DEFAULT '0',
              `kb_id` varchar(64) DEFAULT NULL,
              `department` varchar(100) DEFAULT NULL,
              `category` varchar(100) DEFAULT NULL,
              `total_chunks` int NOT NULL DEFAULT '0',
              `total_parent_chunks` int NOT NULL DEFAULT '0',
              `status` varchar(20) NOT NULL DEFAULT 'processing',
              `summary` text,
              `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
              `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              `deleted` tinyint NOT NULL DEFAULT '0',
              PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # knowledge_chunk
        execute(conn, """
            CREATE TABLE `knowledge_chunk` (
              `id` bigint NOT NULL,
              `document_id` varchar(64) NOT NULL,
              `chunk_id` varchar(100) NOT NULL,
              `chunk_index` int NOT NULL DEFAULT '0',
              `content` text NOT NULL,
              `content_length` int NOT NULL DEFAULT '0',
              `parent_chunk_id` varchar(100) NOT NULL,
              `parent_chunk_index` int NOT NULL DEFAULT '0',
              `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
              `deleted` tinyint NOT NULL DEFAULT '0',
              PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # kb_user_access（补充 kb_id 字段）
        execute(conn, """
            CREATE TABLE `kb_user_access` (
              `id` bigint NOT NULL,
              `kb_id` varchar(64) NOT NULL,
              `user_id` bigint NOT NULL,
              `access_level` varchar(16) NOT NULL DEFAULT 'READ',
              `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              UNIQUE KEY `uk_kb_user` (`kb_id`,`user_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 3. 读取备份 SQL 并解析 INSERT 数据
        print("读取备份 SQL...")
        sql_content = read_backup_sql()
        
        # 跳过 PowerShell 警告头部
        start_marker = "-- MySQL dump"
        idx = sql_content.find(start_marker)
        if idx >= 0:
            sql_content = sql_content[idx:]

        # 3a. 解析并导入 kb_knowledge_base
        print("\n解析知识库数据...")
        kb_rows = parse_insert_values(sql_content, "kb_knowledge_base")
        print(f"  找到 {len(kb_rows)} 条知识库记录")
        
        kb_count = 0
        for row in kb_rows:
            if len(row) < 25:  # 至少需要 25 个字段
                print(f"  跳过无效行: {len(row)} 个字段")
                continue
            try:
                execute(conn, f"""
                    INSERT INTO `{TEMP_DB}`.kb_knowledge_base
                    (id, name, description, category, tags, cover_url, owner_id,
                     department, is_public, status, chunk_size, chunk_overlap,
                     embedding_model, top_k, similarity_threshold, vector_weight,
                     bm25_weight, enable_rerank, filter_low_score,
                     prompt_template, blacklist_words, whitelist_words,
                     create_time, update_time, deleted)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, tuple(row[:25]))
                kb_count += 1
            except Exception as e:
                print(f"  跳过知识库: {e}")
        print(f"  导入 {kb_count} 条知识库")

        # 3b. 解析并导入 knowledge_document
        print("\n解析文档数据...")
        # 由于备份中的 knowledge_document 表缺少 kb_id 字段，
        # 备份数据中 kb_id 值被存入了 department 字段
        # 需要根据 ID 格式判断：
        # - UUID 格式的 ID（如 62cef503...）：department 字段实际是 kb_id
        # - 数字格式的 ID（如 8,9,10...）：department 字段是真实的部门名
        doc_rows = parse_insert_values(sql_content, "knowledge_document")
        print(f"  找到 {len(doc_rows)} 条文档记录")
        
        doc_count = 0
        for row in doc_rows:
            if len(row) < 13:
                print(f"  跳过无效行: {len(row)} 个字段")
                continue
            
            doc_id = row[0].strip("'\"")
            file_name = row[1].strip("'\"")
            file_type = row[2].strip("'\"")
            file_size = row[3]
            field4 = row[4].strip("'\"")  # 备份中第5列：UUID文档是kb_id，数字文档是department
            field5 = row[5].strip("'\"")  # 备份中第6列：UUID文档是NULL，数字文档是category
            total_chunks = row[6]
            total_parent_chunks = row[7]
            status = row[8].strip("'\"")
            summary = row[9].strip("'\"") if row[9] != 'NULL' else None
            create_time = row[10].strip("'\"") if row[10] != 'NULL' else None
            update_time = row[11].strip("'\"") if row[11] != 'NULL' else None
            deleted = row[12]
            
            # 判断文档 ID 是否为 UUID 格式
            is_uuid_id = bool(re.match(r'^[0-9a-f]{32}$', doc_id, re.IGNORECASE))
            
            if is_uuid_id:
                # UUID 文档：field4 是 kb_id，field5 是 department
                kb_id = field4 if field4 != 'NULL' else None
                department = field5 if field5 != 'NULL' else None
                category = None
            else:
                # 数字文档：field4 是 department，field5 是 category
                kb_id = None
                department = field4 if field4 != 'NULL' else None
                category = field5 if field5 != 'NULL' else None
            
            try:
                execute(conn, f"""
                    INSERT INTO `{TEMP_DB}`.knowledge_document
                    (id, file_name, file_type, file_size, kb_id, department,
                     category, total_chunks, total_parent_chunks, status,
                     summary, create_time, update_time, deleted)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (doc_id, file_name, file_type, file_size, kb_id,
                      department, category, total_chunks, total_parent_chunks,
                      status, summary, create_time, update_time, deleted))
                doc_count += 1
            except Exception as e:
                print(f"  跳过文档 {doc_id}: {e}")
        print(f"  导入 {doc_count} 条文档")

        # 3c. 解析并导入 knowledge_chunk
        print("\n解析分块数据...")
        chunk_rows = parse_insert_values(sql_content, "knowledge_chunk")
        print(f"  找到 {len(chunk_rows)} 条分块记录")
        
        chunk_count = 0
        for row in chunk_rows:
            if len(row) < 10:
                continue
            try:
                chunk_id = row[0]
                doc_id = row[1].strip("'\"")
                chunk_id_val = row[2].strip("'\"")
                chunk_index = row[3]
                content = row[4].strip("'\"")
                content_length = row[5]
                parent_chunk_id = row[6].strip("'\"")
                parent_chunk_index = row[7]
                create_time = row[8].strip("'\"") if row[8] != 'NULL' else None
                deleted = row[9]
                
                execute(conn, f"""
                    INSERT INTO `{TEMP_DB}`.knowledge_chunk
                    (id, document_id, chunk_id, chunk_index, content,
                     content_length, parent_chunk_id, parent_chunk_index,
                     create_time, deleted)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (chunk_id, doc_id, chunk_id_val, chunk_index, content,
                      content_length, parent_chunk_id, parent_chunk_index,
                      create_time, deleted))
                chunk_count += 1
            except Exception as e:
                print(f"  跳过 chunk: {e}")
        print(f"  导入 {chunk_count} 条分块")

        # 3d. 解析并导入 kb_user_access
        print("\n解析权限数据...")
        access_rows = parse_insert_values(sql_content, "kb_user_access")
        print(f"  找到 {len(access_rows)} 条权限记录")
        
        access_count = 0
        for row in access_rows:
            if len(row) < 5:
                continue
            try:
                execute(conn, f"""
                    INSERT INTO `{TEMP_DB}`.kb_user_access
                    (id, kb_id, user_id, access_level, create_time)
                    VALUES (%s,%s,%s,%s,%s)
                """, tuple(row[:5]))
                access_count += 1
            except Exception as e:
                print(f"  跳过权限: {e}")
        print(f"  导入 {access_count} 条权限")

        # 4. 验证临时数据库
        print("\n--- 验证临时数据库 ---")
        cur = execute(conn, f"USE `{TEMP_DB}`")
        for tbl in ["kb_knowledge_base", "knowledge_document", "knowledge_chunk", "kb_user_access"]:
            cur = execute(conn, f"SELECT COUNT(*) FROM {tbl}")
            print(f"  {tbl}: {cur.fetchone()[0]} 条")

        # 5. 迁移数据到主库
        print("\n=== 开始迁移数据到主库 ===")
        execute(conn, f"USE rag_engine")

        # 5a. 迁移 kb_knowledge_base
        print("\n迁移知识库...")
        cur = execute(conn, f"USE `{TEMP_DB}`")
        cur = execute(conn, "SELECT * FROM kb_knowledge_base WHERE deleted = 0")
        old_kb_rows = cur.fetchall()
        
        execute(conn, f"USE rag_engine")
        cur = execute(conn, "SELECT COALESCE(MAX(id), 0) FROM kb_knowledge_base")
        next_kb_id = cur.fetchone()[0] + 1
        print(f"  当前知识库最大 ID: {next_kb_id - 1}")

        # 获取主库中已有的知识库名称映射
        cur = execute(conn, "SELECT id, name FROM kb_knowledge_base")
        existing_kbs = {row[1]: row[0] for row in cur.fetchall()}
        print(f"  主库已有知识库: {list(existing_kbs.keys())}")

        uuid_to_kb_id = {}
        for row in old_kb_rows:
            old_id = row[0]  # UUID
            name = row[1]
            
            if name in existing_kbs:
                new_id = existing_kbs[name]
                print(f"  知识库已存在: {name} (ID #{new_id}), 跳过")
            else:
                new_id = next_kb_id
                execute(conn, """
                    INSERT INTO kb_knowledge_base
                    (id, name, description, category, tags, cover_url, owner_id,
                     department, is_public, status, chunk_size, chunk_overlap,
                     embedding_model, top_k, similarity_threshold, vector_weight,
                     bm25_weight, enable_rerank, filter_low_score,
                     prompt_template, blacklist_words, whitelist_words,
                     create_time, update_time, deleted)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)
                """, (new_id,) + row[1:-1])
                next_kb_id += 1
                print(f"  知识库 #{new_id}: {name}")
            
            uuid_to_kb_id[old_id] = new_id

        # 强制迁移所有知识库（包括 deleted=1 的，因为文档可能引用它们）
        print("\n  强制迁移所有被引用的知识库...")
        execute(conn, f"USE `{TEMP_DB}`")
        cur = execute(conn, "SELECT * FROM kb_knowledge_base")
        all_kb_rows = cur.fetchall()
        
        execute(conn, f"USE rag_engine")
        for row in all_kb_rows:
            old_id = row[0]
            if old_id in uuid_to_kb_id:
                continue
            name = row[1]
            if name in existing_kbs:
                uuid_to_kb_id[old_id] = existing_kbs[name]
                print(f"  知识库已存在: {name} (ID #{existing_kbs[name]}), 跳过")
                continue
            new_id = next_kb_id
            execute(conn, """
                INSERT INTO kb_knowledge_base
                (id, name, description, category, tags, cover_url, owner_id,
                 department, is_public, status, chunk_size, chunk_overlap,
                 embedding_model, top_k, similarity_threshold, vector_weight,
                 bm25_weight, enable_rerank, filter_low_score,
                 prompt_template, blacklist_words, whitelist_words,
                 create_time, update_time, deleted)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)
            """, (new_id,) + row[1:-1])
            uuid_to_kb_id[old_id] = new_id
            next_kb_id += 1
            print(f"  知识库 #{new_id}: {name}（强制迁移）")

        print(f"\n  UUID→KB_ID 映射: {uuid_to_kb_id}")

        # 5b. 迁移 knowledge_document
        print("\n迁移文档...")
        execute(conn, f"USE `{TEMP_DB}`")
        cur = execute(conn, """
            SELECT id, file_name, file_type, file_size, kb_id, department,
                   category, total_chunks, total_parent_chunks, status,
                   summary, create_time, update_time, deleted
            FROM knowledge_document
            WHERE deleted = 0
        """)
        old_doc_rows = cur.fetchall()

        execute(conn, f"USE rag_engine")
        cur = execute(conn, "SELECT COALESCE(MAX(id), 0) FROM knowledge_document")
        next_doc_id = cur.fetchone()[0] + 1
        print(f"  当前文档最大 ID: {next_doc_id - 1}")

        uuid_to_doc_id = {}
        # 缓存已创建的"按名称匹配"的知识库
        name_to_kb = {}
        cur = execute(conn, "SELECT id, name FROM kb_knowledge_base")
        for r in cur.fetchall():
            name_to_kb[r[1]] = r[0]
        # 用于创建新知识库的 ID
        cur = execute(conn, "SELECT COALESCE(MAX(id), 0) FROM kb_knowledge_base")
        next_kb_id_for_orphan = cur.fetchone()[0] + 1

        for row in old_doc_rows:
            old_id = row[0]
            old_kb_id = row[4]  # kb_id 字段
            new_id = next_doc_id
            new_kb_id = uuid_to_kb_id.get(old_kb_id)
            
            if new_kb_id is None:
                # 数字ID文档：尝试根据 department 名称查找或创建知识库
                dept_name = row[5]  # department 字段
                if dept_name and dept_name != 'NULL':
                    if dept_name in name_to_kb:
                        new_kb_id = name_to_kb[dept_name]
                        print(f"  文档 {old_id} ({row[1]}): 匹配到知识库 '{dept_name}' (ID #{new_kb_id})")
                    else:
                        new_kb_id = next_kb_id_for_orphan
                        now_val = "2025-07-21 15:35:32"
                        execute(conn, """
                            INSERT INTO kb_knowledge_base
                            (id, name, description, category, tags, cover_url, owner_id,
                             department, is_public, status, chunk_size, chunk_overlap,
                             embedding_model, top_k, similarity_threshold, vector_weight,
                             bm25_weight, enable_rerank, filter_low_score,
                             prompt_template, blacklist_words, whitelist_words,
                             create_time, update_time, deleted)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)
                        """, (new_kb_id, dept_name, '', '', '', '', 0, '', 0, 'ENABLED', 300, 50,
                              'text2vec-base-chinese', 3, 0.6, 0.5, 0.5, 0, 0, '', '', '',
                              now_val, now_val))
                        name_to_kb[dept_name] = new_kb_id
                        next_kb_id_for_orphan += 1
                        print(f"  文档 {old_id} ({row[1]}): 创建知识库 '{dept_name}' (ID #{new_kb_id})")
                else:
                    print(f"  跳过文档 {old_id} ({row[1]}): 知识库 {old_kb_id} 未迁移，且 department 为空")
                    next_doc_id += 1
                    continue

            # 检查是否已存在同名文档
            cur = execute(conn, "SELECT id FROM knowledge_document WHERE file_name = %s AND kb_id = %s AND deleted = 0 LIMIT 1",
                         (row[1], new_kb_id))
            existing_doc = cur.fetchone()
            if existing_doc:
                uuid_to_doc_id[old_id] = existing_doc[0]
                print(f"  文档已存在: {row[1]} (KB #{new_kb_id}), ID #{existing_doc[0]}, 跳过")
                next_doc_id += 1
                continue

            execute(conn, """
                INSERT INTO knowledge_document
                (id, file_name, file_type, file_size, kb_id, department,
                 category, total_chunks, total_parent_chunks, status,
                 summary, create_time, update_time, deleted)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)
            """, (new_id, row[1], row[2], row[3], new_kb_id,
                  row[5], row[6], row[7], row[8], row[9],
                  row[10], row[11], row[12]))
            uuid_to_doc_id[old_id] = new_id
            next_doc_id += 1
            print(f"  文档 #{new_id}: {row[1]} (KB #{new_kb_id})")

        # 5c. 迁移 knowledge_chunk
        print("\n迁移分块...")
        execute(conn, f"USE `{TEMP_DB}`")
        cur = execute(conn, """
            SELECT id, document_id, chunk_id, chunk_index, content,
                   content_length, parent_chunk_id, parent_chunk_index,
                   create_time, deleted
            FROM knowledge_chunk
            WHERE deleted = 0
        """)
        old_chunk_rows = cur.fetchall()

        execute(conn, f"USE rag_engine")
        cur = execute(conn, "SELECT COALESCE(MAX(id), 0) FROM knowledge_chunk")
        next_chunk_id = cur.fetchone()[0] + 1
        print(f"  当前分块最大 ID: {next_chunk_id - 1}")

        chunk_old_id_to_new_id = {}
        for row in old_chunk_rows:
            old_id = row[0]
            old_doc_id = row[1]
            new_id = next_chunk_id
            new_doc_id = uuid_to_doc_id.get(old_doc_id)
            
            if new_doc_id is None:
                print(f"  跳过 chunk {old_id}: 文档 {old_doc_id} 未迁移")
                next_chunk_id += 1
                continue

            execute(conn, """
                INSERT INTO knowledge_chunk
                (id, document_id, chunk_id, chunk_index, content,
                 content_length, parent_chunk_id, parent_chunk_index,
                 create_time, deleted)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0)
            """, (new_id, new_doc_id, row[2], row[3], row[4],
                  row[5], row[6], row[7], row[8]))
            chunk_old_id_to_new_id[old_id] = new_id
            next_chunk_id += 1

        print(f"  迁移了 {len(chunk_old_id_to_new_id)} 条分块记录")

        # 5d. 迁移 kb_user_access
        print("\n迁移用户权限...")
        execute(conn, f"USE `{TEMP_DB}`")
        cur = execute(conn, "SELECT id, kb_id, user_id, access_level, create_time FROM kb_user_access")
        old_access_rows = cur.fetchall()

        execute(conn, f"USE rag_engine")
        cur = execute(conn, "SELECT COALESCE(MAX(id), 0) FROM kb_user_access")
        next_access_id = cur.fetchone()[0] + 1
        print(f"  当前权限最大 ID: {next_access_id - 1}")

        migrated_count = 0
        for row in old_access_rows:
            old_id = row[0]
            old_kb_id = row[1]
            new_id = next_access_id
            new_kb_id = uuid_to_kb_id.get(old_kb_id)
            
            if new_kb_id is None:
                print(f"  跳过权限 {old_id}: 知识库 {old_kb_id} 未迁移")
                next_access_id += 1
                continue

            # 检查是否已存在相同的 kb_id + user_id 组合
            cur = execute(conn, "SELECT id FROM kb_user_access WHERE kb_id = %s AND user_id = %s",
                         (new_kb_id, row[2]))
            if cur.fetchone():
                print(f"  跳过权限 {old_id}: 已存在 (kb_id={new_kb_id}, user_id={row[2]})")
                next_access_id += 1
                continue

            execute(conn, """
                INSERT INTO kb_user_access
                (id, kb_id, user_id, access_level, create_time)
                VALUES (%s,%s,%s,%s,%s)
            """, (new_id, new_kb_id, row[2], row[3], row[4]))
            next_access_id += 1
            migrated_count += 1

        print(f"  迁移了 {migrated_count} 条权限记录")

        # 6. 清理临时数据库
        print("\n清理临时数据库...")
        execute(conn, f"DROP DATABASE IF EXISTS `{TEMP_DB}`")

        # 7. 输出迁移统计
        print("\n=== 迁移完成! ===")
        print(f"知识库: {len(uuid_to_kb_id)} 条")
        print(f"文档: {len(uuid_to_doc_id)} 条")
        print(f"分块: {len(chunk_old_id_to_new_id)} 条")
        print(f"权限: {migrated_count} 条")

        # 8. 验证主库数据
        print("\n--- 验证主库数据 ---")
        cur = execute(conn, "SELECT COUNT(*) FROM kb_knowledge_base")
        print(f"  知识库总数: {cur.fetchone()[0]}")

        cur = execute(conn, "SELECT COUNT(*) FROM knowledge_document WHERE deleted = 0")
        print(f"  文档(未删除): {cur.fetchone()[0]}")

        cur = execute(conn, "SELECT id, file_name, kb_id, status FROM knowledge_document WHERE deleted = 0 ORDER BY id")
        docs = cur.fetchall()
        for d in docs:
            print(f"    ID #{d[0]}: {d[1]} (KB #{d[2]}, status={d[3]})")

        cur = execute(conn, "SELECT COUNT(*) FROM knowledge_chunk WHERE deleted = 0")
        print(f"  分块(未删除): {cur.fetchone()[0]}")

        cur = execute(conn, "SELECT COUNT(*) FROM kb_user_access")
        print(f"  权限: {cur.fetchone()[0]}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()