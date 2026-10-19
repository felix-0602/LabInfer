import type { AnalysisResult } from "../types";
import { stagger } from "../motion";
import { fmt, linear, niceTicks, pad } from "./scale";

const W = 760, H = 420, M = { l: 64, r: 150, t: 24, b: 48 };

interface Props {
  analysis: AnalysisResult;
  highlight: Set<string>;
  // 红色只给异常：由 M5 异常结论引用的点决定，前端不自行判定
  anomalies: Set<string>;
  onHover: (pointId: string | null) => void;
  // M6 推演：某个平行份在调整参数后的预测值（直接取 Simulation.curve 的点）
  projection?: { point_id: string; y: number; label: string } | null;
  // 结论流式出现时，它引用的点闪一下（key 变化即重播）
  flash?: { ids: Set<string>; key: number };
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
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="平行测定精密度">
      <g className="c-frame">
      {niceTicks(y0, y1).map((t) => (
        <g key={t}>
          <line className="grid" x1={M.l} x2={W - M.r} y1={sy(t)} y2={sy(t)} />
          <text className="tick" x={M.l - 8} y={sy(t) + 4} textAnchor="end">{fmt(t, 2)}</text>
        </g>
      ))}
      <line className="axis" x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} />
      <text className="axis-label" x={M.l} y={M.t - 8}>w(Na₂O) / {unit}</text>
      </g>

      {mean != null && bandHalf != null && (
        <g className="c-band">
          <rect className="band" x={M.l} width={W - M.r - M.l} y={sy(mean + bandHalf)} height={Math.max(1, sy(mean - bandHalf) - sy(mean + bandHalf))} />
          <text className="band-label" x={W - M.r + 8} y={sy(mean) - 10}>允许带 ±{fmt(rule!.limit * 100, 2)}%</text>
        </g>
      )}
      {mean != null && (
        <g className="c-fade">
          <line className="mean-line" x1={M.l} x2={W - M.r} y1={sy(mean)} y2={sy(mean)} />
          <text className="fit-label" x={W - M.r + 8} y={sy(mean) + 4}>均值 {mean}{unit}</text>
        </g>
      )}
      {limit && (
        <g className="c-fade">
          <line className="limit-line" x1={M.l} x2={W - M.r} y1={sy(limit.limit)} y2={sy(limit.limit)} />
          <text className="tick" x={W - M.r + 8} y={sy(limit.limit) + 4} textAnchor="start">理论 {limit.limit}{unit}</text>
        </g>
      )}

      {preds.map((p, i) => {
        const on = highlight.has(p.point_id);
        const off = anomalies.has(p.point_id);
        return (
          <g key={p.point_id} className="pt-group c-pop" style={stagger(i)} onMouseEnter={() => onHover(p.point_id)} onMouseLeave={() => onHover(null)}>
            <line className="errbar" x1={sx(i)} x2={sx(i)} y1={sy(p.as_reported - p.u95)} y2={sy(p.as_reported + p.u95)} />
            <line className="errbar" x1={sx(i) - 6} x2={sx(i) + 6} y1={sy(p.as_reported - p.u95)} y2={sy(p.as_reported - p.u95)} />
            <line className="errbar" x1={sx(i) - 6} x2={sx(i) + 6} y1={sy(p.as_reported + p.u95)} y2={sy(p.as_reported + p.u95)} />
            <circle className={"pt" + (off ? " bad" : "") + (on ? " on" : "")} cx={sx(i)} cy={sy(p.as_reported)} r={on ? 7 : 5} />
            {on && <circle className="ring" cx={sx(i)} cy={sy(p.as_reported)} r={13} />}
            {flash?.ids.has(p.point_id) && <circle key={flash.key} className={"flash" + (off ? " bad" : "")} cx={sx(i)} cy={sy(p.as_reported)} r={6} />}
            <text className={"pt-label" + (off ? " bad" : "")} x={sx(i) + 12} y={sy(p.as_reported) + 4}>
              {p.point_id} · {p.as_reported}{unit} ± {p.u95}
            </text>
            <text className="tick" x={sx(i)} y={H - M.b + 18} textAnchor="middle">{p.point_id} · V {Object.values(p.input)[0]} mL</text>
          </g>
        );
      })}

      {projection && (() => {
        const i = preds.findIndex((p) => p.point_id === projection.point_id);
        if (i < 0) return null;
        const p = preds[i];
        return (
          <g className="c-sim" key={projection.label}>
            <line className="sim-line" x1={sx(i)} x2={sx(i) + 28} y1={sy(p.as_reported)} y2={sy(projection.y)} />
            <circle className="sim-pt" cx={sx(i) + 28} cy={sy(projection.y)} r={5} />
            <text className="sim-label" x={sx(i) + 38} y={sy(projection.y) + 4}>推演 {projection.label}</text>
          </g>
        );
      })()}
    </svg>
  );
}
