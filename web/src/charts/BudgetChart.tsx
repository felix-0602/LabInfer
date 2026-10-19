import type { ErrorBudget } from "../types";
import { Bar, Chart, Fade, GrowRect } from "./reveal";
import { fmt, linear } from "./scale";

const W = 760, H = 420, M = { l: 180, r: 96, t: 32, b: 40 };

// 误差预算：每项仪器误差、仪器可解释的相对偏差、实测相对平均偏差，同一横轴（%）对比
export function BudgetChart({ budget }: { budget: ErrorBudget }) {
  const rows = [
    ...budget.items.map((it) => ({ label: `${it.source} · ${it.subject.point_id}`, v: it.rel, cls: "bar" })),
    { label: "仪器可解释", v: budget.expected_rel_dev, cls: "bar strong" },
    { label: "实测相对平均偏差", v: budget.observed_rel_dev, cls: "bar bad" },
  ];
  const max = Math.max(...rows.map((r) => r.v)) * 1.1 || 1;
  const sx = linear(0, max, M.l, W - M.r);
  const rowH = Math.min(36, (H - M.t - M.b) / rows.length);

  return (
    <Chart w={W} h={H} label="误差预算">
      <Fade><text className="axis-label" x={M.l} y={M.t - 12}>相对偏差 / %　实测是仪器可解释的 {budget.ratio} 倍</text></Fade>
      {rows.map((r, i) => {
        const y = M.t + i * rowH;
        return (
          <Bar key={r.label + i} i={i}>
            <text className="tick" x={M.l - 10} y={y + rowH / 2 + 4} textAnchor="end">{r.label}</text>
            <GrowRect className={r.cls} x={M.l} y={y + 6} width={Math.max(1, sx(r.v) - M.l)} height={rowH - 12} />
            <text className="pt-label" x={sx(r.v) + 6} y={y + rowH / 2 + 4}>{fmt(r.v * 100, 2)}%</text>
          </Bar>
        );
      })}
      <line className="axis" x1={M.l} x2={M.l} y1={M.t} y2={M.t + rows.length * rowH} />
    </Chart>
  );
}
