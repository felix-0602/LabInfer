import { useId } from "react";
import type { TitrationCurve } from "../types";
import { Band, Chart, Draw, Fade, Flash, Frame, GridX, GridY, Mark, Sim, type ChartInteraction } from "./reveal";
import { extent, linear, niceTicks, pad } from "./scale";

const W = 760, H = 420, M = { l: 56, r: 24, t: 44, b: 48 };

interface Props extends ChartInteraction {
  curve: TitrationCurve;
  // M6 推演曲线（同一 ΔV–pH 坐标），没有时不画
  simulated?: { x: number; y: number }[] | null;
  // 顶部滴定管刻度：把 ΔV 换回某一份在滴定管上的真实读数（veq = 该份计量点体积，mL）
  burette?: { point_id: string; veq: number } | null;
}

const path = (pts: { x: number; y: number }[], sx: (v: number) => number, sy: (v: number) => number) =>
  pts.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join("");

// 理论滴定曲线：学生只有终点体积，按 M4 给的 ΔV 放到曲线上；变色区用中性灰带，红色只给落在区外的终点
export function TitrationChart({ curve, highlight, anomalies, onHover, simulated, flash, burette }: Props) {
  const xs = [...curve.theory.map((p) => p.x), ...curve.endpoints.map((e) => e.dv_ml)];
  const ys = [...curve.theory.map((p) => p.y), ...curve.endpoints.map((e) => e.ph)];
  const [x0, x1] = pad(extent(xs), 0.04), [y0, y1] = pad(extent(ys), 0.06);
  const sx = linear(x0, x1, M.l, W - M.r), sy = linear(y0, y1, H - M.b, M.t);
  const [w0, w1] = curve.indicator.dv_window_ml;
  const [ph0, ph1] = curve.indicator.ph_range;

  // 文献曲线换到 ΔV 后通常比 ±2 mL 宽得多，裁到绘图区内
  const clip = useId();

  return (
    <Chart w={W} h={H} label="理论滴定曲线与各份标定终点">
      <clipPath id={clip}><rect x={M.l} y={M.t} width={W - M.l - M.r} height={H - M.t - M.b} /></clipPath>
      <Frame>
        <GridY ticks={niceTicks(y0, y1)} sy={sy} x0={M.l} x1={W - M.r} digits={1} />
        <GridX ticks={niceTicks(x0, x1)} sx={sx} y0={M.t} y1={H - M.b} />
      </Frame>
      {burette && (() => {
        const ticks: number[] = [];
        for (let r = Math.ceil((burette.veq + x0) * 10) / 10; r <= burette.veq + x1 + 1e-9; r += 0.1) ticks.push(+r.toFixed(1));
        return (
          <Frame className="burette">
            <line className="burette-base" x1={M.l} x2={W - M.r} y1={M.t} y2={M.t} />
            {ticks.map((r) => {
              const major = Math.abs(r * 2 - Math.round(r * 2)) < 1e-6;
              const x = sx(r - burette.veq);
              return (
                <g key={r}>
                  <line className="burette-tick" x1={x} x2={x} y1={M.t - (major ? 6 : 3)} y2={M.t} />
                  {major && <text className="tick" x={x} y={M.t - 10} textAnchor="middle">{r.toFixed(1)}</text>}
                </g>
              );
            })}
            <text className="tick burette-label" x={W - M.r} y={M.t - 26} textAnchor="end">BURETTE · {burette.point_id} · mL</text>
          </Frame>
        );
      })()}
      <Band>
        <rect className="window" x={sx(w0)} width={Math.max(1, sx(w1) - sx(w0))} y={sy(ph1)} height={Math.max(1, sy(ph0) - sy(ph1))} />
        <text className="band-label" x={sx(w1) + 6} y={sy(ph1) + 14}>{curve.indicator.name} 变色区 pH {ph0}–{ph1}</text>
        <line className="eq-line" x1={sx(0)} x2={sx(0)} y1={M.t} y2={H - M.b} />
        <text className="tick" x={sx(0) + 6} y={M.t + 12}>计量点 pH {curve.ph_eq}</text>
      </Band>

      <Frame>
        <line className="axis" x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} />
        <line className="axis" x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} />
        <text className="axis-label" x={W - M.r} y={H - 8} textAnchor="end">{curve.x_label} / {curve.x_unit}</text>
        <text className="axis-label" x={M.l + 8} y={M.t + 16}>{curve.y_label}</text>
      </Frame>

      <g clipPath={`url(#${clip})`}>
        <Fade>{curve.literature.map((l) => <path key={l.dataset_id} className="lit-line" d={path(l.points, sx, sy)} />)}</Fade>
        <Draw className="theory-line" d={path(curve.theory, sx, sy)} />
        {simulated && simulated.length > 1 && <Sim><path className="sim-curve" d={path(simulated, sx, sy)} /></Sim>}
      </g>

      {curve.endpoints.map((e, i) => {
        const on = highlight.has(e.point_id);
        const outside = e.dv_ml < w0 || e.dv_ml > w1;
        const bad = anomalies.has(e.point_id) || outside;
        return (
          <Mark key={e.point_id} i={i} id={e.point_id} onHover={onHover}>
            <circle className={"pt" + (on ? " on" : "")} cx={sx(e.dv_ml)} cy={sy(e.ph)} r={on ? 7 : 5} />
            {bad && <circle className="ring bad" cx={sx(e.dv_ml)} cy={sy(e.ph)} r={10} />}
            <Flash flash={flash} id={e.point_id} cx={sx(e.dv_ml)} cy={sy(e.ph)} bad={bad} />
            {on && <circle className="ring" cx={sx(e.dv_ml)} cy={sy(e.ph)} r={14} />}
            <text className={"pt-label" + (bad ? " bad" : "")} x={sx(e.dv_ml) + 12} y={sy(e.ph) - 8}>
              {e.point_id} · ΔV {e.dv_ml} mL · pH {e.ph}
            </text>
          </Mark>
        );
      })}
    </Chart>
  );
}
