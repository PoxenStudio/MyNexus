---
name: mynexus-macos-proxy-gotcha
description: macOS system HTTP proxy silently breaks Python urllib calls to localhost during MyNexus local dev/testing
metadata:
  type: project
---

On this dev machine, `urllib.request.getproxies()` returns a system-configured proxy (`http://127.0.0.1:7897`, likely a VPN/Clash-style tool) even though no `HTTP_PROXY`/`HTTPS_PROXY` env vars are set — Python's `urllib` reads macOS's SystemConfiguration proxy settings directly. This silently routed Worker's `http://localhost:8099/...` callback POSTs through that proxy and got a 502 back instead of reaching the target, with no obvious error pointing at "proxy" (looked like the callback target was just broken).

Why it matters: any Python code in this repo (`worker/`) doing HTTP calls to `localhost`/`core-api`/other internal service names will hit this. Go's `net/http` is unaffected — it only honors `HTTP_PROXY`/`NO_PROXY` env vars, not macOS system proxy settings — so this is Python-specific.

How to apply: use `worker/src/util/http.py`'s `urlopen(req, timeout=...)` for all outbound HTTP in worker code instead of calling `urllib.request.urlopen` directly. It inspects the request's hostname and only bypasses the proxy for localhost/loopback/private-IP targets (Core API, a LAN Ollama server, the mock test server, ...), while still routing genuine external hosts (api.openai.com, etc.) through the system proxy as normal — so real cloud API calls that need a proxy for network reasons still get one.
```python
from util.http import urlopen
with urlopen(req, timeout=timeout) as resp:
    ...
```
As of M3 this is used everywhere worker makes an outbound HTTP call: `pipelines/ingestion.py` (Core API callbacks), `nodes/embedders/{openai,ollama}_embedder.py`, `nodes/llm/{openai,ollama}_llm.py`. Any new outbound HTTP client code added to `worker/` should use it too rather than reaching for `urllib.request` directly.
