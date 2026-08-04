import ipaddress
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
