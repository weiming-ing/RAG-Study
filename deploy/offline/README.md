# 离线交付说明（私有化部署）

本目录用于把 RAG 助手交付到**无外网**的客户内网。客户内网无法访问 Docker Hub /
PyPI / Maven Central，所以镜像必须在联网机器上构建完成后整体拷贝过去。

---

## 一、交付包结构

`build-images.ps1` 产出的 `dist/` 目录：

```
dist/
├── images/
│   └── rag-assistant-images-<版本>.tar    # 6 个镜像（应用 3 + 基础 3）
├── docker/
│   └── mysql/init.sql                     # 首次启动自动建表与初始化数据
├── reference/
│   ├── rag-assistant.conf                 # 裸机/多实例用的 Nginx 配置
│   └── rag-admin-nginx.conf               # 容器内 Nginx 配置
├── docker-compose.yml
├── env.example                            # 环境变量模板（install.sh 会据此生成 .env）
├── install.sh                             # 客户侧安装脚本
├── manifest.json                          # 版本、构建时间、git commit、镜像 ID 与 digest
├── README.md                              # 本文件
└── SHA256SUMS                             # 全量校验和
```

**建议同时记录**：`manifest.json` 里的 `gitCommit` 与各镜像 `digest`，作为交付基线存档。

---

## 二、联网侧：构建交付包

在能访问外网的机器上（需已启动 Docker）：

```powershell
# 完整构建（推荐）
pwsh -File deploy/offline/build-images.ps1 -Version 1.0.0

# 已有本地镜像，只想重新打包
pwsh -File deploy/offline/build-images.ps1 -Version 1.0.0 -SkipBuild

# 额外生成 .tar.gz（体积小，但压缩 5GB+ 较慢）
pwsh -File deploy/offline/build-images.ps1 -Version 1.0.0 -Compress
```

脚本会：预检 → `docker compose build` → 拉取基础镜像 → **记录每个镜像的 ID 与
digest** → `docker save` 打成单 tar → 组装上面的目录 → 生成 `manifest.json` 与
`SHA256SUMS`。

> **关于镜像包体积**：当前后端镜像包含 `torch` + `chromadb` +
> `sentence-transformers`（2GB+），而这条本地降级检索路径在 Docker 里因为没有
> 预置模型实际不可用。完成 **P0-3（拆成可选依赖）** 后镜像包可显著变小，建议在
> 正式交付前完成。
>
> **关于复现性**：`docker-compose.yml` 中 `qdrant/qdrant:latest` 使用了浮动标签。
> 脚本会对所有 `:latest` 镜像告警，并把实际 digest 写进 `manifest.json`。若要严格
> 复现，请把 digest 固定的版本号写回 compose 后重新打包。

---

## 三、客户侧：离线安装

1. 把整个 `dist/` 目录拷到客户机器（U 盘或内网文件服务器），例如 `/opt/rag-assistant`
2. 执行：

```bash
cd /opt/rag-assistant
chmod +x install.sh

# 先干跑一遍预检（不改动系统）
./install.sh --check-only

# 正式安装
./install.sh

# 或非交互安装（缺失项自动生成，适合脚本化交付）
./install.sh --yes

# 80 端口被占用时换端口
./install.sh --http-port 8080
```

安装脚本按顺序完成六步：**环境预检 → 校验 SHA256SUMS → 加载镜像并核对
manifest → 生成 .env → 启动服务并等待健康 → 安全自检**。

其中安全自检会验证两件事，这两条也是 P0 整改的验收点：

| 断言 | 期望 | 不通过说明 |
|---|---|---|
| 匿名访问 `/api/internal/health` | **401** | 服务间接口未受保护，检查 `INTERNAL_API_TOKEN` |
| 带 `X-Internal-Token` 访问 | **200** | 令牌不一致，检查 `.env` 与容器环境变量 |

### 安装前需要准备的信息

| 项 | 说明 |
|---|---|
| MySQL root 口令 | 留空则自动生成（24 位随机）；**务必记录** |
| LLM 服务地址 | 内网 vLLM / Ollama 等 OpenAI 兼容端点；留空则用 DeepSeek 公网（内网不可用） |
| LLM API Key | 内网模型通常不需要，可留空（会写入占位值） |

`JWT_SECRET` 与 `INTERNAL_API_TOKEN` 由脚本自动生成 64 位随机值，**Python 与 Java
必须共用同一值**，脚本已保证这一点。

---

## 四、安装后必做

1. **立即修改初始管理员密码**：初始账号为 `admin` / `admin123`（由
   `start-all-local.bat` 的注册逻辑带入），交付版本必须首登改密。
2. 确认 `.env` 权限为 `600`（脚本已设置），不要外传。
3. 配置定期备份：MySQL dump + Qdrant snapshot + `bm25_index` + `documents` 四件套。
4. 若需嵌入客户 OA / 企业微信，见下面「iframe 嵌入」。

---

## 五、常见问题

**Q：`docker compose up` 报 `set XXX in .env` 并退出？**
这是有意设计的 fail-fast：必填项缺失时直接报错，而不是回落到弱口令。按提示补齐
`.env` 中的 `MYSQL_ROOT_PASSWORD` / `DB_PASSWORD` / `JWT_SECRET` /
`INTERNAL_API_TOKEN` 即可。

**Q：管理台上传文档报 413？**
镜像里的 Nginx 配置已设 `client_max_body_size 100M`（后端上限 50M）。若你自行改造
了 Nginx，请确认该值大于等于后端的 `MAX_FILE_SIZE`。

**Q：聊天时答案一次性全部出现，没有逐字流式效果？**
说明 SSE 被缓冲了。裸机部署请检查 `deploy/nginx/rag-assistant.conf` 中
`/api/chat` 这个 location——**它比 `/api/` 更具体，Nginx 只会用它，不会叠加
`/api/` 里的设置**，所以 `proxy_buffering off` 必须在该块内重复一遍（配置已修正）。

**Q：`nginx -t` 报 `"limit_req_zone" directive is not allowed here`？**
`limit_req_zone` 是 **http 级**指令，必须在 `server {}` 之外。本仓库配置已修正；
若你把配置片段放进 `server {}` 内就会复现该错误。

**Q：要把聊天页嵌进 OA / 企业微信（跨域 iframe）？**
默认的 `X-Frame-Options: SAMEORIGIN` 会阻止跨站嵌入。请改为按域名放行：

```nginx
add_header Content-Security-Policy "frame-ancestors https://oa.customer.com" always;
# 并删除 add_header X-Frame-Options 那一行
```

同时把 `CORS_ALLOW_ORIGINS` 设为 OA 的实际域名（不要用 `*`）。

**Q：客户要用自己的私有模型，Agent 工具调用不通？**
部分私有模型的 function calling 支持较弱。可先用纯 RAG 模式验证问答链路，再逐个
排查工具调用；必要时在 `backend/utils/http_client.py` 增加兼容分支。

**Q：想回滚安装？**
`docker compose down`（保留数据卷）或 `docker compose down -v`（删除数据，危险）。

---

## 六、当前交付遗留项

| 项 | 影响 | 状态 |
|---|---|---|
| ~~**P0-3** 后端镜像瘦身~~ | ~~镜像包 4-8GB，交付介质压力大~~ | **已完成**：移除 894MB 无用依赖（本机 venv 实测），另去掉 Java 镜像中重复的 90MB 模型 |
| ~~**P0-5** 统一入口~~ | ~~80 端口当前是管理台，员工聊天页在 8001，客户会当成两个系统~~ | **已完成**：80 端口统一入口，`/` 员工聊天页、`/admin/` 管理台 |
| **P0-4** 私有 LLM 实测 | 决定政企/金融能否过技术评审 | **部分完成**：模型层已可替换（通用变量名 `LLM_*` + base_url 归一化 + `check-llm.py` 探测工具）。但**本机沙箱无法出网，未做真实端点实测**。客户若要求数据不出内网，仍需部署私有模型 |
| **P0-6** License 机制 | 无法控制分发与有效期 | **已完成**：Ed25519 离线签名授权（有效期 + 可选机器绑定 + 容量上限），含签发工具、指纹读取工具与 17 项功能测试 |
| **P1-1** OCR | 扫描件无法问答 | **第一阶段完成**：已能识别"提取不到正文"的文档并标记为 `NEEDS_OCR`（管理台显示"需OCR"、日志与审计留痕），不再出现"上传成功却检索不到"的静默失败。**OCR 引擎本身尚未接入**（本机无出网，无法安装 PaddleOCR/Tesseract） |
| 多实例脚本 | `deploy/start-python-instances.ps1` 的 `$` 被吞掉，无法运行 | 未修（Docker 部署不需要） |

---

## 七、模型（LLM）配置与数据流向

### 数据流向——交付前必须与客户确认

| 会发送到 LLM 端点的内容 | 不会发送的内容 |
|---|---|
| 用户提问 | 整库文档 |
| 检索命中的制度原文片段 | 向量库 / BM25 索引 |
| 最近几轮对话历史 | 用户凭证、数据库口令 |

**因此：若客户制度含薪酬、人事、涉密内容，或客户有"数据不得出内网"的硬性要求，
必须改用客户内网的私有模型。** 默认配置指向公网 API，不满足该要求——这一点在
售前不要含糊，否则会在安全评审阶段被推翻。

### 换模型（不需要改代码）

任何 OpenAI 兼容端点均可，改 `.env` 三行：

```
LLM_BASE_URL=http://10.0.0.21:8000/v1    # 结尾带不带 /v1 都兼容
LLM_API_KEY=EMPTY                        # 私有端点通常任意非空值
LLM_MODEL=qwen2.5-7b-instruct
```

历史变量名 `DEEPSEEK_*` 仍兼容；两者同时存在时以 `LLM_*` 优先。

### 换模型后必须做能力探测

```bash
python deploy/check-llm.py
```

| 探测项 | 不支持时的后果 |
|---|---|
| 基础对话 | 完全不可用 |
| 流式输出 | 聊天页变成长时间空白后一次性弹出 |
| 工具调用 | Agent 模式失败 → 需设 `ENABLE_AGENT_MODE=false`（制度问答主链路不受影响） |

`install.sh` 在安装末尾也会自动探测一次端点可达性，并在末尾汇总提示。若出现
LLM `[WARN]`，最常见原因是 **API Key 仍是占位值** 或 **内网连不上公网服务**。

---



**P0-3 补充说明**：后端镜像默认只装精简依赖。文档解析、切片、向量化、检索全部
在 Java 引擎内完成，因此 `langchain` / `pypdf` / `python-docx` / `rank-bm25` /
`chromadb` / `sentence-transformers` 均已从主依赖移除。若客户场景是「不部署 Java
引擎、单进程运行」，在 `.env` 中设 `INSTALL_FALLBACK=true` 后重新构建即可恢复
本地 ChromaDB 降级检索（需另行准备本地 embedding 模型）。

改完依赖请运行 `python deploy/verify-deps.py`：它会校验「代码 import 的包」与
「requirements 声明的包」是否一致，既防止漏装导致容器启动即崩，也防止重新引入
死依赖把交付包撑大。

---

## 八、授权交付流程（P0-6）

产品采用**离线签名授权**：厂商持私钥签发，产品内置公钥校验，全程不联网、不回连。

### 交付四步

1. **客户读出机器指纹**（在部署机器上执行）：
   ```bash
   python deploy/license/machine_fingerprint.py
   ```
   Docker 部署下也可直接看 `install.sh` 结束时输出的"本机机器指纹"。
2. **厂商签发**（私钥只在厂商侧，不随产品交付）：
   ```bash
   python deploy/license/issue-license.py \
     --customer "某某集团有限公司" --days 365 \
     --fingerprint <客户提供的指纹> --max-documents 5000 \
     --out license.json
   ```
3. **交付授权文件**：把 `license.json` 放到部署目录（与 `docker-compose.yml` 同级）。
   该文件已由 compose 只读挂入容器；随后 `docker compose restart backend` 生效。
4. **客户自查**：`GET /api/license` 查看授权状态、客户名、到期时间与剩余天数。

### 授权失效时的行为（刻意做成"可恢复"）

| 会被限制 | 仍然可用 |
|---|---|
| 问答与 Agent（`/api/chat`、`/api/agent`） | 登录、管理台全部页面 |
| 文档入库与重建索引（`/api/knowledge` 的写操作） | 所有 GET：文档、切片、对话记录、审计日志（**数据始终可查看与导出**） |

这样客户过期后仍能自查与备份数据、供应商也能远程支持，避免把矛盾激化到无法协商。

### 密钥管理与注意事项

- 私钥在 `deploy/license/keys/private.pem`，**已加入 .gitignore，切勿随产品交付或提交**；
  泄露即等于任何人都能签发授权。
- **正式销售前请重新生成密钥对**：运行 `deploy/license/gen-keypair.py`，把打印出的公钥
  替换到 `backend/services/license_service.py` 的 `PRODUCT_PUBLIC_KEY_PEM`。
  仓库当前内置的是开发用密钥，且已签发一份不绑定机器的开发授权（`license.json`，已 gitignore）。
- 机器绑定依赖宿主机 `/etc/machine-id`：`install.sh` 会自动写入 `LICENSE_MACHINE_ID`，
  使容器重建后授权不失效。换机或系统重装导致标识变化时需重新签发。
- 授权校验有 60 秒缓存；换授权文件后 `docker compose restart backend`，
  或调用 `POST /api/license/reload` 立即生效。
- 容量上限（`--max-documents` 等）目前**只上报不强制**；需要强制时应在入库前接入计数校验。

### 能力边界（不要当成 DRM）

产品以源码形式交付到客户内网，任何纯离线校验都能被有决心的客户通过改代码绕过。
它的作用是阻止"一份授权随手复制到多套环境"这类常规越界；真正需要强管控时，
应配合合同条款与交付流程。自带的验证脚本：`python deploy/license/test-license.py`（21 项）。

---

完整路线见 [docs/solution-policy-assistant.md](../../docs/solution-policy-assistant.md)。
