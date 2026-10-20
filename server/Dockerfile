# LabInfer 后端：FastAPI 单容器（API + 前端静态同端口，见 DEPLOY.md 第 3 节）。
# 依赖层单独 COPY，代码改动不触发重装。tuna 镜像源：国内服务器拉 wheels 快。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# opencv-python-headless 在 slim 上仍需 libglib2.0-0 才能 import cv2
# 镜像源都用腾讯云：这台 CVM 访问 debian 官方源要 ~11 分钟、清华 pypi 返回 403
RUN sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g' /etc/apt/sources.list.d/debian.sources \
 && apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -i https://mirrors.cloud.tencent.com/pypi/simple -r requirements.txt

COPY . .

EXPOSE 8000
# 启动即播种演示数据（幂等，覆盖写），再起服务；监听必须 0.0.0.0 才能被端口映射到公网
CMD ["sh", "-c", "python -m scripts.seed_demo && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
