# MyNexus 待办事项

记录当前未完成的开发工作，以及实现与设计文档（`需求文档.md` / `系统设计文档.md`）之间的已知差异。M1–M4 四个里程碑均已完成并通过各自验收标准，以下事项均不阻塞里程碑验收，留待后续按需处理。

## 设计文档与实现的差异（需评估是否需要修正文档或补齐实现）

- [x] **`storage.database: postgres` 已实现**（2026-08-05）。新增 `core-api/internal/storage/postgres`：`postgres.Store` 实现与 `sqlite.Store` 相同的 `storage.Database` 接口（新增 `DB() *sql.DB` 方法），底层用 `github.com/jackc/pgx/v5/stdlib`（纯 Go，无需 CGO）。业务层 SQL 仍以 SQLite 风格 `?` 占位符编写，Postgres 侧通过自定义驱动包装层（`qmarkDriver`，改写 `?` → `$1,$2,...`）透明转换，无需为两个后端各写一套查询。独立维护一份 `storage/postgres/migrations/0001_init.sql`（与 sqlite 版本字段一致，仅 `DATETIME`→`TIMESTAMP`）。`main.go` 按 `storage.database` 配置选择后端；`docker-compose.yml` 新增可选 `postgres` service（`--profile postgres` 启用）与 `STORAGE_DATABASE`/`MYNEXUS_STORAGE_POSTGRES_DSN` 环境变量，可在不改代码的情况下切换。详见 README.md「后端数据库选择」。
- [ ] **`auth.jwt_secret` 配置字段仍是死代码**。管理后台登录（见下一条）最终选用了 Cookie/Session 方案，而非 JWT——与 MyBooks 自身的鉴权方式保持一致（[[mynexus_m2_decisions]]）——所以 `jwt_secret` 依旧没有被消费。建议后续清理该字段，除非明确要新增 JWT 鉴权用途。
- [x] **管理后台鉴权已强制**（2026-08-05）。新增基于 Cookie/Session 的管理员登录：默认账号 `admin/admin`（首次启动自动播种，见 `AdminUserService.EnsureDefaultAdmin`），登录后台修改密码功能（`POST /api/v1/auth/change-password`）。`middleware.RequireAuth` 替换了原先"有 Token 才校验"的 `APITokenAuth`：现在 `/api/v1` 下除 `/auth/login`、`/auth/logout` 外的所有路由都要求「有效 Session 或有效 API Token」二选一——浏览器走 Session（管理员登录后台），自动化/第三方集成走 Token（Tokens 管理页不变）。详见 `mynexus_admin_auth` memory。
- [ ] **后端错误文案未做 i18n**。系统设计文档 §9.2 提出的"Accept-Language 驱动的后端错误文案"未实现，目前 Core API 报错为原始英文/中英混杂文本，仅前端 web-ui 做了完整 i18n。

- [x] **数据库连接建立时自动检查表结构并创建/升级**（2026-08-05）。新增 `core-api/internal/storage/migrator.go`：连接建立后自动创建 `schema_migrations` 表记录已应用的迁移文件名，仅执行尚未应用过的迁移文件（按文件名排序，逐条语句在事务内执行），而不是像之前那样每次启动都重跑全部迁移文件的完整内容。sqlite、postgres 两个后端共用同一套逻辑。此前"改字段直接编辑 0001_init.sql"的做法（见 [[mynexus_m4_decisions]]）已被取代：以后新的表结构变更（包括含 `ALTER TABLE` 的变更）应新增编号迁移文件（如 `0002_xxx.sql`），两个后端各建一份并保持字段一致。已用本地 SQLite 文件验证：首次启动会创建并记录 `0001_init.sql`，二次启动确认被跳过（记录时间戳不变）。详见 memory 中的 `mynexus_migration_versioning`。

## 功能缺口

- [ ] **书籍重建接口缺失**：`POST /books/{id}/rebuild`（对已成功处理的书籍强制重新解析/分块/向量化，例如更换 embedding 模型后）尚未实现，目前只有失败任务重试（`POST /tasks/{id}/retry`，仅重新触发原文件的 ingest）。
- [ ] **任务分阶段日志未落地**：`tasks.stages_log` 字段已建表但从未写入真实内容（始终为空数组 `[]`），任务页目前只能看到 `error_msg`，缺少结构化的分阶段处理日志。
- [ ] **批量书籍操作缺失**：需求文档 §6.7.3 要求的多选删除/批量重建，web-ui 目前只支持单本操作。
- [ ] **管理员操作审计日志缺失**：需求文档 §6.7.3 的"操作审计记录"未实现，没有表或日志记录管理员的操作历史。
- [x] **终端用户问答/聊天页面已实现**（2026-08-05）。新增 `web-ui/src/views/ChatView.vue`（会话列表 + 消息串 + SSE 流式回答），复用已有的 `/chat/completions`（SSE）与 `/chat/sessions*` API。新增配置项 `chat.enabled`（默认 `true`，环境变量 `MYNEXUS_CHAT_ENABLED`）控制该功能整体开关：关闭时后端 `/api/v1/chat/*` 返回 403（`middleware.RequireChatEnabled`），前端隐藏导航项且路由守卫直接跳转回仪表盘。该页面位于管理后台内部，与其它页面一样需要登录后才能访问（不是独立的匿名对外页面）。详见 `mynexus_admin_auth` memory。
- [ ] **上传文件病毒/合法性扫描缺失**：需求文档 §6.6 中标注为可选项，目前未实现。

## 已知的可扩展性限制

- [ ] **混合检索的 BM25 关键词侧不具备大规模扩展性**：每次查询都会重新加载全量候选集并重建 `rank_bm25` 索引；向量检索侧已通过切换到 ChromaDB（HNSW 索引）解决了同类问题，但关键词侧尚未处理，预计在数万本书规模下会成为新的性能瓶颈。可考虑引入 Core API 侧的 SQLite FTS5 或等效方案。
- [ ] **分块/Token 计数为字符数近似**，非真实分词器（无 tiktoken 依赖），对中文场景影响较小，对英文文本会高估 token 数量。
- [ ] **BM25 的中文分词为简单正则**（每个汉字视为一个 token），未引入 jieba 等真实分词器。

---

维护说明：完成某项后请勾选对应复选框并简要注明处理方式/commit，而不是直接删除条目，便于追溯决策历史。
