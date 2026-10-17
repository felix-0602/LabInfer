# LabInfer 后端

FastAPI 单进程服务，实现 contracts 0.3.0 定义的 `/api` 接口。数据集与实验上下文存 JSON 文件（`server/data/`，不入库）；演示缓存放 `server/demo_cache/`（入库，按图片 sha256 命名）。

## 运行

```bash
cd server
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m scripts.seed_demo          # 写入演示数据集与上下文
uvicorn app.main:app --reload --port 8000
```

## 测试

```bash
python -m pytest tests -q
```

## 环境变量

见 `.env.example`。GLM key 缺失时 M5 降级为模板结论（确定性生成，演示保底也用它）；M1 未命中演示缓存且无 key 时返回 503。

## 边界

- 单用户，无并发保护；存储为原子写 JSON。
- 对外请求（VLM/LLM）仅 https，拒绝环回/私网/保留地址（`app/llm.py::validate_outbound_url`）。
- 计算全部在 `app/models/`（纯函数，numpy/scipy），AI 相关在 `app/llm.py` 与 `app/services/findings.py`，两者不交叉。
