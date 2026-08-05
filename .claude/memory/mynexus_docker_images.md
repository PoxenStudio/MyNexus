---
name: mynexus-docker-images
description: Dockerfile OCI labels/ENV convention and Makefile image-build targets (single-arch + multi-arch buildx), added per user request
metadata:
  type: project
---

User asked (2026-08-05) to stop treating the Dockerfiles as bare-minimum: add OCI image metadata, default runtime ENV vars, and Makefile targets to actually build/push the images — modeled after the sibling project `/Volumes/data/projects/reader/mybooks/Makefile`'s buildx pattern.

**All three Dockerfiles** (`core-api/Dockerfile`, `worker/Dockerfile`, `web-ui/Dockerfile`) now carry the same block in their final stage:
- `LABEL org.opencontainers.image.{title,description,authors,vendor,version}` + a plain `maintainer` label for older tooling. Author is `poxenstudio <poxenstudio@gmail.com>` per explicit instruction. `version` is filled from a `ARG VERSION=dev` (re-declared in the final stage, since ARG scope doesn't cross stages), passed at build time via `--build-arg VERSION=$(VER)` from the Makefile. No `org.opencontainers.image.source` — no public repo URL exists to point at, don't invent one.
- `RUN apk add --no-cache tzdata` — required for `ENV TZ=...` to actually affect anything on Alpine-based images (Alpine's base image has no tzdata by default); all three final stages are Alpine-based (`alpine:3.20`, `python:3.12-alpine`, `nginx:alpine`) so this applies uniformly.
- `ENV TZ=Asia/Shanghai LANG=C.UTF-8 PUID=1000 PGID=1000` — per explicit user request. Note: `PUID`/`PGID` are set but **not currently consumed** by any entrypoint script (no gosu/su-exec user-remapping logic exists yet, unlike linuxserver.io-style images) — they're inert placeholders for now. If a future request wants actual non-root user mapping, that's separate follow-up work, not implied by this change.

**Makefile additions** (top of `/Volumes/data/projects/poxenstudio/MyNexus/Makefile`, before `dev-up`):
- Image naming: `poxenstudio/mynexus-{core-api,worker,webui}:$(VER)` + `:latest`, where `VER := git rev-parse --abbrev-ref HEAD` (falls back to `dev` if not in a git repo) — mirrors mybooks' Makefile convention of tagging by branch name, not semver.
- `setup-multiarch` — one-time buildx builder bootstrap (`docker buildx create --use --name mynexusbuilder`), copied near-verbatim from mybooks' Makefile.
- `build-core` / `build-worker` / `build-webui` / `build-images` — single-platform (host arch, auto-detected via `uname -m`) local builds using plain `docker build`, tagged both `:$(VER)` and `:latest`. No `--push`.
- `build-core-multiarch` / `build-worker-multiarch` / `build-webui-multiarch` / `build-images-multiarch` — `docker buildx build --platform=linux/amd64,linux/arm64 ... --push`. Multi-platform buildx output can't be `--load`ed into the local docker daemon (no multi-arch manifest support there), so these targets always push straight to the registry — there is no "build multi-arch, keep local" target, unlike mybooks' `build-multiarch-local` (which arguably has the same limitation, just not called out there).
- No `push` target exists separately from the `-multiarch` targets — single-arch builds are load-only (for local testing), multi-arch builds push directly. If a maintainer wants to push a single-arch image, they'd add a plain `docker push $(CORE_IMAGE)` step; not implemented since it wasn't asked for.

**Verified**: `make -n build-images` dry-run resolves `PLATFORM` correctly from `uname -m` and prints correct `docker build` invocations for all three services; Makefile tab/space correctness checked with `awk` (all target recipe lines use tabs, not spaces — `make` requires this or it errors). Did not actually run a `docker build` (no Docker daemon exercised this session) — the build commands themselves are unverified beyond syntax/dry-run.

See [[mynexus_project]] for where this fits in the overall build/dev-loop picture.
