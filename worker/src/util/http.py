import ipaddress
import logging
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_default_opener = urllib.request.build_opener()

# One lock per distinct host:port, shared process-wide by every caller that
# resolves to the same address — regardless of which provider class
# (OllamaLLM, OllamaEmbedder, ...) or pipeline (ingest, summarize, chat) it's
# called from. Ollama only keeps one model actively loaded per GPU/CPU
# budget; if an embedding call (e.g. bge-m3, from an ingest task) and an LLM
# call (e.g. qwen2.5:7b-instruct, from a concurrently-running summarize or
# chat) land on the same local Ollama instance at once, Ollama may swap one
# model out to load the other — and a request whose model just got evicted
# mid-generation doesn't get a normal error, its connection is simply cut,
# surfacing here as a bare `HTTPError 500` / `URLError` with nothing useful
# in Ollama's own log beyond "completion error ... EOF". Ollama's own
# provider classes hold this lock for the *entire* request (including
# streaming the response body, not just opening the connection) to keep two
# different models' requests from ever overlapping against the same
# instance — see OllamaLLM.process/call and OllamaEmbedder.process. A
# distinct lock per host:port means unrelated targets (a remote OpenAI
# endpoint, a second local service) are never serialized against each other
# for no reason.
_host_locks_guard = threading.Lock()
_host_locks: dict[str, threading.Lock] = {}


def host_lock(url: str) -> threading.Lock:
    parsed = urlparse(url)
    key = f"{parsed.hostname}:{parsed.port or ''}"
    with _host_locks_guard:
        return _host_locks.setdefault(key, threading.Lock())


def _is_local_or_lan(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


def urlopen(req: urllib.request.Request, timeout: float = 30):
    """`urllib.request.urlopen` that bypasses any system/VPN HTTP proxy for
    localhost/LAN targets (Core API, a LAN Ollama server, ...) while still
    honoring the proxy for genuine external hosts (OpenAI, DeepSeek, ...).

    Without this, a machine with a system-wide proxy (common with VPN/Clash
    tools on macOS) silently 502s every localhost call — see
    .claude/memory/mynexus_macos_proxy_gotcha.md.
    """
    host = urlparse(req.full_url).hostname or ""
    opener = _no_proxy_opener if _is_local_or_lan(host) else _default_opener
    return opener.open(req, timeout=timeout)


class ServiceCallError(RuntimeError):
    """Raised for a failed call to an Embedding/LLM provider, carrying a
    human-readable, actionable message — this is what ends up in a task's
    `error_msg` or a chat error banner, so it needs to make sense to
    whoever's reading it, not just whoever's debugging it."""


_SERVICE_LABELS = {"embedding": "Embedding", "llm": "LLM"}

# How many extra attempts a retryable failure gets beyond the first one, and
# how long to wait between attempts (doubling each time: 2s, 4s, 8s — total
# worst-case wait ~14s, small next to a summarize/ingest task that can
# already run for minutes). Only failures that are plausibly transient are
# worth retrying — see _is_retryable below; a call already known to keep
# failing (bad API key, wrong model name) would just waste 3x the wait
# before surfacing the same actionable error it would have given up front.
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE_SECONDS = 2.0

# HTTP status codes worth retrying: 5xx (the provider itself had a problem —
# this is what an overloaded/restarting local Ollama returns) and 429 (rate
# limited, common on hosted APIs like OpenAI). Anything else (401/403/404,
# a plain 400 bad request, ...) is a configuration or request problem that
# retrying can't fix.
_RETRYABLE_HTTP_CODES = frozenset({429, 500, 502, 503, 504})


def _is_retryable(exc: urllib.error.URLError) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRYABLE_HTTP_CODES
    # A plain URLError (connection refused/reset, DNS failure, timeout) is
    # exactly the kind of blip a retry a couple seconds later can ride out.
    return True


def call_provider(req: urllib.request.Request, *, timeout: float, service: str, provider: str, model: str):
    """`urlopen`, but for Embedding/LLM provider calls specifically: turns
    the handful of failure modes that account for almost every real-world
    misconfiguration (service down, wrong API key, model not pulled/deployed)
    into a `ServiceCallError` with a message that names the problem and
    where to fix it, instead of a bare `HTTP Error 404: Not Found` that
    could mean anything.

    `service` is "embedding" or "llm", `provider` is "openai" or "ollama" —
    both are used purely to word the message, they don't change behavior.

    Retries up to _MAX_RETRIES times (with backoff) on failures classified
    as transient by _is_retryable — a temporary 5xx/429 or a connection
    hiccup shouldn't fail an entire ingest/summarize task by itself when
    trying again a couple seconds later would very likely have worked, as
    it does for a one-off Ollama hiccup like the one this was added for
    (see the traceback in the commit this constant set was introduced in).
    Non-retryable failures (401/403/404) still raise immediately, same as
    before — see the docstring above for why those aren't worth retrying.
    """
    label = _SERVICE_LABELS.get(service, service)
    attempt = 0
    while True:
        try:
            return urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ServiceCallError(
                    f"{label} 服务鉴权失败（HTTP {exc.code}）：请检查系统设置中 {provider} 的 API Key 是否正确"
                ) from exc
            if exc.code == 404:
                hint = f"，并确认已执行过 `ollama pull {model}`" if provider == "ollama" else ""
                raise ServiceCallError(
                    f"{label} 模型未找到（HTTP 404）：请检查系统设置中的模型名称「{model}」是否正确{hint}"
                ) from exc
            if attempt < _MAX_RETRIES and _is_retryable(exc):
                attempt += 1
                delay = _RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "%s 服务返回 HTTP %s，%.0f 秒后重试（第 %d/%d 次）", label, exc.code, delay, attempt, _MAX_RETRIES
                )
                time.sleep(delay)
                continue
            raise ServiceCallError(f"{label} 服务返回异常（HTTP {exc.code}）：{exc.reason}") from exc
        except urllib.error.URLError as exc:
            if attempt < _MAX_RETRIES and _is_retryable(exc):
                attempt += 1
                delay = _RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "%s 服务不可用（%s），%.0f 秒后重试（第 %d/%d 次）", label, exc.reason, delay, attempt, _MAX_RETRIES
                )
                time.sleep(delay)
                continue
            raise ServiceCallError(
                f"{label} 服务不可用：无法连接（{exc.reason}），请检查系统设置中的服务地址是否正确，以及对应服务本身是否已启动"
            ) from exc
