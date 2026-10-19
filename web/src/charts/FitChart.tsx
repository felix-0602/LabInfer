import type { AnalysisResult } from "../types";
import { extent, fmt, linear, niceTicks, pad } from "./scale";

const W = 760, H = 420, M = { l: 64, r: 24, t: 24, b: 48 };

interface Props {
  analysis: AnalysisResult;
  highlight: Set<string>;
  anomalies: Set<string>;
  onHover: (pointId: string | null) => void;
}

// V–m 过原点拟合：点是 M4 transformed，直线按 M4 的 slope/intercept 画出
export function FitChart({ analysis, highlight, anomalies, onHover }: Props) {
  const tr = analysis.transformed[0];
  const fit = analysis.fits.find((f) => f.dataset_id === tr?.dataset_id) ?? analysis.fits[0];
  if (!tr || !fit) return <div className="empty dim">没有可画的拟合结果</div>;

  const xs = tr.points.map((p) => p.x), ys = tr.points.map((p) => p.y);
  const [x0, x1] = pad(extent(xs), 0.15), [y0, y1] = pad(extent(ys), 0.15);
  const sx = linear(x0, x1, M.l, W - M.r), sy = linear(y0, y1, H - M.b, M.t);
  const line = (x: number) => fit.slope * x + fit.intercept;
  const residual = new Map(analysis.residuals.map((r) => [r.point_id, r]));

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="滴定体积与称样量的过原点拟合">
      {niceTicks(y0, y1).map((t) => (
        <g key={"y" + t}>
          <line className="grid" x1={M.l} x2={W - M.r} y1={sy(t)} y2={sy(t)} />
          <text className="tick" x={M.l - 8} y={sy(t) + 4} textAnchor="end">{fmt(t, 2)}</text>
        </g>
      ))}
      {niceTicks(x0, x1).map((t) => (
        <g key={"x" + t}>
          <line className="grid" x1={sx(t)} x2={sx(t)} y1={M.t} y2={H - M.b} />
          <text className="tick" x={sx(t)} y={H - M.b + 18} textAnchor="middle">{fmt(t, 3)}</text>
        </g>
      ))}
      <line className="axis" x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} />
      <line className="axis" x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} />
      <text className="axis-label" x={W - M.r} y={H - 8} textAnchor="end">{tr.x_label} / {tr.x_unit}</text>
      <text className="axis-label" x={M.l} y={M.t - 8}>{tr.y_label} / {tr.y_unit}</text>

      <line className="fit-line" x1={sx(x0)} y1={sy(line(x0))} x2={sx(x1)} y2={sy(line(x1))} />
      <text className="fit-label" x={W - M.r - 8} y={sy(line(x1)) + 18} textAnchor="end">
        V = {fmt(fit.slope, 3)}·m　R² = {fit.r2}　n = {fit.n}
      </text>

      {tr.points.map((p) => {
        const on = highlight.has(p.point_id);
        const r = residual.get(p.point_id);
        return (
          <g key={p.point_id} onMouseEnter={() => onHover(p.point_id)} onMouseLeave={() => onHover(null)} className="pt-group">
            <line className="leader" x1={sx(p.x)} x2={sx(p.x)} y1={sy(p.y)} y2={sy(line(p.x))} />
            <circle className={"pt" + (r?.outlier || anomalies.has(p.point_id) ? " bad" : "") + (on ? " on" : "")} cx={sx(p.x)} cy={sy(p.y)} r={on ? 7 : 5} />
            {on && <circle className="ring" cx={sx(p.x)} cy={sy(p.y)} r={13} />}
            <text className="pt-label" x={sx(p.x) + 10} y={sy(p.y) - 10}>
              {p.point_id} · {p.y} mL{r ? ` · 残差 ${r.residual}` : ""}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
