# LabInfer 部署交接（目标：腾讯云服务器，公网 8081）

> 写给下一个会话：本文是部署的唯一信息源。服务器侧的准备（安全组、SSH、惯例）都已就绪，
> 你只需要决定容器形态、写 compose、跑部署。动完更新本文的「部署现状」一节。

## 1. 服务器与网络（已就绪，直接用）

- **SSH 别名 `myserver`**（本机 `~/.ssh/config` 已配好）：`106.52.67.72`，用户 `ubuntu`，密钥登录，`sudo docker` 免交互。`ssh myserver "命令"` 即可操作。
- **机器规格**：2 核 / 1.9GB 内存（日常可用约 1.1GB）/ 磁盘 40GB 空闲。跑 Python 后端 + 静态前端绰绰有余；
  **不要**在这台机器上跑本地大模型——LabInfer 的 VLM/LLM 走 GLM 云端 API，正好。
- **安全组已放行 TCP 8081**（来源 0.0.0.0/0，用户已在腾讯云控制台添加）。宿主机无额外防火墙拦截
  （同机 8080 端口的博客就是这条路径，直接可访问）。唯一要求：**服务监听 0.0.0.0:8081**（容器映射也算）。
- 端口占用现状：22 SSH / 80 zrelay（勿动）/ 8080 博客 / 1883·18083 EMQX。**8081 空闲**。
- 公网访问形态是裸 IP `http://106.52.67.72:8081/`，无需备案；以后想绑域名再说。

## 2. 服务器上已有的部署惯例（照抄即可）

同机博客项目（本机 `~/音乐/inward`）跑着一套成熟范式，结构直接复用：

```
服务器 ~/inward-compose/     compose 文件 + nginx.conf + api 代码（rsync 上去的）
      ~/inward-site/         前端构建产物
      ~/inward-data/         数据（博文 md + 媒体），不随部署覆盖
```

deploy 脚本模式：本地构建 → `rsync -az` 上服务器 → `ssh myserver "cd ~/xxx && sudo docker compose up -d --remove-orphans && sudo docker compose restart"`（**挂载文件改了必须 restart 容器才生效**，博客项目踩过这个坑）→ `curl` 健康检查。参考文件：`~/音乐/inward/scripts/deploy.sh`、`server/docker-compose.yml`。

## 3. LabInfer 的建议形态（单端口 8081 对外）

**已定型并落地**：单容器，FastAPI 同时伺服 API 与前端（`LABINFER_WEB_DIST` 门控的 StaticFiles
挂载，见 `server/app/main.py`），compose 映射 `8081:8000`。部署物全部入库：

- `server/Dockerfile`：python:3.12-slim + libglib（cv2 需要），启动即播种再起 uvicorn
  （**镜像源必须用腾讯云** `mirrors.cloud.tencent.com`：这台 CVM 访问 debian 官方源 ~11 分钟、
  清华 pypi 直接 403，Dockerfile 里有注释）
- `server/.dockerignore`：`.env`/`data`/`tests` 等绝不进镜像
- `deploy/docker-compose.yml`：`../labinfer-data:/data` 数据卷 + `web-dist`/`design` 只读挂载
- `deploy/deploy.sh`：本地 `npm run build` → rsync → 服务器 `compose build && up && restart`
  → 带重试的健康检查。GLM key 不经此脚本：首次部署时由本地 `server/.env` 经 ssh stdin
  写入服务器 `~/labinfer-compose/labinfer.env`（600 权限，compose `env_file` 引用）

- **GLM key**：`LABINFER_GLM_API_KEY` 用 compose 的 `environment:` 注入；**不要**把真实 key 写进被
  rsync 的文件里明文躺在服务器。无 key 也能跑（M5 模板结论 + DEMO 烘焙缓存），演示够用。
- **数据/识别缓存**：挂卷到 `~/labinfer-data`，容器重建不丢。
- compose 里 `restart: unless-stopped` 已配。

## 4. 安全提醒（重要，黑客松期间就要考虑）

8081 对全网开放，意味着：`/docs` 公开、任何写入接口公开、**配置了 GLM key 的话识别接口会烧你的
API 余额**（公网扫描器会找到开放端点）。三选一，按优先级：

1. FastAPI 加一个简单的 Bearer token（演示时给评委口令即可）；
2. 或腾讯云控制台把 8081 的来源从 0.0.0.0/0 改成常用 IP 段；
3. 至少给识别接口加简单限速。

**已落地第 3 档**：`server/app/ratelimit.py` 滑动窗口限速（线上验证过 429 生效）——
m1/m2/m5 的 POST 限 10 次/分/IP，其余 `/api` POST 限 60 次/分/IP，GET 不限。
`LABINFER_RATELIMIT=0` 可关（测试 conftest 已自动关）。演示结束后：关掉安全组规则或
`ssh myserver "cd ~/labinfer-compose && sudo docker compose down"`。

## 5. 上线验证清单

- [x] `curl http://106.52.67.72:8081/` 返回前端页面（LabInfer 工作台 HTML）
- [x] `/docs`（或 `/api/docs`）能打开（200）
- [x] 上传 `design/assets/DEMO-01.jpg`，无 key 走烘焙缓存出结果（201，`"cached":true`，瞬时）
- [x] 配 key 后 VLM 结论正常（重编码副本走真实出网：两段式整链 93.6s，样品行 V/ms 与记录页一致；
      期间产生了真实余额消耗；同一张重编码图二次上传命中运行时缓存秒回）
- [x] `ssh myserver "free -h; df -h /"` 内存磁盘正常（可用内存 1.2G、磁盘 39G 空闲、镜像 902MB）
- [x] 更新本文「部署现状」

## 6. 部署现状（每完成一次部署更新这里）

- 2026-10-20 **首次部署成功**，`http://106.52.67.72:8081/` 在线。
  - 部署物与代码改动收在分支 `release/v0.9.0`（正式版基线，与线上一致）。
  - 形态：单容器 `labinfer-api`（compose 管），8081→8000，FastAPI 伺服 API + 前端静态。
  - key 已注入：`~/labinfer-compose/labinfer.env`（600 权限，4 个变量，由本地 `server/.env`
    经 ssh stdin 写入；rsync/deploy.sh 均不碰它）。
  - 限速已启用并线上验证（15 连发第 11 个起 429）。
  - 部署方式：仓库 `deploy/deploy.sh`（本地构建前端 → rsync → 服务器 compose build/up/restart
    → 健康检查重试 30×2s）。改动代码后重跑该脚本即可。
  - 踩坑记录：清华 pypi 源从该 CVM 访问 403、debian 官方 apt 源 ~11 分钟 → Dockerfile 全用
    `mirrors.cloud.tencent.com`；rsync 目标的中间父目录不会自动创建，脚本里 `mkdir -p` 了
    `~/labinfer-compose/design`。
  - VLM 实测：单次视觉调用 ~6s，m1 整链（版面分析+逐表）约 90~120s，前端 fetch 无超时可等；
    演示主线建议走 DEMO-01 烘焙缓存（秒回），真机识别作为附加环节。
