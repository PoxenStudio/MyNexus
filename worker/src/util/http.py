import ipaddress
import urllib.error
import urllib.request
from urllib.parse import urlparse

_no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_default_opener = urllib.request.build_opener()


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


def call_provider(req: urllib.request.Request, *, timeout: float, service: str, provider: str, model: str):
    """`urlopen`, but for Embedding/LLM provider calls specifically: turns
    the handful of failure modes that account for almost every real-world
    misconfiguration (service down, wrong API key, model not pulled/deployed)
    into a `ServiceCallError` with a message that names the problem and
    where to fix it, instead of a bare `HTTP Error 404: Not Found` that
    could mean anything.

    `service` is "embedding" or "llm", `provider` is "openai" or "ollama" —
    both are used purely to word the message, they don't change behavior.
    """
    label = _SERVICE_LABELS.get(service, service)
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
        raise ServiceCallError(f"{label} 服务返回异常（HTTP {exc.code}）：{exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ServiceCallError(
            f"{label} 服务不可用：无法连接（{exc.reason}），请检查系统设置中的服务地址是否正确，以及对应服务本身是否已启动"
        ) from exc
