#!/usr/bin/env python3
"""MyNexus 书库 CLI：供 agent 通过 HTTP API 操作书籍与查询会话/检索。"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = "http://localhost:8080"
DEFAULT_TIMEOUT = 60.0
_QUIET = False


def log(message):
    if not _QUIET:
        print("[mynexus] " + message, file=sys.stderr, flush=True)


class ApiError(Exception):
    def __init__(self, message, status=None, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


def resolve_base_url(args):
    url = args.base_url or os.environ.get("MYNEXUS_BASE_URL") or os.environ.get("MYNEXUS_API_URL") or DEFAULT_BASE_URL
    return url.rstrip("/")


def resolve_token(args):
    return args.token or os.environ.get("MYNEXUS_API_TOKEN") or os.environ.get("MYNEXUS_TOKEN") or os.environ.get("MNX_TOKEN") or ""


def build_headers(args):
    headers = {"Accept": "application/json"}
    token = resolve_token(args)
    if token:
        headers["Authorization"] = "Bearer " + token
    else:
        log("未提供 API Token，受保护接口将返回 401")
    if args.mybooks_user_id:
        headers["X-MyBooks-User-ID"] = str(args.mybooks_user_id)
    return headers


def encode_body(body):
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def http_call(args, method, path, params=None, body=None, raw=False, extra_headers=None):
    base_url = resolve_base_url(args)
    url = base_url + path
    if params:
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        if clean:
            url = url + "?" + urllib.parse.urlencode(clean)
    headers = build_headers(args)
    data = encode_body(body) if body is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    log("请求 %s %s" % (method, url))
    started = time.time()
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            payload = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        log("响应 %s %s（耗时 %.0fms）" % (method, exc.code, (time.time() - started) * 1000))
        detail = payload.decode("utf-8", "replace")
        try:
            parsed = json.loads(detail)
            message = parsed.get("error") or parsed.get("message") or detail
        except (ValueError, AttributeError):
            parsed = None
            message = detail
        if exc.code == 401:
            message = "%s（请检查 MYNEXUS_API_TOKEN 是否有效）" % message
        raise ApiError("HTTP %s: %s" % (exc.code, message), exc.code, parsed)
    except urllib.error.URLError as exc:
        log("连接失败 %s %s: %s" % (method, url, exc.reason))
        raise ApiError("无法连接 %s：%s（可用 --base-url 指定地址）" % (base_url, exc.reason))

    log("响应 %s %s（%d 字节，耗时 %.0fms）" % (method, status, len(payload), (time.time() - started) * 1000))
    if status >= 400:
        raise ApiError("HTTP %s: %s" % (status, payload.decode("utf-8", "replace")), status)
    if raw:
        return status, payload
    if not payload:
        return status, None
    return status, json.loads(payload.decode("utf-8"))


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def require_confirm(args, action, target):
    if not args.yes:
        raise ApiError("破坏性操作 %s（%s）需要显式确认，请加 --yes" % (action, target))


def parse_csv(value):
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def cmd_health(args):
    status, payload = http_call(args, "GET", "/healthz")
    emit({"status": status, "body": payload})


def cmd_books_list(args):
    _, payload = http_call(args, "GET", "/api/v1/books", {
        "page": args.page, "size": args.size, "status": args.status, "q": args.q,
    })
    emit(payload)


def cmd_books_get(args):
    _, payload = http_call(args, "GET", "/api/v1/books/" + urllib.parse.quote(args.book_id))
    if args.no_chapters and isinstance(payload, dict):
        payload.pop("chapters", None)
    emit(payload)


def cmd_books_chunks(args):
    _, payload = http_call(args, "GET", "/api/v1/books/%s/chunks" % urllib.parse.quote(args.book_id), {
        "page": args.page, "size": args.size, "chapter_id": args.chapter_id,
    })
    emit(payload)


def cmd_books_tokens(args):
    _, payload = http_call(args, "GET", "/api/v1/books/%s/token-usage" % urllib.parse.quote(args.book_id))
    emit(payload)


def cmd_books_cover(args):
    _, payload = http_call(args, "GET", "/api/v1/books/%s/cover" % urllib.parse.quote(args.book_id), raw=True)
    out = args.out or "%s.jpg" % args.book_id
    with open(out, "wb") as handle:
        handle.write(payload)
    log("封面已写入 %s（%d 字节）" % (out, len(payload)))
    emit({"book_id": args.book_id, "path": os.path.abspath(out), "bytes": len(payload)})


def cmd_books_import(args):
    if not os.path.isfile(args.file):
        raise ApiError("文件不存在：" + args.file)
    fields = {}
    for key, value in (("source_origin", args.source_origin), ("mybooks_id", args.mybooks_id), ("cover_url", args.cover_url)):
        if value:
            fields[key] = value

    boundary = "----mynexus%s" % os.urandom(16).hex()
    filename = os.path.basename(args.file)
    with open(args.file, "rb") as handle:
        file_bytes = handle.read()

    chunks = []
    for key, value in fields.items():
        chunks.append(("--%s\r\n" % boundary).encode("utf-8"))
        chunks.append(('Content-Disposition: form-data; name="%s"\r\n\r\n' % key).encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    chunks.append(("--%s\r\n" % boundary).encode("utf-8"))
    chunks.append(('Content-Disposition: form-data; name="file"; filename="%s"\r\n' % filename).encode("utf-8"))
    chunks.append(b"Content-Type: application/octet-stream\r\n\r\n")
    chunks.append(file_bytes)
    chunks.append(b"\r\n")
    chunks.append(("--%s--\r\n" % boundary).encode("utf-8"))
    body = b"".join(chunks)

    path = "/api/v1/books/import"
    base_url = resolve_base_url(args)
    headers = build_headers(args)
    headers["Content-Type"] = "multipart/form-data; boundary=%s" % boundary
    log("上传 %s（%d 字节）到 %s" % (filename, len(file_bytes), path))
    request = urllib.request.Request(base_url + path, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ApiError("HTTP %s: %s" % (exc.code, exc.read().decode("utf-8", "replace")), exc.code)
    except urllib.error.URLError as exc:
        raise ApiError("无法连接 %s：%s（可用 --base-url 指定地址）" % (base_url, exc.reason))
    log("导入已受理，task=%s book=%s" % (payload.get("task_id"), payload.get("book_id")))
    emit(payload)


def cmd_books_update(args):
    body = {}
    for key, value in (("title", args.title), ("author", args.author), ("category", args.category), ("language", args.language)):
        if value is not None:
            body[key] = value
    tags = parse_csv(args.tags)
    if tags is not None:
        body["tags"] = tags
    if not body:
        raise ApiError("至少需要提供一个字段：--title/--author/--category/--language/--tags")
    _, payload = http_call(args, "PUT", "/api/v1/books/" + urllib.parse.quote(args.book_id), body=body)
    emit(payload)


def cmd_books_summary(args):
    text = args.text
    if args.file:
        with open(args.file, "r", encoding="utf-8") as handle:
            text = handle.read()
    if text is None:
        raise ApiError("需要 --text 或 --file 提供新的全书总结")
    _, payload = http_call(args, "PUT", "/api/v1/books/%s/summary" % urllib.parse.quote(args.book_id), body={"summary": text})
    log("全书总结已更新")
    emit(payload)


def cmd_books_rebuild(args):
    _, payload = http_call(args, "POST", "/api/v1/books/%s/rebuild" % urllib.parse.quote(args.book_id))
    log("重建任务已创建，task=%s（注意：重建会清空该书已有章节摘要向量）" % payload.get("task_id"))
    emit(payload)


def cmd_books_summarize(args):
    _, payload = http_call(args, "POST", "/api/v1/books/%s/summarize" % urllib.parse.quote(args.book_id), params={"mode": args.mode})
    log("总结任务已创建，task=%s" % payload.get("task_id"))
    emit(payload)


def cmd_books_delete(args):
    require_confirm(args, "删除书籍", args.book_id)
    status, _ = http_call(args, "DELETE", "/api/v1/books/" + urllib.parse.quote(args.book_id))
    log("书籍 %s 已删除（HTTP %s）" % (args.book_id, status))
    emit({"book_id": args.book_id, "deleted": True, "status": status})


def cmd_books_bulk_delete(args):
    require_confirm(args, "批量删除书籍", ",".join(args.book_ids))
    _, payload = http_call(args, "POST", "/api/v1/books/bulk-delete", body={"ids": args.book_ids})
    emit(payload)


def cmd_books_bulk_rebuild(args):
    _, payload = http_call(args, "POST", "/api/v1/books/bulk-rebuild", body={"ids": args.book_ids})
    log("批量重建已提交（注意：重建会清空各书已有章节摘要向量）")
    emit(payload)


def cmd_search(args):
    body = {"query": args.query, "enable_rerank": args.rerank}
    book_ids = parse_csv(args.book_ids)
    if book_ids:
        body["book_ids"] = book_ids
    if args.top_k:
        body["top_k"] = args.top_k
    if args.score_threshold is not None:
        body["score_threshold"] = args.score_threshold
    _, payload = http_call(args, "POST", "/api/v1/search/hybrid", body=body)
    emit(payload)


def cmd_chat(args):
    body = {"messages": [{"role": "user", "content": args.message}], "stream": True}
    if args.session_id:
        body["session_id"] = args.session_id
    book_ids = parse_csv(args.book_ids)
    if book_ids:
        body["book_ids"] = book_ids

    path = "/api/v1/chat/completions"
    url = resolve_base_url(args) + path
    headers = build_headers(args)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "text/event-stream"

    log("发起会话请求 session=%s books=%s" % (args.session_id or "(新建)", book_ids or []))
    request = urllib.request.Request(url, data=encode_body(body), headers=headers, method="POST")
    answer_parts = []
    citations = []
    tool_results = []
    session_id = args.session_id or ""
    started = time.time()

    try:
        response = urllib.request.urlopen(request, timeout=args.timeout)
    except urllib.error.HTTPError as exc:
        raise ApiError("HTTP %s: %s" % (exc.code, exc.read().decode("utf-8", "replace")), exc.code)
    except urllib.error.URLError as exc:
        raise ApiError("无法连接 %s：%s" % (url, exc.reason))

    with response:
        session_id = response.headers.get("X-Session-Id") or session_id
        for raw_line in response:
            line = raw_line.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            chunk = line[len("data:"):].strip()
            if chunk == "[DONE]":
                break
            if not chunk:
                continue
            try:
                frame = json.loads(chunk)
            except ValueError:
                log("跳过无法解析的 SSE 帧：%s" % chunk[:200])
                continue
            for choice in frame.get("choices") or []:
                delta = (choice.get("delta") or {}).get("content") or ""
                if delta:
                    answer_parts.append(delta)
            if frame.get("citations"):
                citations = frame["citations"]
            if frame.get("tool_result"):
                tool_results.append(frame["tool_result"])

    answer = "".join(answer_parts)
    log("会话完成：session=%s 回答 %d 字，引用 %d 条，工具调用 %d 次，耗时 %.1fs"
        % (session_id, len(answer), len(citations), len(tool_results), time.time() - started))
    emit({
        "session_id": session_id,
        "answer": answer,
        "citations": citations,
        "tool_results": tool_results,
    })


def cmd_sessions_list(args):
    _, payload = http_call(args, "GET", "/api/v1/chat/sessions")
    emit(payload)


def cmd_sessions_get(args):
    _, payload = http_call(args, "GET", "/api/v1/chat/sessions/" + urllib.parse.quote(args.session_id))
    emit(payload)


def cmd_sessions_rename(args):
    status, _ = http_call(args, "PUT", "/api/v1/chat/sessions/" + urllib.parse.quote(args.session_id), body={"title": args.title})
    log("会话 %s 已重命名为 %s" % (args.session_id, args.title))
    emit({"session_id": args.session_id, "title": args.title, "status": status})


def cmd_sessions_delete(args):
    require_confirm(args, "删除会话", args.session_id)
    status, _ = http_call(args, "DELETE", "/api/v1/chat/sessions/" + urllib.parse.quote(args.session_id))
    emit({"session_id": args.session_id, "deleted": True, "status": status})


def cmd_tasks_list(args):
    _, payload = http_call(args, "GET", "/api/v1/tasks", {
        "page": args.page, "size": args.size, "status": args.status, "book_id": args.book_id,
    })
    emit(payload)


def cmd_tasks_get(args):
    _, payload = http_call(args, "GET", "/api/v1/tasks/" + urllib.parse.quote(args.task_id))
    emit(payload)


def cmd_tasks_retry(args):
    _, payload = http_call(args, "POST", "/api/v1/tasks/%s/retry" % urllib.parse.quote(args.task_id))
    emit(payload)


def cmd_tasks_cancel(args):
    _, payload = http_call(args, "POST", "/api/v1/tasks/%s/cancel" % urllib.parse.quote(args.task_id))
    log("取消请求已提交：task=%s" % args.task_id)
    emit(payload)


def build_parser():
    parser = argparse.ArgumentParser(prog="mynexus", description="MyNexus 书库 CLI（书籍管理 + 会话/检索问答）")
    parser.add_argument("--base-url", help="core-api 地址，默认取 MYNEXUS_BASE_URL，否则 %s" % DEFAULT_BASE_URL)
    parser.add_argument("--token", help="API Token，默认取 MYNEXUS_API_TOKEN")
    parser.add_argument("--mybooks-user-id", help="以外部 MyBooks 用户身份访问会话接口（X-MyBooks-User-ID）")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="单次请求超时秒数，默认 60")
    parser.add_argument("--quiet", action="store_true", help="关闭调试日志")

    groups = parser.add_subparsers(dest="group", required=True)

    groups.add_parser("health", help="服务健康检查").set_defaults(func=cmd_health)

    books = groups.add_parser("books", help="书籍管理")
    books_sub = books.add_subparsers(dest="cmd", required=True)

    books_list = books_sub.add_parser("list", help="书籍列表")
    books_list.add_argument("--page", type=int, default=1)
    books_list.add_argument("--size", type=int, default=20)
    books_list.add_argument("--status")
    books_list.add_argument("--q", help="标题/作者关键词")
    books_list.set_defaults(func=cmd_books_list)

    books_get = books_sub.add_parser("get", help="书籍详情（含章节摘要/关键词/术语）")
    books_get.add_argument("book_id")
    books_get.add_argument("--no-chapters", action="store_true", help="只输出书籍本身，省略章节列表")
    books_get.set_defaults(func=cmd_books_get)

    books_chunks = books_sub.add_parser("chunks", help="书籍分块原文")
    books_chunks.add_argument("book_id")
    books_chunks.add_argument("--chapter-id")
    books_chunks.add_argument("--page", type=int, default=1)
    books_chunks.add_argument("--size", type=int, default=50)
    books_chunks.set_defaults(func=cmd_books_chunks)

    books_tokens = books_sub.add_parser("tokens", help="书籍 token 用量")
    books_tokens.add_argument("book_id")
    books_tokens.set_defaults(func=cmd_books_tokens)

    books_cover = books_sub.add_parser("cover", help="下载封面")
    books_cover.add_argument("book_id")
    books_cover.add_argument("--out", help="输出文件名，默认 <book_id>.jpg")
    books_cover.set_defaults(func=cmd_books_cover)

    books_import = books_sub.add_parser("import", help="导入 epub/txt（写操作）")
    books_import.add_argument("file")
    books_import.add_argument("--source-origin")
    books_import.add_argument("--mybooks-id")
    books_import.add_argument("--cover-url")
    books_import.set_defaults(func=cmd_books_import)

    books_update = books_sub.add_parser("update", help="更新标题/作者/分类/语言/标签（写操作）")
    books_update.add_argument("book_id")
    books_update.add_argument("--title")
    books_update.add_argument("--author")
    books_update.add_argument("--category")
    books_update.add_argument("--language")
    books_update.add_argument("--tags", help="逗号分隔")
    books_update.set_defaults(func=cmd_books_update)

    books_summary = books_sub.add_parser("summary", help="改写全书总结（写操作）")
    books_summary.add_argument("book_id")
    books_summary.add_argument("--text")
    books_summary.add_argument("--file")
    books_summary.set_defaults(func=cmd_books_summary)

    books_rebuild = books_sub.add_parser("rebuild", help="重新解析/分块/向量化（写操作）")
    books_rebuild.add_argument("book_id")
    books_rebuild.set_defaults(func=cmd_books_rebuild)

    books_summarize = books_sub.add_parser("summarize", help="触发章节+全书总结（写操作）")
    books_summarize.add_argument("book_id")
    books_summarize.add_argument("--mode", choices=["restart", "continue"], default="restart")
    books_summarize.set_defaults(func=cmd_books_summarize)

    books_delete = books_sub.add_parser("delete", help="删除单本书（写操作，需 --yes）")
    books_delete.add_argument("book_id")
    books_delete.add_argument("--yes", action="store_true")
    books_delete.set_defaults(func=cmd_books_delete)

    books_bulk_delete = books_sub.add_parser("bulk-delete", help="批量删除（写操作，需 --yes）")
    books_bulk_delete.add_argument("book_ids", nargs="+")
    books_bulk_delete.add_argument("--yes", action="store_true")
    books_bulk_delete.set_defaults(func=cmd_books_bulk_delete)

    books_bulk_rebuild = books_sub.add_parser("bulk-rebuild", help="批量重建（写操作）")
    books_bulk_rebuild.add_argument("book_ids", nargs="+")
    books_bulk_rebuild.set_defaults(func=cmd_books_bulk_rebuild)

    search = groups.add_parser("search", help="混合检索（向量+关键词）")
    search.add_argument("--query", required=True)
    search.add_argument("--book-ids", help="逗号分隔，留空检索全部书籍")
    search.add_argument("--top-k", type=int, default=10)
    search.add_argument("--score-threshold", type=float)
    search.add_argument("--rerank", action="store_true")
    search.set_defaults(func=cmd_search)

    chat = groups.add_parser("chat", help="向书库提问（流式，返回答案+引用）")
    chat.add_argument("--message", required=True)
    chat.add_argument("--session-id", help="沿用已有会话，留空则新建")
    chat.add_argument("--book-ids", help="逗号分隔，限定检索范围")
    chat.set_defaults(func=cmd_chat)

    sessions = groups.add_parser("sessions", help="会话查询与管理")
    sessions_sub = sessions.add_subparsers(dest="cmd", required=True)

    sessions_list = sessions_sub.add_parser("list", help="会话列表")
    sessions_list.set_defaults(func=cmd_sessions_list)

    sessions_get = sessions_sub.add_parser("get", help="会话详情（含消息与引用）")
    sessions_get.add_argument("session_id")
    sessions_get.set_defaults(func=cmd_sessions_get)

    sessions_rename = sessions_sub.add_parser("rename", help="重命名会话")
    sessions_rename.add_argument("session_id")
    sessions_rename.add_argument("--title", required=True)
    sessions_rename.set_defaults(func=cmd_sessions_rename)

    sessions_delete = sessions_sub.add_parser("delete", help="删除会话（需 --yes）")
    sessions_delete.add_argument("session_id")
    sessions_delete.add_argument("--yes", action="store_true")
    sessions_delete.set_defaults(func=cmd_sessions_delete)

    tasks = groups.add_parser("tasks", help="任务查询与重试/取消")
    tasks_sub = tasks.add_subparsers(dest="cmd", required=True)

    tasks_list = tasks_sub.add_parser("list", help="任务列表")
    tasks_list.add_argument("--page", type=int, default=1)
    tasks_list.add_argument("--size", type=int, default=20)
    tasks_list.add_argument("--status")
    tasks_list.add_argument("--book-id")
    tasks_list.set_defaults(func=cmd_tasks_list)

    tasks_get = tasks_sub.add_parser("get", help="任务详情（含阶段日志）")
    tasks_get.add_argument("task_id")
    tasks_get.set_defaults(func=cmd_tasks_get)

    tasks_retry = tasks_sub.add_parser("retry", help="重试失败任务（写操作）")
    tasks_retry.add_argument("task_id")
    tasks_retry.set_defaults(func=cmd_tasks_retry)

    tasks_cancel = tasks_sub.add_parser("cancel", help="取消运行中任务（写操作）")
    tasks_cancel.add_argument("task_id")
    tasks_cancel.set_defaults(func=cmd_tasks_cancel)

    return parser


def main(argv):
    global _QUIET
    parser = build_parser()
    args = parser.parse_args(argv)
    _QUIET = bool(getattr(args, "quiet", False))
    try:
        args.func(args)
    except ApiError as exc:
        log("执行失败：%s" % exc)
        print(json.dumps({"error": str(exc), "status": exc.status}, ensure_ascii=False), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        log("已中断")
        return 130
    except Exception as exc:
        log("未处理异常 %s: %s" % (type(exc).__name__, exc))
        print(json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
