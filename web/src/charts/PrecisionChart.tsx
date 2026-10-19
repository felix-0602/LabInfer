import type { AnalysisResult } from "../types";
import { Band, Chart, Fade, Flash, Frame, GridY, Mark, Sim, type ChartInteraction } from "./reveal";
import { fmt, linear, niceTicks, pad } from "./scale";

const W = 760, H = 420, M = { l: 64, r: 150, t: 24, b: 48 };

interface Props extends ChartInteraction {
  analysis: AnalysisResult;
  // M6 推演：某个平行份在调整参数后的预测值（直接取 Simulation.curve 的点）
  projection?: { point_id: string; y: number; label: string } | null;
}

// 平行样精密度：各份报告值 ± U95、平均值、允许带（来自 qc 规则限值）、理论上限
export function PrecisionChart({ analysis, highlight, anomalies, onHover, projection, flash }: Props) {
  const preds = analysis.predictions;
  if (!preds.length) return <div className="empty dim">没有样品测定结果</div>;
  const d = analysis.fits[0]?.derived ?? {};
  const mean = d.w_na2o_mean_pct;
  const rule = analysis.qc_results.find((q) => q.rule_id === "parallel_rpd");
  const limit = analysis.comparison.vs_limit[0];
  const unit = preds[0].unit;

  const vals = preds.flatMap((p) => [p.as_reported - p.u95, p.as_reported + p.u95]);
  if (limit) vals.push(limit.limit);
  if (projection) vals.push(projection.y);
  const [y0, y1] = pad([Math.min(...vals), Math.max(...vals)], 0.1);
  const sy = linear(y0, y1, H - M.b, M.t);
  const sx = linear(-0.5, preds.length - 0.5, M.l, W - M.r);
  const bandHalf = mean != null && rule ? mean * rule.limit : null;

  return (
    <Chart w={W} h={H} label="平行测定精密度">
      <Frame>
        <GridY ticks={niceTicks(y0, y1)} sy={sy} x0={M.l} x1={W - M.r} />
        <line className="axis" x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} />
        <text className="axis-label" x={M.l} y={M.t - 8}>w(Na₂O) / {unit}</text>
      </Frame>

      {mean != null && bandHalf != null && (
        <Band>
          <rect className="band" x={M.l} width={W - M.r - M.l} y={sy(mean + bandHalf)} height={Math.max(1, sy(mean - bandHalf) - sy(mean + bandHalf))} />
          <text className="band-label" x={W - M.r + 8} y={sy(mean) - 10}>允许带 ±{fmt(rule!.limit * 100, 2)}%</text>
        </Band>
      )}
      {mean != null && (
        <Fade>
          <line className="mean-line" x1={M.l} x2={W - M.r} y1={sy(mean)} y2={sy(mean)} />
          <text className="fit-label" x={W - M.r + 8} y={sy(mean) + 4}>均值 {mean}{unit}</text>
        </Fade>
      )}
      {limit && (
        <Fade>
          <line className="limit-line" x1={M.l} x2={W - M.r} y1={sy(limit.limit)} y2={sy(limit.limit)} />
          <text className="tick" x={W - M.r + 8} y={sy(limit.limit) + 4} textAnchor="start">理论 {limit.limit}{unit}</text>
        </Fade>
      )}

      {preds.map((p, i) => {
        const on = highlight.has(p.point_id);
        const off = anomalies.has(p.point_id);
        const lo = sy(p.as_reported - p.u95), hi = sy(p.as_reported + p.u95);
        return (
          <Mark key={p.point_id} i={i} id={p.point_id} onHover={onHover}>
            <line className="errbar" x1={sx(i)} x2={sx(i)} y1={lo} y2={hi} />
            <line className="errbar" x1={sx(i) - 6} x2={sx(i) + 6} y1={lo} y2={lo} />
            <line className="errbar" x1={sx(i) - 6} x2={sx(i) + 6} y1={hi} y2={hi} />
            <circle className={"pt" + (off ? " bad" : "") + (on ? " on" : "")} cx={sx(i)} cy={sy(p.as_reported)} r={on ? 7 : 5} />
            {on && <circle className="ring" cx={sx(i)} cy={sy(p.as_reported)} r={13} />}
            <Flash flash={flash} id={p.point_id} cx={sx(i)} cy={sy(p.as_reported)} bad={off} />
            <text className={"pt-label" + (off ? " bad" : "")} x={sx(i) + 12} y={sy(p.as_reported) + 4}>
              {p.point_id} · {p.as_reported}{unit} ± {p.u95}
            </text>
            <text className="tick" x={sx(i)} y={H - M.b + 18} textAnchor="middle">{p.point_id} · V {Object.values(p.input)[0]} mL</text>
          </Mark>
        );
      })}

      {projection && (() => {
        const i = preds.findIndex((p) => p.point_id === projection.point_id);
        if (i < 0) return null;
        const p = preds[i];
        return (
          <Sim key={projection.label}>
            <line className="sim-line" x1={sx(i)} x2={sx(i) + 28} y1={sy(p.as_reported)} y2={sy(projection.y)} />
            <circle className="sim-pt" cx={sx(i) + 28} cy={sy(projection.y)} r={5} />
            <text className="sim-label" x={sx(i) + 38} y={sy(projection.y) + 4}>推演 {projection.label}</text>
          </Sim>
        );
      })()}
    </Chart>
  );
}
