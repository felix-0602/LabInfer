import type { Simulation, Snapshot } from "./types";

// 影子快照由 `npm run snapshot` 从 GET /api/snapshot/{context_id} 拉取后入库（演示保底需要提交）。
// 按需加载，正常联网时不进首屏包。
export async function loadShadow(): Promise<Snapshot> {
  const mod = await import("./shadow/snapshot.json");
  return mod.default as unknown as Snapshot;
}

// 演示保底的推演结果：同一次拉取时由 M6 算好（按结论 id 索引），没有后端也能展开推演
export async function loadShadowSims(): Promise<Record<string, Simulation>> {
  const mod = await import("./shadow/simulations.json");
  return mod.default as unknown as Record<string, Simulation>;
}
