#!/usr/bin/env bash
# LabInfer 一键启动：后端 FastAPI(:8000) + 前端 Vite(:5173，/api 代理到后端)。
#
# 首次运行自动装依赖：后端 uv venv + requirements.txt（直连失败自动切清华镜像），
# 前端 npm install。有 server/.env 会自动加载（GLM key 等）；没有也能起——
# M5 降级为模板结论，M1/M2 演示图走烘焙缓存，不依赖模型。
set -euo pipefail
cd "$(dirname "$0")"

usage() {
  cat <<'EOF'
用法：./start.sh [选项]

  （无参数）         前后端一起起，Ctrl+C 一起停
  --backend, -b      只起后端（:8000）
  --frontend, -f     只起前端（:5173）
  --no-seed          跳过演示数据播种（默认每次启动写入/覆盖演示数据与识别缓存）
  --reload           后端热重载（开发用）
  -h, --help         本帮助
EOF
}

MODE=both SEED=1 RELOAD=""
for arg in "$@"; do
  case "$arg" in
    --backend|-b)  MODE=backend ;;
    --frontend|-f) MODE=frontend ;;
    --no-seed)     SEED=0 ;;
    --reload)      RELOAD="--reload" ;;
    -h|--help)     usage; exit 0 ;;
    *) printf '未知参数: %s\n\n' "$arg" >&2; usage >&2; exit 2 ;;
  esac
done

log() { printf '\033[36m[start]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[start]\033[0m %s\n' "$*" >&2; exit 1; }

port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

BACKEND_PID=""
cleanup() {
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

setup_backend() {
  command -v uv >/dev/null || die "缺 uv（依赖统一用它装，安装见 server/README.md）"
  cd server
  if [ ! -x .venv/bin/python ]; then
    log "创建后端虚拟环境 server/.venv"
    uv venv .venv
  fi
  log "安装后端依赖（uv pip install -r requirements.txt）"
  if ! uv pip install --python .venv/bin/python -q -r requirements.txt; then
    log "pypi 直连失败，切清华镜像重试"
    uv pip install --python .venv/bin/python -q \
      --default-index https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
  fi
  if [ -f .env ]; then
    set -a; . ./.env; set +a
    log "已加载 server/.env"
  fi
  if [ "$SEED" = 1 ]; then
    log "写入演示数据与识别缓存（python -m scripts.seed_demo）"
    .venv/bin/python -m scripts.seed_demo
  fi
  cd ..
}

setup_frontend() {
  command -v npm >/dev/null || die "缺 node/npm（前端 Vite + React 需要）"
  cd web
  if [ ! -d node_modules ]; then
    log "安装前端依赖（npm install，首次较慢）"
    npm install --no-fund --no-audit
  fi
  cd ..
}

if [ "$MODE" != frontend ]; then
  if port_busy 8000; then
    die "8000 端口已被占用（后端可能已在跑）。先停旧进程，或用 ./start.sh --frontend 只起前端"
  fi
  setup_backend
  log "后端 → http://127.0.0.1:8000 （接口文档 /docs，健康检查 /api/health）"
  ( cd server && exec .venv/bin/python -m uvicorn app.main:app --port 8000 $RELOAD ) &
  BACKEND_PID=$!
fi

if [ "$MODE" != backend ]; then
  setup_frontend
  log "前端 → http://127.0.0.1:5173 （/api 由 Vite 代理到 8000）"
  cd web
  npm run dev          # 占前台；退出（含 Ctrl+C）后由 EXIT 钩子停掉后台后端
else
  wait "$BACKEND_PID"  # 只起后端：跟着 uvicorn 走
fi
