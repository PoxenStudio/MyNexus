# MyNexus 待办事项

记录当前未完成的开发工作，以及实现与设计文档（`需求文档.md` / `系统设计文档.md`）之间的已知差异。M1–M4 四个里程碑均已完成并通过各自验收标准，以下事项均不阻塞里程碑验收，留待后续按需处理。

## 设计文档与实现的差异（需评估是否需要修正文档或补齐实现）

- [x] **`storage.database: postgres` 已实现**（2026-08-05）。新增 `core-api/internal/storage/postgres`：`postgres.Store` 实现与 `sqlite.Store` 相同的 `storage.Database` 接口（新增 `DB() *sql.DB` 方法），底层用 `github.com/jackc/pgx/v5/stdlib`（纯 Go，无需 CGO）。业务层 SQL 仍以 SQLite 风格 `?` 占位符编写，Postgres 侧通过自定义驱动包装层（`qmarkDriver`，改写 `?` → `$1,$2,...`）透明转换，无需为两个后端各写一套查询。独立维护一份 `storage/postgres/migrations/0001_init.sql`（与 sqlite 版本字段一致，仅 `DATETIME`→`TIMESTAMP`）。`main.go` 按 `storage.database` 配置选择后端；`docker-compose.yml` 新增可选 `postgres` service（`--profile postgres` 启用）与 `STORAGE_DATABASE`/`MYNEXUS_STORAGE_POSTGRES_DSN` 环境变量，可在不改代码的情况下切换。详见 README.md「后端数据库选择」。
- [ ] **`auth.jwt_secret` 配置字段仍是死代码**。管理后台登录（见下一条）最终选用了 Cookie/Session 方案，而非 JWT——与 MyBooks 自身的鉴权方式保持一致（[[mynexus_m2_decisions]]）——所以 `jwt_secret` 依旧没有被消费。建议后续清理该字段，除非明确要新增 JWT 鉴权用途。
- [x] **管理后台鉴权已强制**（2026-08-05）。新增基于 Cookie/Session 的管理员登录：默认账号 `admin/admin`（首次启动自动播种，见 `AdminUserService.EnsureDefaultAdmin`），登录后台修改密码功能（`POST /api/v1/auth/change-password`）。`middleware.RequireAuth` 替换了原先"有 Token 才校验"的 `APITokenAuth`：现在 `/api/v1` 下除 `/auth/login`、`/auth/logout` 外的所有路由都要求「有效 Session 或有效 API Token」二选一——浏览器走 Session（管理员登录后台），自动化/第三方集成走 Token（Tokens 管理页不变）。详见 `mynexus_admin_auth` memory。
- [ ] **后端错误文案未做 i18n**。系统设计文档 §9.2 提出的"Accept-Language 驱动的后端错误文案"未实现，目前 Core API 报错为原始英文/中英混杂文本，仅前端 web-ui 做了完整 i18n。
- [x] **Core API ↔ Worker 通信已从 HTTP 迁移为 gRPC**（2026-08-05）。新增 `proto/mynexus.proto` 作为唯一契约来源，Go（`core-api/internal/grpcapi/mynexuspb`）与 Python（`worker/src/mynexus_pb2*.py`）两侧代码均由此生成（生成产物已提交，不需要 Docker 镜像里装 protoc）。`WorkerService`（Worker 实现：`TriggerIngest`/`Search`/`Chat` 流式）与 `CoreApiService`（Core API 实现：`ReportProgress`/`ReportComplete`/`ReportFail`/`KeywordSearch`）两个双向 service 替换了原来的全部 `/internal/*` HTTP 端点；浏览器 ↔ Core API 仍是普通 HTTP/SSE，未受影响。Core API 新增独立 gRPC 监听端口（`server.grpc_port`，默认 9090），与原有 8080 HTTP 端口并存。Worker 侧移除了 FastAPI/uvicorn 依赖。已完整跑通端到端验证（登录→上传书籍→gRPC 触发解析→gRPC 逐步上报进度→gRPC 报告完成→书籍状态变为 ready；混合检索 RPC；问答流式 RPC 通过 SSE 正确转发到浏览器），过程中用 mock OpenAI server 让 embedding/LLM 调用可控。详见 `mynexus_grpc_migration` memory。

- [x] **数据库连接建立时自动检查表结构并创建/升级**（2026-08-05）。新增 `core-api/internal/storage/migrator.go`：连接建立后自动创建 `schema_migrations` 表记录已应用的迁移文件名，仅执行尚未应用过的迁移文件（按文件名排序，逐条语句在事务内执行），而不是像之前那样每次启动都重跑全部迁移文件的完整内容。sqlite、postgres 两个后端共用同一套逻辑。此前"改字段直接编辑 0001_init.sql"的做法（见 [[mynexus_m4_decisions]]）已被取代：以后新的表结构变更（包括含 `ALTER TABLE` 的变更）应新增编号迁移文件（如 `0002_xxx.sql`），两个后端各建一份并保持字段一致。已用本地 SQLite 文件验证：首次启动会创建并记录 `0001_init.sql`，二次启动确认被跳过（记录时间戳不变）。详见 memory 中的 `mynexus_migration_versioning`。

## 功能缺口

- [x] **书籍重建接口已实现**（2026-08-05）——见下一条"批量书籍操作"，`POST /books/{id}/rebuild` 是与批量重建一起实现的。
- [x] **任务分阶段日志已完善**（2026-08-05）。此前 `TaskProgressCallback` 早就带了 `stage`/`message` 字段，但 `TaskService.UpdateProgress` 直接丢弃、从不写入 `stages_log`。现在 `task_service.go` 的 `transition()`/`appendStageLog()` 在每次 progress/complete/fail/retry 时都会向 `stages_log`（JSON 数组）追加一条 `{stage, message, progress, at}` 记录，而不是覆盖。`TaskResponse` DTO 新增 `stages_log` 字段（解析后返回结构化数组），任务列表页支持点击一行展开查看完整阶段时间线。用 sqlite3 直接写入测试任务并调用 `/internal/tasks/{id}/progress`、`/fail` 验证过追加逻辑正确、时间线完整。
- [x] **批量书籍操作已实现**（2026-08-05）。同时补齐了单本重建能力（此前"书籍重建接口缺失"的前提工作）：`POST /books/{id}/rebuild` 对任意书籍（不限于失败任务）重新触发解析/分块/向量化，创建全新任务而非复用旧任务；`POST /books/bulk-delete`、`POST /books/bulk-rebuild`（body `{ids: []}`）批量处理，每个 id 独立执行、互不阻塞，返回逐项成功/失败结果（`{items: [{id, ok, error?}]}`）。web-ui 书籍列表页新增复选框、全选、批量删除/批量重建按钮，失败项汇总展示。所有批量/单本重建操作都写入审计日志（`book.delete`/`book.rebuild`/`book.bulk_delete`/`book.bulk_rebuild`）。已用 curl（含无 Worker 运行、部分书籍无文件等失败场景）和真实 Vite 代理路径验证过。
- [x] **管理员操作审计日志已实现**（2026-08-05）。新增 `admin_audit_log` 表（新迁移 `0003_admin_audit_log.sql`，sqlite/postgres 各一份）、`AuditService`（记录 + 分页查询）、`GET /api/v1/audit-log`，以及 web-ui 的「审计日志」页面。记录范围：登录成功/失败、改密码、书籍删除、任务重试、Token 创建/吊销。操作者字段区分「管理员用户名」（Session 登录）与「token:别名」（API Token 访问），复用了鉴权中间件里已经解析出的身份信息，不需要额外查库。已用 curl 端到端验证过完整记录链路。
- [x] **终端用户问答/聊天页面已实现**（2026-08-05）。新增 `web-ui/src/views/ChatView.vue`（会话列表 + 消息串 + SSE 流式回答），复用已有的 `/chat/completions`（SSE）与 `/chat/sessions*` API。新增配置项 `chat.enabled`（默认 `true`，环境变量 `MYNEXUS_CHAT_ENABLED`）控制该功能整体开关：关闭时后端 `/api/v1/chat/*` 返回 403（`middleware.RequireChatEnabled`），前端隐藏导航项且路由守卫直接跳转回仪表盘。该页面位于管理后台内部，与其它页面一样需要登录后才能访问（不是独立的匿名对外页面）。详见 `mynexus_admin_auth` memory。
- [ ] **上传文件病毒/合法性扫描缺失**：需求文档 §6.6 中标注为可选项，目前未实现。

## 已知的可扩展性限制

- [x] **混合检索的 BM25 关键词侧扩展性问题已解决（仅 Postgres 后端）**（2026-08-05）。`chunks` 表新增 `content_tsv tsvector` 生成列 + GIN 索引（`storage/postgres/migrations/0004_chunk_keyword_search.sql`，Postgres 自动维护，Core API 写入路径不用改代码），新增只读接口 `CoreApiService.KeywordSearch`（最初实现为 HTTP `POST /internal/search/keyword`，同日晚些时候随全面 gRPC 迁移改为 gRPC RPC，仅 postgres 后端可用，sqlite 返回 `NOT_FOUND`），`worker/src/pipelines/retrieval.py` 的 `RetrievalPipeline` 在 `storage.database == postgres` 时改为调用该接口（失败自动回退到原 BM25 逻辑），sqlite 后端行为不变（定位为小规模验证/试用场景，不做这个优化）。**明确决定：这次只给 Worker 加了只读查询能力，没有让 Worker 直连数据库写库**——"Worker 只算、Core API 统一持久化"这条架构原则的核心理由是避免同一套写入逻辑在 Go/Python 两边维护两份，这个理由与数据库并发能力无关，Postgres 解决不了"两套代码要保持同步"的问题，所以即使 Postgres 并发写入能力更强，也没有让 Worker 绕过 Core API 直接写 `chapters`/`chunks`/`tasks`。受限于本机没有可用的 Postgres/Docker 环境，未做真实 GIN 索引查询的端到端验证。详见 `mynexus_keyword_search_gin` memory 与系统设计文档 §3.4。
- [ ] **分块/Token 计数为字符数近似**，非真实分词器（无 tiktoken 依赖），对中文场景影响较小，对英文文本会高估 token 数量。
- [ ] **BM25 的中文分词为简单正则**（每个汉字视为一个 token），未引入 jieba 等真实分词器。

---

维护说明：完成某项后请勾选对应复选框并简要注明处理方式/commit，而不是直接删除条目，便于追溯决策历史。
