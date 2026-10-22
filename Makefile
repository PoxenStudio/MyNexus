PARENT := $(patsubst %/,%,$(dir $(realpath $(lastword $(MAKEFILE_LIST)))))

.PHONY: dev-up dev-down dev-logs build-base build-image setup-multiarch build-base-multiarch build-image-multiarch

# ---- image build config ----
REGISTRY := poxenstudio
VER := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo dev)
IMAGE := $(REGISTRY)/mynexus:$(VER)
IMAGE_LATEST := $(REGISTRY)/mynexus:latest
BASE_IMAGE := $(REGISTRY)/mynexus_base:$(VER)
BASE_IMAGE_LATEST := $(REGISTRY)/mynexus_base:latest

BUILDER := shukubuilder
ARCH := $(shell uname -m)
PLATFORM ?= linux/$(shell if [ "$(ARCH)" = "x86_64" ]; then echo "amd64"; elif [ "$(ARCH)" = "aarch64" ] || [ "$(ARCH)" = "arm64" ]; then echo "arm64"; else echo "amd64"; fi)
PLATFORMS := linux/amd64,linux/arm64

# 初始化多架构构建环境（每台构建机只需运行一次），不要使用 snap 安装的 docker
setup-multiarch:
	docker run --privileged --rm tonistiigi/binfmt --install all
	docker buildx create --use --name $(BUILDER) || docker buildx use $(BUILDER)
	docker buildx inspect $(BUILDER) --bootstrap

# ---- base image (runtime dependencies and offline models) ----
build-base:
	docker build --pull --platform=$(PLATFORM) --build-arg VERSION=$(VER) \
		-f Dockerfile.base -t $(BASE_IMAGE) -t $(BASE_IMAGE_LATEST) .

# ---- single-arch local build (docker build, loaded into local docker) ----
build-image: build-base
	docker build --platform=$(PLATFORM) --build-arg VERSION=$(VER) \
		-f Dockerfile -t $(IMAGE) -t $(IMAGE_LATEST) .

# ---- multi-arch base and app images (published to the configured registry) ----
build-base-multiarch:
	docker buildx build --pull --platform=$(PLATFORMS) \
		--builder $(BUILDER) --build-arg VERSION=$(VER) \
		-f Dockerfile.base -t $(BASE_IMAGE) -t $(BASE_IMAGE_LATEST) --load .

build-image-multiarch: build-base-multiarch
	docker buildx build --pull --platform=$(PLATFORMS) \
		--builder $(BUILDER) --build-arg VERSION=$(VER) \
		-f Dockerfile -t $(IMAGE) -t $(IMAGE_LATEST) --load .

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
	PORT=8001 python worker/src/server.py > $(PARENT)/.tmp/worker.log 2>&1 & \
	( cd web-ui && npm run dev > $(PARENT)/.tmp/web.log 2>&1 & ) ; \
	 sleep 3 && echo 'Dev services started'

dev-down:
	pkill -f 'mynexus-api' || true
	pkill -f 'worker/src/server.py' || true
	pkill -f 'vite' || true

# Tails all three dev-up log files at once in a single `tail` process
dev-logs:
	@touch $(PARENT)/.tmp/core.log $(PARENT)/.tmp/worker.log $(PARENT)/.tmp/web.log
	cd $(PARENT)/.tmp && tail -n 20 -f core.log worker.log web.log
