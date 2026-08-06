# ✴MyNexus - A private knowledge base for your books.

一个私有化的书籍知识库化系统，目标是将您的电子书内容转化为可检索、可问答、可扩展的知识资产。

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
