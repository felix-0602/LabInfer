"""真实模型联调探针：M1–M7 全链路走一遍，输出逐模块结论。

不走演示缓存（上传照片重编码改字节），VLM/LLM 为真实出网调用。
用法（key 建议密文存放，解密进环境变量，见 server/README.md）：

  LABINFER_GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4 \
  LABINFER_GLM_API_KEY=$(openssl enc -d ... ) \
  LABINFER_ALLOW_FAKEIP=1 \
  python -m scripts.live_check
"""

import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 必须在 import app 之前：真实识别的烘焙缓存指向临时目录，不污染仓库的 demo_cache
os.environ.setdefault("LABINFER_DEMO_CACHE", tempfile.mkdtemp(prefix="labinfer-live-cache-"))

from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import create_app
from app.storage import Store
from scripts.seed_demo import DEMO_RECORD_IMAGE, main as seed

# 手写记录页的真值（团队数据记录页，docs 见 scripts/seed_demo.py 头注）
STD_TRUTH = [{"m": 0.1549, "V": 28.54}, {"m": 0.1832, "V": 33.00}, {"m": 0.1670, "V": 31.19}]
SAMPLE_TRUTH = [{"V": 29.55, "ms": 1.5919}, {"V": 31.29, "ms": 1.5919}, {"V": 30.11, "ms": 1.5919}]
TEMPLATE_FALLBACK_MARK = "基准 Na₂CO₃ 标定线性良好"   # 模板降级文案的特征句


def step(name):
    print(f"\n=== {name} ===", flush=True)
    return time.time()


def ok(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg, flush=True)
    return bool(cond)


def reencoded_photo() -> bytes:
    # 每次运行字节都不同（quality 随时间变化）：绕开演示缓存，也绕开上一轮烘焙的缓存
    img = Image.open(DEMO_RECORD_IMAGE)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80 + int(time.time()) % 10)
    return buf.getvalue()


def main() -> int:
    results = {}
    tmp = tempfile.mkdtemp(prefix="labinfer-live-")
    store = Store(tmp)
    seed(store)
    client = TestClient(create_app(store), raise_server_exceptions=False)

    t = step("M3 模板与上下文")
    templates = client.get("/api/m3/templates").json()
    ok(any(x["id"] == "tpl_alkali_titration" and x["status"] == "演示" for x in templates),
       f"模板列表 {len(templates)} 项，含演示模板 tpl_alkali_titration")
    ctx = client.post("/api/m3/contexts", json={"template_id": "tpl_alkali_titration"}).json()
    ok("id" in ctx, f"实例化上下文 {ctx.get('id')}")
    results["M3"] = time.time() - t

    t = step(f"M1 真实 VLM 识别（{settings.vlm_model}，照片重编码绕开缓存）")
    photo = reencoded_photo()
    r = client.post("/api/m1/records", data={"context_id": ctx["id"]},
                    files={"image": ("note-live.jpg", io.BytesIO(photo), "image/jpeg")})
    if r.status_code != 201:
        ok(False, f"M1 返回 {r.status_code}: {r.text[:200]}")
        return 1
    ds = r.json()
    ok(ds.get("cached") is not True, "未命中缓存（真实调用了 VLM）")
    print(f"  识别出 {len(ds['rows'])} 行:")
    total_cells = exact = 0
    mismatches = []
    std_rows = [x for x in ds["rows"] if x["series"] == "std"]
    sample_rows = [x for x in ds["rows"] if str(x["series"]).startswith("sample:")]
    for i, row in enumerate(std_rows):
        print(f"    {row['id']} {row['series']}: {row['values']}  conf={row.get('confidence')}")
        truth = STD_TRUTH[i] if i < len(STD_TRUTH) else {}
        for k, v in truth.items():
            total_cells += 1
            got = row["values"].get(k)
            if got is not None and abs(float(got) - v) < 5e-4:
                exact += 1
            else:
                mismatches.append(f"{row['id']}.{k}: 真值 {v}，识别 {got}")
    for i, row in enumerate(sample_rows):
        print(f"    {row['id']} {row['series']}: {row['values']}  conf={row.get('confidence')}")
        truth = SAMPLE_TRUTH[i] if i < len(SAMPLE_TRUTH) else {}
        for k, v in truth.items():
            total_cells += 1
            got = row["values"].get(k)
            if got is not None and abs(float(got) - v) < 5e-4:
                exact += 1
            else:
                mismatches.append(f"{row['id']}.{k}: 真值 {v}，识别 {got}")
    ok(len(std_rows) == 3 and len(sample_rows) == 3, f"行结构: 标定 {len(std_rows)} 行 / 测定 {len(sample_rows)} 行")
    print(f"  数字格准确率: {exact}/{total_cells}")
    for m in mismatches:
        print(f"    偏差 {m}")
    results["M1"] = time.time() - t
    results["m1_accuracy"] = f"{exact}/{total_cells}"

    t = step("手动校正（用户在 M8 补全/修正识别结果，PUT 数据集）")
    # 模拟用户操作：识别漏了整张标定表时补行，识别错的格子改对，然后锁定
    corrected = []
    for i, truth in enumerate(STD_TRUTH):
        corrected.append({"id": f"p{i + 1}", "series": "std", "values": dict(truth),
                          "confidence": {}, "verified": True})
    for i, truth in enumerate(SAMPLE_TRUTH):
        corrected.append({"id": f"s{i + 1}", "series": "sample:碱灰", "values": dict(truth),
                          "confidence": {}, "verified": True})
    ds["rows"] = corrected
    r = client.put(f"/api/datasets/{ds['id']}", json=ds)
    ok(r.status_code == 200 and len(r.json()["rows"]) == 6
       and all(x["verified"] for x in r.json()["rows"]), "6 行（补全后）全部校正并锁定")
    results["校正"] = time.time() - t

    t = step("M4 分析（代码计算，无模型参与）")
    r = client.post("/api/m4/analyze", json={"context_id": ctx["id"]})
    analysis = r.json()
    d = analysis["fits"][0]["derived"]
    ok(abs(d["c_hcl"] - 0.1027) < 0.0002, f"c̄(HCl) = {d['c_hcl']:.6f}（记录页 0.1027）")
    ok(abs(d["w_na2o_mean_pct"] - 60.63) < 0.02, f"w̄(Na₂O) = {d['w_na2o_mean_pct']:.4f}%（记录页 60.63%）")
    qc = {q["rule_id"]: q["pass"] for q in analysis["qc_results"]}
    ok(qc.get("standardization_rpad") is False and qc.get("parallel_rpd") is False,
       f"两条精密度质控按预期未通过（1.31% / 2.14% > 0.2%），格拉布斯 {qc.get('outlier_grubbs')}")
    results["M4"] = time.time() - t

    t = step(f"M5 真实 LLM 解读（{settings.llm_model}，两段式 + 溯源校验）")
    r = client.post("/api/m5/findings", json={"context_id": ctx["id"]})
    text = r.text
    findings, event = [], ""
    for line in text.splitlines():
        if line.startswith("event: "):
            event = line[len("event: "):].strip()
        elif line.startswith("data: {") and event == "finding":
            findings.append(json.loads(line[len("data: "):]))
    ok(len(findings) >= 4, f"收到 {len(findings)} 条结论")
    ok(all(f.get("evidence") for f in findings), "每条结论都有 evidence")
    ok(TEMPLATE_FALLBACK_MARK not in text, "走的是 LLM 输出而非模板降级")
    types = [f["type"] for f in findings]
    ok("anomaly" in types and "conclusion" in types, f"类型分布 {types}")
    for f in findings[:3]:
        print(f"    [{f['type']}] {f['text'][:90]}")
    results["M5"] = time.time() - t
    results["m5_count"] = len(findings)

    t = step("M6 参数推演")
    r = client.post("/api/m6/simulate", json={
        "context_id": ctx["id"], "finding_id": "f", "from": -2, "to": 0,
        "param": "titrant_volume_delta", "unit": "mL"})
    sim = r.json()
    ok(r.status_code == 200 and len(sim.get("curve", [])) == 20,
       f"ΔV=-2 → w={sim['curve'][0]['y']}%（少滴 2 mL 回落约 4 个百分点）")
    results["M6"] = time.time() - t

    t = step("M7 导出")
    r = client.post("/api/m7/export", json={"context_id": ctx["id"], "format": "md"})
    md = r.text
    ok("HCl 标定" in md and "总碱度" in md and "60.63" in md or "60.6" in md,
       "Markdown 段落含标定、总碱度与均值")
    r = client.post("/api/m7/export", json={"context_id": ctx["id"], "format": "docx"})
    ok(r.status_code == 200 and r.content[:2] == b"PK", "docx 为合法 Word 文件")
    results["M7"] = time.time() - t

    t = step("演示保底快照")
    r = client.get(f"/api/snapshot/{ctx['id']}")
    snap = r.json()
    ok(snap["schema_version"] == "0.6.0" and snap["findings"] and snap["analysis"]["fits"],
       "快照含上下文、数据集、分析与结论")
    results["snapshot"] = time.time() - t

    print("\n=== 逐模块耗时 ===")
    for k, v in results.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.1f}s")
    print("\n数据目录:", tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
