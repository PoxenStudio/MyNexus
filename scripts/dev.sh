#!/usr/bin/env bash
# MyNexus 本地开发环境启停：core-api + worker + web-ui（Vite）。
# 用法：scripts/dev.sh up|down，或 make dev-up / make dev-down。
# 日志写入 .tmp/，PID 写入 .tmp/dev/，可用 make dev-logs 聚合查看。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$ROOT/.tmp"
PID_DIR="$TMP_DIR/dev"
CONFIG="${MYNEXUS_CONFIG_PATH:-$ROOT/data/config/config.yaml}"
SQLITE="${MYNEXUS_STORAGE_SQLITE_PATH:-$ROOT/data/mynexus.db}"

CORE_LOG="$TMP_DIR/core.log"
WORKER_LOG="$TMP_DIR/worker.log"
WEB_LOG="$TMP_DIR/web.log"
CORE_PID="$PID_DIR/core.pid"
WORKER_PID="$PID_DIR/worker.pid"
WEB_PID="$PID_DIR/web.pid"

# 与 config/config.yaml 及 web-ui/vite.config.ts 保持一致。
API_PORT=8080
GRPC_PORT=9090
WORKER_PORT=8001
WEB_PORT=3030

# Go 构建缓存沿用 Makefile 中的约定，避免默认落到系统盘。
export GOCACHE="${GOCACHE:-/Volumes/data/cache/go/.cache/go-build}"
export GOMODCACHE="${GOMODCACHE:-/Volumes/data/cache/go/pkg/mod}"
export GOPATH="${GOPATH:-/Volumes/data/cache/go}"
export GOTMPDIR="${GOTMPDIR:-/Volumes/data/cache/go/tmp}"

log() { printf '%s\n' "$*"; }

die() {
  log "[!!] $*"
  exit 1
}

# 打印给定端口当前的监听进程，便于端口冲突时定位。
port_pid() {
  lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -n 1
}

# PID 文件存在且进程仍存活时才返回 PID。
service_pid() {
  local pid_file="$1" pid
  [[ -f "$pid_file" ]] || return 1
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  printf '%s' "$pid"
}

service_running() {
  service_pid "$1" >/dev/null 2>&1
}

require_port_free() {
  local label="$1" port="$2" pid cmd
  if pid="$(port_pid "$port")" && [[ -n "$pid" ]]; then
    cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    log "[!!] 端口 $port（$label）已被占用：pid $pid ${cmd:-(未知进程)}"
    log "     请先执行 make dev-down，或手动停止占用该端口的进程后重试。"
    return 1
  fi
}

require_config() {
  [[ -f "$CONFIG" ]] || die "缺少本地配置文件 $CONFIG（可从 config/config.yaml 复制一份）"
}

require_commands() {
  local need_go="$1" need_python="$2" need_node="$3"
  if [[ "$need_go" == "1" ]] && ! command -v go >/dev/null 2>&1; then
    die "未找到 go 命令，无法启动 core-api"
  fi
  if [[ "$need_python" == "1" ]] && ! command -v python >/dev/null 2>&1; then
    die "未找到 python 命令，请先激活包含 grpc 依赖的 Python 环境"
  fi
  if [[ "$need_node" == "1" ]]; then
    command -v npm >/dev/null 2>&1 || die "未找到 npm 命令，无法启动 web-ui"
    [[ -d "$ROOT/web-ui/node_modules" ]] || die "web-ui 依赖未安装，请先执行：cd web-ui && npm install"
  fi
}

wait_http() {
  local name="$1" url="$2" timeout="$3" pid_file="$4"
  local deadline=$((SECONDS + timeout))
  while ((SECONDS < deadline)); do
    if curl -fsS --max-time 2 -o /dev/null "$url" 2>/dev/null; then
      log "[OK] $name 已就绪"
      return 0
    fi
    if ! service_running "$pid_file"; then
      return 1
    fi
    sleep 1
  done
  return 1
}

wait_tcp() {
  local name="$1" port="$2" timeout="$3" pid_file="$4"
  local deadline=$((SECONDS + timeout))
  while ((SECONDS < deadline)); do
    if python - "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

with socket.socket() as sock:
    sock.settimeout(1)
    sock.connect(("127.0.0.1", int(sys.argv[1])))
PY
    then
      log "[OK] $name 已就绪"
      return 0
    fi
    if ! service_running "$pid_file"; then
      return 1
    fi
    sleep 1
  done
  return 1
}

tail_log() {
  local log_file="$1"
  [[ -f "$log_file" ]] || return 0
  log "----- $log_file（最后 20 行）-----"
  tail -n 20 "$log_file" || true
  log "--------------------------------"
}

start_core() {
  mkdir -p "$GOTMPDIR"
  log "[..] 启动 core-api（http :$API_PORT，grpc :$GRPC_PORT）"
  (
    cd "$ROOT"
    PORT="$API_PORT" \
    MYNEXUS_SERVER_PORT="$API_PORT" \
    MYNEXUS_SERVER_GRPC_PORT="$GRPC_PORT" \
    MYNEXUS_CONFIG_PATH="$CONFIG" \
    MYNEXUS_STORAGE_SQLITE_PATH="$SQLITE" \
    nohup go run ./core-api/cmd/mynexus-api >"$CORE_LOG" 2>&1 &
    echo $! >"$CORE_PID"
  )
}

start_worker() {
  log "[..] 启动 worker（grpc :$WORKER_PORT）"
  (
    cd "$ROOT"
    PORT="$WORKER_PORT" \
    PYTHONUNBUFFERED=1 \
    MYNEXUS_CONFIG_PATH="$CONFIG" \
    MYNEXUS_SERVER_INTERNAL_URL="localhost:$GRPC_PORT" \
    nohup python worker/src/server.py >"$WORKER_LOG" 2>&1 &
    echo $! >"$WORKER_PID"
  )
}

start_web() {
  log "[..] 启动 web-ui（Vite :$WEB_PORT）"
  (
    cd "$ROOT/web-ui"
    nohup npm run dev -- --port "$WEB_PORT" --strictPort >"$WEB_LOG" 2>&1 &
    echo $! >"$WEB_PID"
  )
}

kill_tree() {
  local pid="$1" signal="${2:-TERM}" child
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$child" "$signal"
  done
  kill -"$signal" "$pid" 2>/dev/null || true
}

stop_service() {
  local name="$1" pid_file="$2" pid
  if ! pid="$(service_pid "$pid_file")"; then
    rm -f "$pid_file"
    log "[--] $name 未在运行"
    return 0
  fi

  kill_tree "$pid" TERM
  for _ in {1..20}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill_tree "$pid" KILL
    log "[OK] 已强制停止 $name（pid $pid）"
  else
    log "[OK] 已停止 $name（pid $pid）"
  fi
  rm -f "$pid_file"
}

# PID 文件丢失时，按端口反查并确认进程名，避免误杀其它项目。
stop_listener() {
  local name="$1" port="$2" pattern="$3" pid cmd
  pid="$(port_pid "$port" || true)"
  [[ -n "$pid" ]] || return 0
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  case "$cmd" in
    *"$pattern"*)
      kill_tree "$pid" TERM
      for _ in {1..10}; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
      done
      kill -0 "$pid" 2>/dev/null && kill_tree "$pid" KILL
      log "[OK] 兜底停止 $name（端口 $port，pid $pid）"
      ;;
    *)
      log "[--] 端口 $port 被其它进程占用（pid $pid），已跳过：${cmd:-(未知进程)}"
      ;;
  esac
}

started_services=()

cleanup_started() {
  local name
  for ((i = ${#started_services[@]} - 1; i >= 0; i--)); do
    name="${started_services[$i]}"
    case "$name" in
      core) stop_service "core-api" "$CORE_PID" ;;
      worker) stop_service "worker" "$WORKER_PID" ;;
      web) stop_service "web-ui" "$WEB_PID" ;;
    esac
  done
}

up() {
  require_config
  mkdir -p "$TMP_DIR" "$PID_DIR"

  local core_running=0 worker_running=0 web_running=0
  service_running "$CORE_PID" && core_running=1
  service_running "$WORKER_PID" && worker_running=1
  service_running "$WEB_PID" && web_running=1

  require_commands \
    "$((1 - core_running))" \
    "$((1 - worker_running))" \
    "$((1 - web_running))"

  if ((core_running)); then
    log "[--] core-api 已在运行（pid $(service_pid "$CORE_PID")）"
  else
    require_port_free "core-api HTTP" "$API_PORT" || exit 1
    require_port_free "core-api gRPC" "$GRPC_PORT" || exit 1
  fi
  if ((worker_running)); then
    log "[--] worker 已在运行（pid $(service_pid "$WORKER_PID")）"
  else
    require_port_free "worker gRPC" "$WORKER_PORT" || exit 1
  fi
  if ((web_running)); then
    log "[--] web-ui 已在运行（pid $(service_pid "$WEB_PID")）"
  else
    require_port_free "web-ui" "$WEB_PORT" || exit 1
  fi

  if ((!core_running)); then
    start_core
    started_services+=("core")
    if ! wait_http "core-api" "http://127.0.0.1:$API_PORT/healthz" 120 "$CORE_PID"; then
      tail_log "$CORE_LOG"
      cleanup_started
      exit 1
    fi
  fi

  if ((!worker_running)); then
    start_worker
    started_services+=("worker")
    if ! wait_tcp "worker" "$WORKER_PORT" 120 "$WORKER_PID"; then
      tail_log "$WORKER_LOG"
      cleanup_started
      exit 1
    fi
  fi

  if ((!web_running)); then
    start_web
    started_services+=("web")
    if ! wait_http "web-ui" "http://127.0.0.1:$WEB_PORT/" 120 "$WEB_PID"; then
      tail_log "$WEB_LOG"
      cleanup_started
      exit 1
    fi
  fi

  log ""
  log "MyNexus 本地开发环境已就绪："
  log "  管理后台   http://localhost:$WEB_PORT  （默认账号 admin / admin，首次登录后请修改密码）"
  log "  Core API   http://localhost:$API_PORT  （健康检查 http://localhost:$API_PORT/healthz）"
  log "  Worker     grpc://localhost:$WORKER_PORT  （内部服务，不对外提供 HTTP）"
  log "  配置文件   $CONFIG"
  log "  日志文件   .tmp/core.log  .tmp/worker.log  .tmp/web.log"
  log "  进程 PID   .tmp/dev/*.pid"
  log "  查看日志   make dev-logs"
  log "  停止服务   make dev-down"
  log ""
}

down() {
  stop_service "web-ui" "$WEB_PID"
  stop_service "worker" "$WORKER_PID"
  stop_service "core-api" "$CORE_PID"

  # 兜底清理 PID 文件缺失、由旧版 make dev-up 或手工启动的实例。
  stop_listener "web-ui" "$WEB_PORT" "vite"
  stop_listener "worker" "$WORKER_PORT" "worker/src/server.py"
  stop_listener "core-api" "$API_PORT" "mynexus-api"
  stop_listener "core-api gRPC" "$GRPC_PORT" "mynexus-api"

  log "[OK] 本地开发环境已停止"
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  *)
    log "用法: $0 {up|down}（或 make dev-up / make dev-down）"
    exit 2
    ;;
esac
