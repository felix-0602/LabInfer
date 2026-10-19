import type { TitrationCurve } from "../types";
import { extent, fmt, linear, niceTicks, pad } from "./scale";

const W = 760, H = 420, M = { l: 56, r: 24, t: 24, b: 48 };

interface Props {
  curve: TitrationCurve;
  highlight: Set<string>;
  anomalies: Set<string>;
  onHover: (pointId: string | null) => void;
  // M6 推演曲线（同一 ΔV–pH 坐标），没有时不画
  simulated?: { x: number; y: number }[] | null;
}

const path = (pts: { x: number; y: number }[], sx: (v: number) => number, sy: (v: number) => number) =>
  pts.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join("");

// 理论滴定曲线：学生只有终点体积，按 M4 给的 ΔV 放到曲线上；变色区用中性灰带，红色只给落在区外的终点
export function TitrationChart({ curve, highlight, anomalies, onHover, simulated }: Props) {
  const xs = [...curve.theory.map((p) => p.x), ...curve.endpoints.map((e) => e.dv_ml)];
  const ys = [...curve.theory.map((p) => p.y), ...curve.endpoints.map((e) => e.ph)];
  const [x0, x1] = pad(extent(xs), 0.04), [y0, y1] = pad(extent(ys), 0.06);
  const sx = linear(x0, x1, M.l, W - M.r), sy = linear(y0, y1, H - M.b, M.t);
  const [w0, w1] = curve.indicator.dv_window_ml;
  const [ph0, ph1] = curve.indicator.ph_range;

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="理论滴定曲线与各份标定终点">
      {niceTicks(y0, y1).map((t) => (
        <g key={"y" + t}>
          <line className="grid" x1={M.l} x2={W - M.r} y1={sy(t)} y2={sy(t)} />
          <text className="tick" x={M.l - 8} y={sy(t) + 4} textAnchor="end">{fmt(t, 1)}</text>
        </g>
      ))}
      {niceTicks(x0, x1).map((t) => (
        <g key={"x" + t}>
          <line className="grid" x1={sx(t)} x2={sx(t)} y1={M.t} y2={H - M.b} />
          <text className="tick" x={sx(t)} y={H - M.b + 18} textAnchor="middle">{fmt(t, 2)}</text>
        </g>
      ))}
      <rect className="window" x={sx(w0)} width={Math.max(1, sx(w1) - sx(w0))} y={sy(ph1)} height={Math.max(1, sy(ph0) - sy(ph1))} />
      <text className="band-label" x={sx(w1) + 6} y={sy(ph1) + 14}>{curve.indicator.name} 变色区 pH {ph0}–{ph1}</text>
      <line className="eq-line" x1={sx(0)} x2={sx(0)} y1={M.t} y2={H - M.b} />
      <text className="tick" x={sx(0) + 6} y={M.t + 12}>计量点 pH {curve.ph_eq}</text>

      <line className="axis" x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} />
      <line className="axis" x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} />
      <text className="axis-label" x={W - M.r} y={H - 8} textAnchor="end">{curve.x_label} / {curve.x_unit}</text>
      <text className="axis-label" x={M.l} y={M.t - 8}>{curve.y_label}</text>

      {curve.literature.map((l) => <path key={l.dataset_id} className="lit-line" d={path(l.points, sx, sy)} />)}
      <path className="theory-line" d={path(curve.theory, sx, sy)} />
      {simulated && simulated.length > 1 && <path className="sim-curve" d={path(simulated, sx, sy)} />}

      {curve.endpoints.map((e) => {
        const on = highlight.has(e.point_id);
        const outside = e.dv_ml < w0 || e.dv_ml > w1;
        const bad = anomalies.has(e.point_id) || outside;
        return (
          <g key={e.point_id} className="pt-group" onMouseEnter={() => onHover(e.point_id)} onMouseLeave={() => onHover(null)}>
            <circle className={"pt" + (on ? " on" : "")} cx={sx(e.dv_ml)} cy={sy(e.ph)} r={on ? 7 : 5} />
            {bad && <circle className="ring bad" cx={sx(e.dv_ml)} cy={sy(e.ph)} r={10} />}
            {on && <circle className="ring" cx={sx(e.dv_ml)} cy={sy(e.ph)} r={14} />}
            <text className={"pt-label" + (bad ? " bad" : "")} x={sx(e.dv_ml) + 12} y={sy(e.ph) - 8}>
              {e.point_id} · ΔV {e.dv_ml} mL · pH {e.ph}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
