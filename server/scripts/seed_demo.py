"""写入演示数据集与上下文。数值来源见 docs/demo-experiment-brief.md 与调研记录：
- ds_mine（标准系列）：团队现有记录页数据（待老师实验后替换为真数据）
- ds_lit：《大学化学》2019 图1(b) 印刷方程 Y=0.13933X+0.06103 生成的占位点（待 M2 真实取数替换）
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import CONTRACT_VERSION
from app.routers.contexts import TEMPLATES
from app.storage import Store


def build_demo_objects():
    mine = {
        "schema_version": CONTRACT_VERSION,
        "id": "ds_mine_demo",
        "source": "my_experiment",
        "meta": {"title": "水质氨氮 标准系列与样品（演示）", "doi": None, "figure": None,
                 "image_ref": None},
        "columns": [
            {"key": "c", "name": "氨氮浓度", "unit": "mg/L"},
            {"key": "A", "name": "吸光度", "unit": ""},
            {"key": "V", "name": "取样体积", "unit": "mL"},
            {"key": "dil", "name": "稀释倍数", "unit": ""},
        ],
        "rows": [
            {"id": "p0", "series": "std", "values": {"c": 0.0, "A": 0.0}, "verified": True},
            {"id": "p1", "series": "std", "values": {"c": 0.10, "A": 0.041}, "verified": True},
            {"id": "p2", "series": "std", "values": {"c": 0.20, "A": 0.082}, "verified": True},
            {"id": "p3", "series": "std", "values": {"c": 0.40, "A": 0.165}, "verified": True},
            {"id": "p4", "series": "std", "values": {"c": 0.80, "A": 0.328}, "verified": True},
            {"id": "p5", "series": "std", "values": {"c": 1.60, "A": 0.647}, "verified": True},
            {"id": "p6", "series": "std", "values": {"c": 2.00, "A": 0.805}, "verified": True},
            {"id": "s1a", "series": "sample:地表水1", "values": {"c": None, "A": 0.226, "V": 10, "dil": 1}, "verified": True},
            {"id": "s1b", "series": "sample:地表水1", "values": {"c": None, "A": 0.228, "V": 10, "dil": 1}, "verified": True},
            {"id": "s2", "series": "sample:自来水", "values": {"c": None, "A": 0.066, "V": 10, "dil": 1}, "verified": True},
            {"id": "s3", "series": "sample:污水稀释样", "values": {"c": None, "A": 0.484, "V": 5, "dil": 10}, "verified": True},
            {"id": "q1", "series": "qc:crm", "values": {"c": None, "A": 0.291}, "verified": True},
        ],
    }

    lit_rows = []
    for i, x in enumerate([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]):
        lit_rows.append({"id": f"L{i}", "series": "std",
                         "values": {"x": round(x, 2), "y": round(0.13933 * x + 0.06103, 4)},
                         "verified": True})
    lit = {
        "schema_version": CONTRACT_VERSION,
        "id": "ds_lit_dxhx",
        "source": "literature",
        "meta": {"title": "图1(b) 纳氏试剂法标准曲线（印刷方程生成的占位点，待 M2 取数替换）",
                 "doi": "10.3866/PKU.DXHX201807034", "figure": "图1(b)", "image_ref": None},
        "columns": [
            {"key": "x", "name": "氨氮浓度", "unit": "mg/L"},
            {"key": "y", "name": "吸光度", "unit": ""},
        ],
        "rows": lit_rows,
    }

    ctx = copy.deepcopy(TEMPLATES["tpl_ammonia_nessler"]["template"])
    ctx["id"] = "ctx_demo"
    ctx["datasets"] = {"mine": mine["id"]}
    ctx["reference"]["datasets"] = [{
        "dataset_id": lit["id"],
        "columns": {"concentration": "x", "signal": "y"},
        "space": "raw",
        "meta": {"doi": "10.3866/PKU.DXHX201807034", "figure": "图1(b)",
                 "note": "纳氏试剂法标准曲线"},
    }]
    return mine, lit, ctx


def main(store: Store | None = None):
    store = store or Store()
    mine, lit, ctx = build_demo_objects()
    store.put_dataset(mine)
    store.put_dataset(lit)
    store.put_context(ctx)
    print(f"已写入: {mine['id']}, {lit['id']}, {ctx['id']} (data dir: {store.root})")


if __name__ == "__main__":
    main()
