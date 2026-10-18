---
name: "mynexus"
description: "通过 CLI 调用 MyNexus 私有书库的 HTTP API，完成书籍管理与会话/检索问答。当用户要查询、导入、重建、总结、删除 MyNexus 书籍，或对书库内容提问、检索原文时调用。"
---

# MyNexus 书库调用

用 `scripts/mynexus.py` 操作 MyNexus（core-api）的 HTTP 接口。**仅覆盖书籍管理与会话/检索问答**；系统设置修改、用户管理、Token 管理、审计日志不在本 Skill 范围内，遇到这类需求直接说明不支持。

## 前置配置

| 环境变量 | 必填 | 说明 |
|---------|------|------|
| `MYNEXUS_API_TOKEN` | 是 | API Token（后台「API Token」页面创建，`mnx_` 前缀；或服务端配置的全局 `MYNEXUS_API_TOKEN`） |
| `MYNEXUS_BASE_URL` | 否 | core-api 地址，默认 `http://localhost:8080`；Docker 部署经 nginx 访问时用 `http://localhost:3000` |
| `MYNEXUS_MYBOOKS_USER_ID` | 否 | 以外部 MyBooks 用户身份访问会话接口，对应请求头 `X-MyBooks-User-ID` |

也可用 `--base-url` / `--token` / `--mybooks-user-id` 逐个覆盖。所有命令输出 JSON 到 stdout，调试日志在 stderr；加 `--quiet` 只保留结果。

## 命令速查

```bash
python3 scripts/mynexus.py health                     # 服务存活检查
python3 scripts/mynexus.py books list --q 关键词 --size 50
python3 scripts/mynexus.py books get <book_id>        # 详情含章节摘要/关键词/术语
python3 scripts/mynexus.py books get <book_id> --no-chapters
python3 scripts/mynexus.py books chunks <book_id> --chapter-id <id>
python3 scripts/mynexus.py books tokens <book_id>     # 该书 LLM token 用量
python3 scripts/mynexus.py books cover <book_id> --out cover.jpg
python3 scripts/mynexus.py search --query "查询内容" --book-ids id1,id2 --top-k 10
python3 scripts/mynexus.py chat --message "这本书讲了什么？" --book-ids id1
python3 scripts/mynexus.py chat --message "继续追问" --session-id <session_id>
python3 scripts/mynexus.py sessions list
python3 scripts/mynexus.py sessions get <session_id>
python3 scripts/mynexus.py tasks list --book-id <book_id>
python3 scripts/mynexus.py tasks get <task_id>
```

写操作（会改变书库数据）：

```bash
python3 scripts/mynexus.py books import ./book.epub [--mybooks-id 123 --cover-url http://...]
python3 scripts/mynexus.py books update <book_id> --title "新标题" --tags a,b
python3 scripts/mynexus.py books summary <book_id> --text "手工修订后的全书总结"
python3 scripts/mynexus.py books summarize <book_id> [--mode continue]
python3 scripts/mynexus.py books rebuild <book_id>
python3 scripts/mynexus.py books delete <book_id> --yes
python3 scripts/mynexus.py books bulk-delete <id1> <id2> --yes
python3 scripts/mynexus.py books bulk-rebuild <id1> <id2>
python3 scripts/mynexus.py sessions rename <session_id> --title "新标题"
python3 scripts/mynexus.py sessions delete <session_id> --yes
python3 scripts/mynexus.py tasks retry <task_id>
python3 scripts/mynexus.py tasks cancel <task_id>
```

## 使用要点

- **问答链路**：`chat` 会消费 SSE 流并聚合，返回 `session_id` / `answer` / `citations` / `tool_results`。回答里的 `[n]` 角标与 `citations` 数组按顺序对应，引用中带 `book_id`、`chapter_id`、`content`，需要溯源时直接读 citations，不要臆造出处。
- **会话续问**：新建会话时首次回答会返回 `session_id`，后续追问把它传给 `--session-id` 即可延续上下文；历史由服务端按会话组装，只需发送本轮问题。
- **检索 vs 问答**：要定位原文片段用 `search`（返回 chunk 与分数）；要成段解释、归纳用 `chat`。
- **异步任务**：`import` / `rebuild` / `summarize` 只返回 `task_id`，处理是异步的。查进度用 `tasks get <task_id>`（`progress`、`status`、`stages_log`），或 `tasks list --book-id <book_id>` 看最新任务；书籍就绪状态是「向量化 + 章节总结 + 全书总结」全部完成后才出现。
- **状态字段**：书 `status` 取值 `pending` / `processing` / `ready` / `failed`；任务 `status` 另有 `canceled`。`dispatched=false` 的 pending 导入任务表示在队列里等并发槽位，不是失败。
- **失败排查**：`tasks get` 的 `error_msg` 是 worker 生成的中文业务提示（LLM 连接失败、模型不可用、无章节可总结等），优先按该文案判断，不要自行改写成通用错误。

## 边界与风险

- 不触碰 `/system/*`、`/users/*`、`/tokens/*`、`/audit-log`，也不使用导出专用端点。
- `books delete` / `bulk-delete` 是不可逆的数据删除（同时清理向量与封面），必须显式 `--yes`，且应先向用户确认目标书籍。
- `rebuild` 会重新解析并重建向量；当前实现会清掉该书已生成的章节摘要向量，重跑前提醒用户后续需要重新总结。
- 会话接口按用户隔离：`sessions` 只能看到 Token 所属用户的会话；以外部身份访问需显式传 `--mybooks-user-id`。
- 会话功能可能被服务端关闭（`chat.enabled=false`），此时 `/chat/*` 返回 403，改用 `search`。
