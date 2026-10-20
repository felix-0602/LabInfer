#!/usr/bin/env bash
# 部署 LabInfer：本地构建前端 → rsync（后端源码 / 前端产物 / 演示图 / compose）
# → 服务器 compose build + up + restart → curl 健康检查。
# GLM key 在服务器 ~/labinfer-compose/labinfer.env（首次由本地 server/.env 经
# ssh stdin 写入，见 DEPLOY.md；本脚本不传输、不覆盖它）。
# 数据与识别缓存在服务器 ~/labinfer-data，不随部署覆盖。
set -euo pipefail
cd "$(dirname "$0")/.."

( cd web && npm run build )

ssh -o BatchMode=yes myserver "mkdir -p ~/labinfer-compose/design ~/labinfer-data && touch ~/labinfer-compose/labinfer.env"
rsync -az --delete \
  --exclude .env --exclude .venv --exclude data --exclude tests \
  --exclude .pytest_cache --exclude .mimosa --exclude .worktrees --exclude __pycache__ \
  server/ myserver:labinfer-compose/server/
rsync -az --delete web/dist/ myserver:labinfer-compose/web-dist/
rsync -az --delete --exclude lit-candidates design/assets/ myserver:labinfer-compose/design/assets/
rsync -az deploy/docker-compose.yml myserver:labinfer-compose/

# 镜像在服务器上构建；挂载文件（web-dist 等）改动必须 restart 容器才生效（博客踩过的坑）
ssh -o BatchMode=yes myserver "cd ~/labinfer-compose && sudo docker compose build && sudo docker compose up -d --remove-orphans && sudo docker compose restart api"

# 容器 restart 后播种+启动要几秒，健康检查带重试
for i in $(seq 1 30); do
  curl -fsS --max-time 5 http://106.52.67.72:8081/api/health >/dev/null 2>&1 && break
  [ "$i" = 30 ] && { echo "健康检查超时" >&2; exit 1; }
  sleep 2
done
curl -fsS http://106.52.67.72:8081/api/health && echo
echo "已部署 → http://106.52.67.72:8081/   接口文档 → http://106.52.67.72:8081/docs"
