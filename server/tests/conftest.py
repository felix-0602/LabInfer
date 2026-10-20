import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 测试对 m1/m2/m5 的 POST 远超限速阈值（TestClient 同源伪 IP），测试进程一律关限速
os.environ.setdefault("LABINFER_RATELIMIT", "0")
