---
name: mynexus-macos-proxy-gotcha
description: macOS system HTTP proxy silently breaks Python urllib calls to localhost during MyNexus local dev/testing
metadata:
  type: project
---

On this dev machine, `urllib.request.getproxies()` returns a system-configured proxy (`http://127.0.0.1:7897`, likely a VPN/Clash-style tool) even though no `HTTP_PROXY`/`HTTPS_PROXY` env vars are set — Python's `urllib` reads macOS's SystemConfiguration proxy settings directly. This silently routed Worker's `http://localhost:8099/...` callback POSTs through that proxy and got a 502 back instead of reaching the target, with no obvious error pointing at "proxy" (looked like the callback target was just broken).

Why it matters: any Python code in this repo (`worker/`) doing HTTP calls to `localhost`/`core-api`/other internal service names will hit this. Go's `net/http` is unaffected — it only honors `HTTP_PROXY`/`NO_PROXY` env vars, not macOS system proxy settings — so this is Python-specific.

How to apply: for internal service-to-service HTTP calls in worker code (e.g. task progress/complete/fail callbacks to Core API), always bypass the system proxy explicitly:
```python
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
opener.open(req, timeout=timeout)
```
This is already applied in `worker/src/pipelines/ingestion.py`'s `_post_json`. Apply the same pattern to any new outbound HTTP client code added to `worker/` (e.g. M3's calls to Embedding/LLM providers should NOT bypass proxy — those are legitimately external and may need it — but calls to Core API / other internal MyNexus services should).
