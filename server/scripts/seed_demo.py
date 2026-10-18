"""写入演示数据集与上下文，并烘焙 M1 演示缓存。

数据来源（真实记录，不得编造）：
- 团队成员的实验数据记录页（武汉工程大学《分析化学实验》实验 3「HCl 溶液的标定
  及碱灰总碱度的测定」，2026-10 提供照片，即 design/assets/DEMO-01.jpg）。
- 方法与常数依据 GB/T 601-2016：基准无水碳酸钠 270~300 ℃ 灼烧至恒重，
  M(½Na₂CO₃) = 52.994（即 M(Na₂CO₃) = 105.99）；总碱度以 Na₂O 计，M(Na₂O) = 61.979。
- 手写记录页上的 c̄ = 0.1027、w̄ = 60.6%、相对平均偏差 1.33% / 2.1% 用于测试对账，
  与代码从原始 m/V 复算的结果一致（差异来自记录页的中间舍入）。
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cache import cache_put, sha256_file
from app.config import CONTRACT_VERSION
from app.routers.contexts import TEMPLATES
from app.storage import Store, store_from_env

DEMO_RECORD_IMAGE = Path(__file__).resolve().parent.parent.parent / "design" / "assets" / "DEMO-01.jpg"


def build_demo_objects():
    mine = {
        "schema_version": CONTRACT_VERSION,
        "id": "ds_mine_demo",
        "source": "my_experiment",
        "meta": {"title": "HCl 标定与碱灰总碱度 数据记录（演示）", "doi": None, "figure": None,
                 "image_ref": None},
        "columns": [
            {"key": "m", "name": "基准 Na₂CO₃ 质量", "unit": "g"},
            {"key": "V", "name": "HCl 滴定体积", "unit": "mL"},
            {"key": "ms", "name": "碱灰试样质量", "unit": "g"},
        ],
        "rows": [
            # 标定段：三份平行，称样量落在 GB/T 601-2016 的 0.15~0.2 g 设计区间
            {"id": "p1", "series": "std", "values": {"m": 0.1549, "V": 28.54}, "verified": True},
            {"id": "p2", "series": "std", "values": {"m": 0.1832, "V": 33.00}, "verified": True},
            {"id": "p3", "series": "std", "values": {"m": 0.1670, "V": 31.19}, "verified": True},
            # 测定段：碱灰 1.5919 g 定容 250 mL，每份移取 25.00 mL
            {"id": "s1", "series": "sample:碱灰", "values": {"V": 29.55, "ms": 1.5919}, "verified": True},
            {"id": "s2", "series": "sample:碱灰", "values": {"V": 31.29, "ms": 1.5919}, "verified": True},
            {"id": "s3", "series": "sample:碱灰", "values": {"V": 30.11, "ms": 1.5919}, "verified": True},
        ],
    }

    ctx = copy.deepcopy(TEMPLATES["tpl_alkali_titration"]["template"])
    ctx["id"] = "ctx_demo"
    ctx["datasets"] = {"mine": mine["id"]}
    return mine, ctx


def bake_m1_cache(mine: dict) -> str | None:
    """把记录页照片的识别结果烘焙进演示缓存：上传原图即命中，无需 VLM。"""
    if not DEMO_RECORD_IMAGE.exists():
        return None
    payload = copy.deepcopy(mine)
    payload.pop("id", None)
    payload.pop("schema_version", None)   # 由路由盖当前契约版本
    for r in payload["rows"]:
        r["verified"] = False
    # 记录页上 p1 的滴定体积有涂改痕迹（28.54），保留一个低置信格子演示校正交互
    payload["rows"][0]["confidence"] = {"m": 0.98, "V": 0.62}
    digest = sha256_file(DEMO_RECORD_IMAGE)
    cache_put("m1", digest, payload)
    return digest


def main(store: Store | None = None):
    store = store or store_from_env()   # 跟随 LABINFER_STORAGE，与 uvicorn 同后端
    mine, ctx = build_demo_objects()
    store.put_dataset(mine)
    store.put_context(ctx)
    digest = bake_m1_cache(mine)
    baked = f"，已烘焙 M1 演示缓存（sha256 {digest[:12]}…）" if digest else ""
    print(f"已写入: {mine['id']}, {ctx['id']}{baked} (data dir: {store.root})")


if __name__ == "__main__":
    main()
