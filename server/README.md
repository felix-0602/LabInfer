# LabInfer 后端

FastAPI 单进程服务，实现 contracts 0.6.0 定义的 `/api` 接口。存储有两个后端，默认 JSON 文件（`server/data/`，不入库），设 `LABINFER_STORAGE=sqlite` 切到 SQLite（`server/data/labinfer.sqlite3`，表结构见 [docs/sql.md](../docs/sql.md)），接口行为一致。演示缓存放 `server/demo_cache/`（入库，按图片 sha256 命名）。

## 环境（统一用 uv）

虚拟环境与依赖统一用 [uv](https://docs.astral.sh/uv/) 管理，不用 pip 直装（本机 pip 缓存损坏过，pypi 直连也不稳定，uv 加镜像一次通过）。pypi 直连不稳时加清华镜像。

```bash
cd server
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
# 网络不稳时：
uv pip install --python .venv/bin/python \
  --default-index https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

## 运行

```bash
. .venv/bin/activate
python -m scripts.seed_demo          # 写入演示数据集与上下文，并按 design/assets/DEMO-01.jpg 烘焙 M1 演示缓存
uvicorn app.main:app --reload --port 8000
```

演示时上传 `design/assets/DEMO-01.jpg`（真实数据记录页）即命中 M1 缓存，不依赖 VLM。

## 测试

```bash
python -m pytest tests -q
```

## 环境变量

见 `.env.example`。`LABINFER_STORAGE=sqlite` 启用 SQLite 后端；`LABINFER_DATA` 改数据目录。GLM key 缺失时 M5 降级为模板结论（确定性生成，演示保底也用它）；M1 未命中演示缓存且无 key 时返回 503。本机走 fake-ip 代理（域名全解析进 198.18.0.0/15）时设 `LABINFER_ALLOW_FAKEIP=1` 放行该段出网，其余拒绝规则不变（`app/llm.py`）。

## 边界

- 单用户，无并发保护；存储为原子写 JSON。
- 对外请求（VLM/LLM）仅 https，拒绝环回/私网/保留地址（`app/llm.py::validate_outbound_url`）。
- 计算全部在 `app/models/`（纯函数，numpy/scipy），AI 相关在 `app/llm.py` 与 `app/services/findings.py`，两者不交叉。
