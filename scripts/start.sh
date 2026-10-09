#!/bin/sh
# =====================================================================
# 启动 Myolotrain（docker compose），宿主机端口被占用时自动顺延。
#
# 用法：scripts/start.sh [传给 docker compose up 的额外参数，例如 --build]
#
# 端口规则：
#   1. 首选端口 = .env 中的 APP_PORT（默认 8000）；如果上次因冲突顺延过、且 APP_PORT 没改，
#      优先复用上次实际使用的端口（记录在 .app_port），保证调用方的地址尽量不变；
#   2. 端口被其他程序占用就 +1，最多尝试 APP_PORT_MAX_TRIES 个（默认 20）；
#      本服务自己的容器占着的端口不算冲突；
#   3. APP_PORT_STRICT=true 时不顺延，冲突直接报错退出；
#   4. 启动成功后打印实际访问地址，并等待服务就绪。
# GPU：USE_GPU=auto（默认，检测到 NVIDIA 环境就叠加 docker-compose.gpu.yml）/ true / false
# =====================================================================
set -eu

cd "$(dirname "$0")/.."

# 读取配置：环境变量优先，其次 .env，最后默认值。只读这几个键，不 source 整个 .env
conf() {
  key="$1"; default="$2"
  val="$(printenv "$key" 2>/dev/null || true)"
  if [ -z "$val" ] && [ -f .env ]; then
    val="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" .env | tail -n 1 | cut -d= -f2- \
      | sed -e 's/[[:space:]]#.*$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/" | tr -d '\r')"
  fi
  if [ -n "$val" ]; then echo "$val"; else echo "$default"; fi
}

REQUESTED_PORT="$(conf APP_PORT 8000)"
MAX_TRIES="$(conf APP_PORT_MAX_TRIES 20)"
STRICT="$(conf APP_PORT_STRICT false)"
USE_GPU="$(conf USE_GPU auto)"
PORT_FILE=.app_port

if [ ! -f .env ]; then
  echo "错误：缺少 .env。请先执行 cp .env.example .env 并填写 SECRET_KEY、POSTGRES_PASSWORD" >&2
  exit 1
fi

# docker compose v2 优先，兼容旧版 docker-compose
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "错误：未找到 docker compose" >&2
  exit 1
fi

# GPU 判断：需要驱动（nvidia-smi 能列出 GPU）且 Docker 装了 NVIDIA 运行时
gpu_available() {
  command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1 || return 1
  command -v nvidia-container-cli >/dev/null 2>&1 && return 0
  docker info 2>/dev/null | grep -qi nvidia
}
COMPOSE_FILES="-f docker-compose.yml"
case "$USE_GPU" in
  true|1|yes) COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.gpu.yml" ;;
  false|0|no) ;;
  *) if gpu_available; then COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.gpu.yml"; fi ;;
esac
case "$COMPOSE_FILES" in
  *gpu*) echo "GPU：已启用" ;;
  *) echo "GPU：未启用（未检测到 NVIDIA 驱动或 nvidia-container-toolkit；训练将使用 CPU）" ;;
esac

# 端口是否已有程序在监听
port_in_use() {
  if command -v ss >/dev/null 2>&1; then
    [ -n "$(ss -Hltn "sport = :$1" 2>/dev/null)" ]
  elif command -v netstat >/dev/null 2>&1; then
    netstat -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$1\$"
  else
    return 1  # 无法预检，交给 docker 报错后再顺延
  fi
}

# 本服务的容器当前占着的宿主机端口（重复执行脚本时，自己占着的端口不算冲突）
OWN_PORT="$($COMPOSE $COMPOSE_FILES port app 8000 2>/dev/null | head -n 1 | sed 's/.*://' || true)"

# 上次记录：第一行是当时的 APP_PORT，第二行是实际使用的端口
LAST_REQUESTED=""; LAST_ACTUAL=""
if [ -f "$PORT_FILE" ]; then
  LAST_REQUESTED="$(sed -n 1p "$PORT_FILE" | tr -d '\r')"
  LAST_ACTUAL="$(sed -n 2p "$PORT_FILE" | tr -d '\r')"
fi
if [ "$LAST_REQUESTED" = "$REQUESTED_PORT" ] && [ -n "$LAST_ACTUAL" ]; then
  START_PORT="$LAST_ACTUAL"
else
  START_PORT="$REQUESTED_PORT"
fi
case "$STRICT" in true|1|yes) START_PORT="$REQUESTED_PORT"; MAX_TRIES=1 ;; esac

port="$START_PORT"
tries=0
chosen=""
while [ "$tries" -lt "$MAX_TRIES" ]; do
  tries=$((tries + 1))
  if [ "$port" != "$OWN_PORT" ] && port_in_use "$port"; then
    echo "端口 $port 已被占用"
    port=$((port + 1))
    continue
  fi
  echo "使用端口 $port 启动..."
  # shellcheck disable=SC2086
  if out="$(APP_PORT="$port" $COMPOSE $COMPOSE_FILES up -d "$@" 2>&1)"; then
    echo "$out"
    chosen="$port"
    break
  fi
  echo "$out"
  # 预检之后端口才被抢占、或被系统保留（预检看不到），docker 会在这里报错；其他错误直接退出
  if echo "$out" | grep -Eqi "port is already allocated|address already in use|bind.*(failed|forbidden)|ports are not available"; then
    if [ "$tries" -lt "$MAX_TRIES" ]; then echo "端口 $port 绑定失败，尝试下一个"; else echo "端口 $port 绑定失败"; fi
    port=$((port + 1))
    continue
  fi
  echo "启动失败（非端口冲突），请检查上面的输出" >&2
  exit 1
done

if [ -z "$chosen" ]; then
  case "$STRICT" in
    true|1|yes) echo "错误：端口 $REQUESTED_PORT 已被占用，且 APP_PORT_STRICT=true 不允许顺延" >&2 ;;
    *) echo "错误：端口 $START_PORT~$((START_PORT + MAX_TRIES - 1)) 全部被占用，请释放端口或调大 APP_PORT_MAX_TRIES" >&2 ;;
  esac
  exit 1
fi

printf '%s\n%s\n' "$REQUESTED_PORT" "$chosen" > "$PORT_FILE"

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "$HOST_IP" ] || HOST_IP="<服务器IP>"

echo "============================================================"
if [ "$chosen" != "$REQUESTED_PORT" ] && [ "$chosen" = "$START_PORT" ]; then
  echo "注意：沿用上次顺延后的端口 $chosen（首选端口 $REQUESTED_PORT 当时被占用）"
  echo "      如需改回首选端口，删除 $PORT_FILE 后重新执行本脚本"
elif [ "$chosen" != "$REQUESTED_PORT" ]; then
  echo "注意：端口 $START_PORT 被占用，本次使用端口 $chosen"
  echo "      接口调用方和 PUBLIC_BASE_URL 需要使用新端口"
fi
if [ -n "$LAST_ACTUAL" ] && [ "$LAST_ACTUAL" != "$chosen" ]; then
  echo "注意：端口与上次（$LAST_ACTUAL）不同"
fi
echo "控制台:   http://$HOST_IP:$chosen/"
echo "健康检查: http://$HOST_IP:$chosen/api/health"
echo "实际端口已记录到 $PORT_FILE"
echo "============================================================"

# 等待服务就绪（首次启动要初始化数据库，可能需要一两分钟）。START_WAIT_SECONDS=0 跳过等待
WAIT_SECONDS="$(conf START_WAIT_SECONDS 180)"
if [ "$WAIT_SECONDS" -gt 0 ] && command -v curl >/dev/null 2>&1; then
  printf '等待服务就绪'
  waited=0
  while [ "$waited" -lt "$WAIT_SECONDS" ]; do
    if curl -fsS "http://127.0.0.1:$chosen/api/health" >/dev/null 2>&1; then
      echo " 已就绪"
      exit 0
    fi
    printf '.'
    sleep 2
    waited=$((waited + 2))
  done
  echo ""
  echo "服务 ${WAIT_SECONDS} 秒内未就绪，请查看日志：$COMPOSE $COMPOSE_FILES logs -f app" >&2
  exit 1
fi
