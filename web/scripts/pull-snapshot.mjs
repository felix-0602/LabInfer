// 拉取演示保底快照，存为影子文件 src/shadow/snapshot.json（契约：M8 构建时拉取一次）。
// 用法：后端起在 LABINFER_API（默认 http://127.0.0.1:8000）并已执行 seed_demo 后，npm run snapshot
import { writeFile } from "node:fs/promises";

const base = process.env.LABINFER_API ?? "http://127.0.0.1:8000";
const ctx = process.env.LABINFER_DEMO_CONTEXT ?? "ctx_demo";
const post = (path, body) =>
  fetch(base + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// 快照需要分析结果与结论，先按正常流程跑一遍 M4、M5（M5 无 key 时为确定性模板结论）
const a = await post("/api/m4/analyze", { context_id: ctx });
if (!a.ok) throw new Error(`M4 analyze 失败: ${a.status}`);
await (await post("/api/m5/findings", { context_id: ctx })).text();

const res = await fetch(`${base}/api/snapshot/${ctx}`);
if (!res.ok) throw new Error(`snapshot 失败: ${res.status}`);
const snap = await res.json();
const out = new URL("../src/shadow/snapshot.json", import.meta.url);
await writeFile(out, JSON.stringify(snap, null, 1) + "\n");
console.log(`已写入 ${out.pathname}：${snap.datasets.length} 个数据集，${snap.findings.length} 条结论`);

// 可推演的结论顺带把 M6 推演结果也存下来，演示保底时推演面板照样能展开、拖滑块（数值全部来自 M6，前端不插值）
const sims = {};
for (const f of snap.findings) {
  if (!f.simulatable || !f.simulation) continue;
  const r = await post("/api/m6/simulate", { schema_version: "0.6.0", context_id: ctx, finding_id: f.id, ...f.simulation });
  if (!r.ok) throw new Error(`M6 simulate ${f.id} 失败: ${r.status}`);
  sims[f.id] = await r.json();
}
const simOut = new URL("../src/shadow/simulations.json", import.meta.url);
await writeFile(simOut, JSON.stringify(sims, null, 1) + "\n");
console.log(`已写入 ${simOut.pathname}：${Object.keys(sims).length} 条推演`);
