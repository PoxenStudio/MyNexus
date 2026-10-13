# ✴MyNexus - A private knowledge base for your books.

一个私有化的书籍知识库化系统，目标是将您的电子书内容转化为可检索、可问答、可扩展的知识资产。

![Main UI](docs/mainui.png)

书籍的总结

![Book](docs/book_header.jpg)

章节的总结

![Chapters](docs/book_detail.jpg)

## 项目简介

MyNexus 将 EPUB / PDF / TXT 电子书导入后，自动完成解析、清洗、分块、向量化，构建可检索、可问答（RAG）的书籍知识库，并配套一个管理后台用于查看书籍、任务处理状态与 API Token 管理，服务于 MyBooks/MyReader 生态。

系统由三个服务组成（monorepo）：

- **core-api**（Go + Gin）：唯一持有业务数据的服务，所有元数据（书籍、章节、任务、对话、Token）存储于关系型数据库，默认 SQLite（`modernc.org/sqlite`，纯 Go 驱动，便于 NAS 多架构构建，无需 CGO），也可切换为 Postgres（详见下文「后端数据库选择」）。
- **worker**（Python + FastAPI）：无状态的能力节点层，负责解析 / 清洗 / 分块 / 向量化 / 检索 / LLM 问答，通过 HTTP 回调向 core-api 汇报任务进度与结果。向量存储默认使用 ChromaDB（HNSW 索引，适合大规模书库），也可切换为轻量的本地 numpy + JSON 方案。
- **web-ui**（Vue 3 + TypeScript + Vite）：管理后台前端，包含仪表盘、书籍管理、任务监控、Token 管理、会话（问答）页面，支持中文简体/繁体与英文界面。

详细需求、系统设计与开发计划见 `docs/` 目录：`需求文档.md`、`系统设计文档.md`、`开发技术文档.md`。

## 登录与访问控制

管理后台需要登录才能访问。首次启动会自动创建默认管理员账号 **用户名 `admin` / 密码 `admin`**（`AdminUserService.EnsureDefaultAdmin`，仅在 `admin_users` 表为空时播种一次），**首次登录后请立即在「设置」页面修改密码**。管理员登录使用 Cookie/Session（与 MyBooks 自身的鉴权方式一致，非 JWT），会话有效期 24 小时，服务重启后需要重新登录。

其它服务/自动化脚本访问 Core API 走 API Token 方式（后台「API Token」页面创建/查看/吊销），与管理员登录是两条独立、可并存的鉴权路径：受保护的接口在「有效 Session」或「有效 Token」任一满足时即可访问。

会话（问答）页面可通过 `chat.enabled` 配置项整体开关（默认开启，环境变量 `MYNEXUS_CHAT_ENABLED`）：关闭后 `/api/v1/chat/*` 接口返回 403，前端也会隐藏该导航项。该页面位于登录后的管理后台内，不是独立的匿名对外页面。

## 后端数据库选择

`config/config.yaml` 的 `storage.database` 字段支持 `sqlite`（默认）与 `postgres` 两种后端，可在部署时二选一。

- **SQLite**（默认）：`modernc.org/sqlite`，纯 Go 驱动，无需 CGO。单文件、零运维，适合 NAS/单实例私有化部署——不需要独立数据库服务，数据库文件（`storage.sqlite.path`，默认 `./data/mynexus.db`）随 `./data` 卷一起挂载/备份即可。
- **Postgres**：适合需要更强并发写入性能、或未来多实例部署的场景。连接串通过 `storage.postgres.dsn` 配置（如 `postgres://mynexus:mynexus@postgres:5432/mynexus?sslmode=disable`）。底层使用 `github.com/jackc/pgx/v5/stdlib`（纯 Go 驱动，同样无需 CGO，交叉编译不受影响）。

两个后端共享同一套 SQL 语句（`internal/service/*.go` 里以 SQLite 风格的 `?` 占位符编写），Postgres 一侧通过一个轻量的驱动包装层（`storage/postgres` 内的 `qmarkDriver`）在发给数据库前自动把 `?` 改写为 `$1, $2, ...`，因此业务代码完全不感知具体后端；两个后端各自维护一份 schema 迁移（`storage/{sqlite,postgres}/migrations/0001_init.sql`），字段保持一致，仅 `DATETIME`/`TIMESTAMP` 等类型名因数据库而异。

切换方式：

```bash
# 方式 A：直接改 config/config.yaml
storage:
  database: postgres
  postgres:
    dsn: "postgres://mynexus:mynexus@localhost:5432/mynexus?sslmode=disable"

# 方式 B：环境变量（Docker Compose 默认走这条路，见下）
export MYNEXUS_STORAGE_DATABASE=postgres
export MYNEXUS_STORAGE_POSTGRES_DSN="postgres://mynexus:mynexus@postgres:5432/mynexus?sslmode=disable"
```

## 部署方式

### 方式一：Docker Compose（推荐，生产/NAS 部署）

```bash
# 1. 按需修改 config/config.yaml（数据库路径、向量库、LLM/Embedding 提供方等）

# 2. 设置必要的环境变量（可选，也可直接写入 config.yaml）
export OPENAI_API_KEY=sk-xxx
export JWT_SECRET=your-secret

# 3. 启动全部服务（默认 SQLite 后端）
docker compose up -d --build

# 若要改用 Postgres 后端：额外启用 postgres profile 并设置 STORAGE_DATABASE
STORAGE_DATABASE=postgres docker compose --profile postgres up -d --build
```

服务启动后：

- Web 管理后台：http://localhost:3000
- Core API：http://localhost:8080
- Worker（内部服务，gRPC 端口 8001，一般无需直接访问，也无法用浏览器/curl 直接访问）：`localhost:8001`

数据与配置通过卷挂载持久化在宿主机的 `./data` 与 `./config` 目录下。Worker 容器内存上限为 1536M（ChromaDB 的实际需求，适配 4GB+ 内存的 NAS 环境）。Core API 与 Worker 之间的内部通信为 gRPC（见系统设计文档 §1.3），浏览器与 Core API 之间仍是普通 HTTP/SSE，不受影响。

### 方式二：本地开发（Makefile）

无需 Docker，直接在本机以三个独立进程启动，适合开发调试：

```bash
# 启动 core-api / worker / web-ui（前后台运行，日志输出到 .tmp/*.log）
make dev-up

# 停止所有服务
make dev-down
```

依赖前提：

- Go（core-api 使用 `go run` 直接启动）
- Python 3 及 `worker/` 下的依赖（建议使用虚拟环境安装 `worker/requirements.txt`）
- Node.js（`web-ui` 使用 `npm run dev` 启动 Vite 开发服务器）

默认配置从 `config/config.yaml` 读取，SQLite 数据库位于 `data/mynexus.db`。

### 单独运行 Worker 处理节点（调试用）

Worker 的每个处理节点（解析器、清洗器、分块器、向量化器、LLM 调用等）都支持独立在命令行运行，便于单元测试和问题排查，例如：

```bash
cd worker
python3 -m src.nodes.parsers.epub_parser /path/to/book.epub
python3 -m src.nodes.splitters.token_splitter --input chapter.txt
```

具体参数见各模块内的 `argparse` 定义。

## 关键词提取维护（TF-IDF / POS 过滤 / 停用词）

书籍/章节关键词由 `worker/src/util/keywords.py` 从章节原始正文（非 LLM 摘要）提取，中英文各走一条独立路径：

- **中文**：`jieba.analyse` TF-IDF，仅保留名词类 POS（`_ZH_ALLOW_POS`：`n`/`ns`/`nz`/`nt`/`nr`/`vn` 及未译英文词 `eng`），再叠加一份手工维护的通用名词停用词表 `_ZH_STOPWORDS`（如"受试者""结果""人们""方法"等跨书通用、无主题区分度的词）。
- **英文**：POS 过滤仅保留 NLTK 标注的名词（`NN`/`NNS`/`NNP`/`NNPS`），词频计数排序，并叠加停用词表 `_EN_STOPWORDS` 兜底 POS 过滤漏掉的虚词/代词。

若发现关键词列表里混入了新的"放之四海皆通用"的词，直接把该词加进 `_ZH_STOPWORDS`（或 `_EN_STOPWORDS`）即可，无需改动抽取逻辑；反之若某个领域词被误杀，从表中删掉。这份表刻意偏保守——只收跨领域都通用的词，不收某一类书里恰好常见的领域词（例如"患者"对医学类书籍是合理关键词，不放入表中）。

除静态停用词表外，书级关键词聚合（`pipelines/summary.py` 里章节→全书的 reduce 步骤）还会做一次自适应过滤：`merge_topk` 的 `doc_freq` 参数统计每个词出现在多少章节里，`filter_by_doc_frequency` 剔除出现章节占比超过阈值（默认 60%，章节数 <4 时跳过）的词——这类词是"这本书"通用的全书背景词，即使不在静态表里也会被过滤掉，不需要为每本书单独维护词表。

**何时生效**：书级关键词每次运行"总结全书"任务都会用当前代码重新计算（不依赖上次运行的缓存），所以改完停用词表后对已入库的书重新触发一次总结即可生效；章节级关键词只在该章节被重新生成时（强制重跑 `force_restart=True`，或该章节尚无摘要）才会重算，普通"续跑"不会触碰已总结章节的关键词。
