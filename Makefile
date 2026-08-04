PARENT := /Volumes/data/projects/poxenstudio/MyNexus

m1-up:
	mkdir -p $(PARENT)/.tmp
	GOCACHE=/Volumes/data/cache/go/.cache/go-build \
	GOMODCACHE=/Volumes/data/cache/go/pkg/mod \
	GOPATH=/Volumes/data/cache/go \
	GOTMPDIR=/Volumes/data/cache/go/tmp \
	MYNEXUS_CONFIG_PATH=$(PARENT)/config/config.yaml \
	MYNEXUS_STORAGE_SQLITE_PATH=$(PARENT)/data/mynexus.db \
	PORT=8080 go run ./core-api/cmd/mynexus-api > $(PARENT)/.tmp/core.log 2>&1 & \
	MYNEXUS_CONFIG_PATH=$(PARENT)/config/config.yaml \
	PORT=8001 python3 worker/src/server.py > $(PARENT)/.tmp/worker.log 2>&1 & \
	( cd web-ui && npm run dev > $(PARENT)/.tmp/web.log 2>&1 & ) ; \
	 sleep 3 && echo 'M1 services started'

m1-down:
	pkill -f 'mynexus-api' || true
	pkill -f 'worker/src/server.py' || true
	pkill -f 'vite' || true
