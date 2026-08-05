PARENT := /Volumes/data/projects/poxenstudio/MyNexus

.PHONY: dev-up dev-down build-images build-core build-worker build-webui \
	setup-multiarch build-images-multiarch build-core-multiarch build-worker-multiarch build-webui-multiarch

# ---- image build config ----
REGISTRY := poxenstudio
VER := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo dev)
CORE_IMAGE := $(REGISTRY)/mynexus-core-api:$(VER)
CORE_LATEST := $(REGISTRY)/mynexus-core-api:latest
WORKER_IMAGE := $(REGISTRY)/mynexus-worker:$(VER)
WORKER_LATEST := $(REGISTRY)/mynexus-worker:latest
WEBUI_IMAGE := $(REGISTRY)/mynexus-webui:$(VER)
WEBUI_LATEST := $(REGISTRY)/mynexus-webui:latest

BUILDER := mynexusbuilder
ARCH := $(shell uname -m)
PLATFORM ?= linux/$(shell if [ "$(ARCH)" = "x86_64" ]; then echo "amd64"; elif [ "$(ARCH)" = "aarch64" ] || [ "$(ARCH)" = "arm64" ]; then echo "arm64"; else echo "amd64"; fi)
PLATFORMS := linux/amd64,linux/arm64

# 初始化多架构构建环境（每台构建机只需运行一次），不要使用 snap 安装的 docker
setup-multiarch:
	docker run --privileged --rm tonistiigi/binfmt --install all
	docker buildx create --use --name $(BUILDER) || docker buildx use $(BUILDER)
	docker buildx inspect $(BUILDER) --bootstrap

# ---- single-arch local builds (docker build, loaded into local docker) ----
build-core:
	docker build --pull --platform=$(PLATFORM) --build-arg VERSION=$(VER) \
		-f core-api/Dockerfile -t $(CORE_IMAGE) -t $(CORE_LATEST) core-api

build-worker:
	docker build --pull --platform=$(PLATFORM) --build-arg VERSION=$(VER) \
		-f worker/Dockerfile -t $(WORKER_IMAGE) -t $(WORKER_LATEST) worker

build-webui:
	docker build --pull --platform=$(PLATFORM) --build-arg VERSION=$(VER) \
		-f web-ui/Dockerfile -t $(WEBUI_IMAGE) -t $(WEBUI_LATEST) web-ui

build-images: build-core build-worker build-webui

# ---- multi-arch builds (docker buildx, pushed to registry) ----
build-core-multiarch:
	docker buildx build --pull --platform=$(PLATFORMS) \
		--builder $(BUILDER) --build-arg VERSION=$(VER) \
		-f core-api/Dockerfile -t $(CORE_IMAGE) -t $(CORE_LATEST) --push core-api

build-worker-multiarch:
	docker buildx build --pull --platform=$(PLATFORMS) \
		--builder $(BUILDER) --build-arg VERSION=$(VER) \
		-f worker/Dockerfile -t $(WORKER_IMAGE) -t $(WORKER_LATEST) --push worker

build-webui-multiarch:
	docker buildx build --pull --platform=$(PLATFORMS) \
		--builder $(BUILDER) --build-arg VERSION=$(VER) \
		-f web-ui/Dockerfile -t $(WEBUI_IMAGE) -t $(WEBUI_LATEST) --push web-ui

build-images-multiarch: build-core-multiarch build-worker-multiarch build-webui-multiarch

dev-up:
	mkdir -p $(PARENT)/.tmp
	GOCACHE=/Volumes/data/cache/go/.cache/go-build \
	GOMODCACHE=/Volumes/data/cache/go/pkg/mod \
	GOPATH=/Volumes/data/cache/go \
	GOTMPDIR=/Volumes/data/cache/go/tmp \
	MYNEXUS_CONFIG_PATH=$(PARENT)/config/config.yaml \
	MYNEXUS_STORAGE_SQLITE_PATH=$(PARENT)/data/mynexus.db \
	PORT=8080 go run ./core-api/cmd/mynexus-api > $(PARENT)/.tmp/core.log 2>&1 & \
	MYNEXUS_CONFIG_PATH=$(PARENT)/config/config.yaml \
	PYTHONUNBUFFERED=1 \
	PORT=8001 python3 worker/src/server.py > $(PARENT)/.tmp/worker.log 2>&1 & \
	( cd web-ui && npm run dev > $(PARENT)/.tmp/web.log 2>&1 & ) ; \
	 sleep 3 && echo 'Dev services started'

dev-down:
	pkill -f 'mynexus-api' || true
	pkill -f 'worker/src/server.py' || true
	pkill -f 'vite' || true
