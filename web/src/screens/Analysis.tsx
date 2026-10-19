import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import anchor from "../../../design/assets/GEN-09.webp";
import { api } from "../api";
import { BudgetChart } from "../charts/BudgetChart";
import { FitChart } from "../charts/FitChart";
import { PrecisionChart } from "../charts/PrecisionChart";
import { TitrationChart } from "../charts/TitrationChart";
import type { AnalysisResult, Finding, Simulation } from "../types";
import { CountUp, STREAM_GAP, Segmented, reducedMotion, stagger } from "../motion";
import { loadShadowSims } from "../shadow";
import { Vignette } from "../vignette";
import { errorText, useWorkbench } from "../workbench";

type Tab = "titration" | "fit" | "precision" | "budget";
const TAB_LABEL: Record<Tab, string> = { titration: "滴定曲线", fit: "V–m 拟合", precision: "精密度", budget: "误差预算" };
const TYPE_LABEL: Record<string, string> = { pattern: "规律", conclusion: "能证明什么", anomaly: "异常", suggestion: "建议" };
const VERIFY_LABEL = { verified: "被证实", refuted: "被否定", unverified: "未验证" };

// 结论引用到的数据点：直接引用的点，加上它引用的质控规则所覆盖的点
function pointsOf(f: Finding, a: AnalysisResult): Set<string> {
  const out = new Set<string>();
  for (const e of f.evidence) {
    if (e.type === "point") out.add(e.point_id);
    if (e.type === "qc") a.qc_results.find((q) => q.rule_id === e.rule_id)?.subjects.forEach((s) => out.add(s.point_id));
  }
  return out;
}

// 已经播过进场的结论（按对象记）：回到分析页时不再重播，重新解读得到的新对象会重播
const played = new WeakSet<Finding>();

function evidenceLabel(e: Finding["evidence"][number]): string {
  switch (e.type) {
    case "point": return e.point_id;
    case "fit": return "拟合";
    case "qc": return e.rule_id;
    case "comparison": return e.target;
  }
}

export function Analysis() {
  const { s, dispatch, rerunFindings } = useWorkbench();
  const a = s.analysis;
  const tabs = useMemo<Tab[]>(() => {
    if (!a) return [];
    return [a.titration_curve && "titration", "fit", a.predictions.length && "precision", a.error_budget && "budget"]
      .filter(Boolean) as Tab[];
  }, [a]);
  const [tab, setTab] = useState<Tab | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hoverPt, setHoverPt] = useState<string | null>(null);
  const [openLadder, setOpenLadder] = useState<Set<string>>(new Set());
  const [sim, setSim] = useState<{ finding: Finding; result: Simulation; idx: number } | null>(null);
  const [simBusy, setSimBusy] = useState<string | null>(null);
  const [simError, setSimError] = useState<string | null>(null);
  // 推演面板展开的是哪条结论；折叠时图上的推演曲线 / 投影一起收起，结果留着，再展开不用重算
  const [simOpen, setSimOpen] = useState<string | null>(null);

  useEffect(() => { if (!tab || !tabs.includes(tab)) setTab(tabs[0] ?? null); }, [tabs, tab]);

  // 结论逐条流式出现：新结论按到达顺序排进场延迟（一次到齐时也按 STREAM_GAP 逐条放出），
  // 每条出现时它引用的点在图上闪一下
  const entering = useRef(new Map<Finding, number>());
  let queued = 0;
  for (const f of s.findings) {
    if (!played.has(f) && !entering.current.has(f)) entering.current.set(f, queued++ * STREAM_GAP);
  }
  const [flash, setFlash] = useState<{ ids: Set<string>; key: number }>({ ids: new Set(), key: 0 });
  const timers = useRef(new Map<Finding, number>());
  useEffect(() => {
    if (!a) return;
    for (const [f, delay] of entering.current) {
      if (played.has(f) || timers.current.has(f)) continue;
      timers.current.set(f, window.setTimeout(() => {
        played.add(f);
        setFlash((p) => ({ ids: pointsOf(f, a), key: p.key + 1 }));
      }, delay + 120));
    }
  }, [s.findings, a]);
  useEffect(() => () => {
    timers.current.forEach(clearTimeout);
    timers.current.clear();
  }, []);

  if (!a) return <div className="pane main-pane center"><p className="dim">{s.busy ?? "还没有分析结果"}</p></div>;

  const d = a.fits[0]?.derived ?? {};
  const fit = a.fits[0];
  const stdRule = a.qc_results.find((q) => q.rule_id === "standardization_rpad");
  const limit = a.comparison.vs_limit[0];

  // 红色只给异常：只看异常结论直接点名的点，前端不自行判定
  const anomalies = new Set(s.findings.filter((f) => f.type === "anomaly")
    .flatMap((f) => f.evidence.flatMap((e) => (e.type === "point" ? [e.point_id] : []))));
  const selFinding = s.findings.find((f) => f.id === selected);
  const highlight = new Set<string>(selFinding ? pointsOf(selFinding, a) : []);
  if (hoverPt) highlight.add(hoverPt);

  const runSim = async (f: Finding) => {
    if (!f.simulation || !s.ctx) return;
    setSimBusy(f.id);
    setSimError(null);
    try {
      let result: Simulation;
      if (s.shadow) {
        const cached = (await loadShadowSims())[f.id];
        if (!cached) throw new Error("演示保底里没有这条推演，需要后端");
        result = cached;
      } else {
        result = await api.simulate({ context_id: s.ctx.id, finding_id: f.id, ...f.simulation });
      }
      // 滑块从「不调整」那一端开始：取最接近 0 的点（推演曲线由 M6 给出，前端只选点不插值）
      let idx = 0;
      result.curve.forEach((p, i) => { if (Math.abs(p.x) < Math.abs(result.curve[idx].x)) idx = i; });
      setSim({ finding: f, result, idx });
      setSelected(f.id);
      if (f.simulation.param === "titrant_volume_delta" && tabs.includes("precision")) setTab("precision");
    } catch (e) {
      setSimError(errorText(e));
    } finally {
      setSimBusy(null);
    }
  };

  const toggleSim = (f: Finding) => {
    if (simOpen === f.id) { setSimOpen(null); return; }
    setSimOpen(f.id);
    if (sim?.finding.id !== f.id) void runSim(f);
  };
  const shown = sim && simOpen === sim.finding.id ? sim : null;
  const simPoint = shown ? shown.result.curve[shown.idx] : null;
  const simTarget = shown?.finding.evidence.find((e) => e.type === "point");
  const projection = shown && simPoint && simTarget?.type === "point" && shown.finding.simulation?.param === "titrant_volume_delta"
    ? { point_id: simTarget.point_id, y: simPoint.y, label: `ΔV ${simPoint.x} mL → ${simPoint.y}%` }
    : null;
  const simCurve = shown?.finding.simulation?.param === "co2_retained_fraction" ? shown.result.curve : null;

  const chartProps = { highlight, anomalies, onHover: setHoverPt, flash };

  // 滴定管刻度跟随当前关注的那一份：悬停的点 > 选中结论的点 > 第一个异常点 > 第一份
  const tc = a.titration_curve;
  const focus = tc && (tc.endpoints.find((e) => e.point_id === hoverPt)
    ?? tc.endpoints.find((e) => highlight.has(e.point_id))
    ?? tc.endpoints.find((e) => anomalies.has(e.point_id))
    ?? tc.endpoints.find((e) => e.dv_ml < tc.indicator.dv_window_ml[0] || e.dv_ml > tc.indicator.dv_window_ml[1])
    ?? tc.endpoints[0]);
  const volCol = s.dataset?.columns.find((c) => c.key === "V" || c.unit === "mL")?.key;
  const vRead = focus && volCol ? s.dataset?.rows.find((r) => r.id === focus.point_id)?.values[volCol] : null;
  const burette = focus && typeof vRead === "number" ? { point_id: focus.point_id, veq: vRead - focus.dv_ml } : null;

  return (
    <div className="s4">
      <section className="pane chart-area">
        <div className="headline">
          {d.c_hcl != null ? (
            <div className="metric rv" style={stagger(0)}>
              <div className="eyebrow mono">c̄(HCl) · {fit?.n ?? "—"} 份平行标定</div>
              <div className="big display"><CountUp value={d.c_hcl} digits={4} delay={200} /><small>mol·L⁻¹</small></div>
            </div>
          ) : fit && (
            <div className="metric">
              <div className="eyebrow mono">拟合斜率 · {a.model}</div>
              <div className="big display">{fit.slope}</div>
            </div>
          )}
          <div className="vs mono rv" style={stagger(2)}>
            {d.rel_avg_dev_c != null && (
              <span>相对平均偏差 <b className={stdRule && !stdRule.pass ? "bad" : ""}>{(d.rel_avg_dev_c * 100).toFixed(2)}%</b>
                {stdRule && <> · 限值 {(stdRule.limit * 100).toFixed(1)}%</>}</span>
            )}
            {d.w_na2o_mean_pct != null && (
              <span>总碱度 w̄(Na₂O) <b>{d.w_na2o_mean_pct.toFixed(2)}%</b>{limit && <> · 理论 {limit.limit}%</>}</span>
            )}
            {fit && <span>{tabs.includes("titration") ? "V–m 过原点 " : ""}R² {fit.r2} · n = {fit.n}</span>}
          </div>
          <Vignette id="GEN-09" className="s4-anchor" src={anchor} />
        </div>

        <Segmented items={tabs} value={tab} label={(t) => TAB_LABEL[t]} onChange={setTab}>
          {!a.titration_curve && <span className="mono dim small">滴定曲线、误差预算等 M4 输出 0.7.0 字段后出现</span>}
        </Segmented>

        <div className="chart-box" key={tab ?? "none"}>
          {tab === "titration" && a.titration_curve && <TitrationChart curve={a.titration_curve} simulated={simCurve} burette={burette} {...chartProps} />}
          {tab === "fit" && <FitChart analysis={a} {...chartProps} />}
          {tab === "precision" && <PrecisionChart analysis={a} projection={projection} {...chartProps} />}
          {tab === "budget" && a.error_budget && <BudgetChart budget={a.error_budget} />}
        </div>
      </section>

      <aside className="pane findings">
        <div className="panel-h">
          <b>AI 解读</b>
          <span className="dim">
            {s.findingsStatus === "streaming" ? `正在生成 · 已出 ${s.findings.length} 条` : `${s.findings.length} 条 · 每条都标注了依据`}
          </span>
        </div>
        <div className="f-list">
          {s.findings.map((f) => {
            const pts = pointsOf(f, a);
            const delay = entering.current.get(f);
            const linked = hoverPt != null && pts.has(hoverPt);
            const canSim = f.simulatable && f.simulation;
            return (
              <article
                key={f.id}
                className={"f-card " + f.type + (selected === f.id ? " selected" : "") + (linked ? " linked" : "") + (delay != null ? " entering" : "")}
                style={delay != null ? { "--d": `${delay}ms` } as CSSProperties : undefined}
                onClick={() => {
                  setSelected(selected === f.id ? null : f.id);
                  // 结论引用了某张图的整节（滴定曲线 / 误差预算），切到那张图
                  const t = f.evidence.find((e) => e.type === "comparison" && (e.target === "titration_curve" || e.target === "error_budget"));
                  if (t?.type === "comparison") setTab(t.target === "titration_curve" ? "titration" : "budget");
                }}
              >
                <div className="type mono"><i />{TYPE_LABEL[f.type] ?? f.type}{canSim ? " · 可推演" : ""}</div>
                <p>{f.text}</p>
                <div className="ev">{f.evidence.map((e, i) => <span key={i} className="chip-ev mono">{evidenceLabel(e)}</span>)}</div>
                {f.verification && f.verification.status !== "unverified" && (
                  <div className={"verify " + f.verification.status}>
                    <b>虚拟台复核 · {VERIFY_LABEL[f.verification.status]}</b> {f.verification.reason}
                  </div>
                )}
                {f.ladder?.map((r) => (
                  <div key={r.rung_id} className="ladder" onClick={(e) => {
                    e.stopPropagation();
                    const n = new Set(openLadder);
                    if (n.has(r.rung_id + f.id)) n.delete(r.rung_id + f.id); else n.add(r.rung_id + f.id);
                    setOpenLadder(n);
                  }}>
                    <b>↑ {r.level} 级</b> {openLadder.has(r.rung_id + f.id) ? <span className="ladder-text">{r.text}</span> : "展开讲解"}
                  </div>
                ))}
                {canSim && (() => {
                  const open = simOpen === f.id;
                  const mine = sim?.finding.id === f.id ? sim : null;
                  const sp = f.simulation!;
                  return (
                    <div className={"sim-ctl" + (open ? " open" : "")} onClick={(e) => e.stopPropagation()}>
                      <button className="sim-head mono" aria-expanded={open} onClick={(e) => {
                        const panel = e.currentTarget.parentElement;
                        toggleSim(f);
                        // 展开后面板可能落在列表可视区外，等高度动画走完再滚进来
                        if (!open) setTimeout(() => panel?.scrollIntoView({ block: "nearest", behavior: reducedMotion() ? "auto" : "smooth" }), 360);
                      }}>
                        <i className="chev" aria-hidden />
                        <span>推演 · {sp.param} {sp.from}→{sp.to}{sp.unit}</span>
                        <span className="dim">{open ? "收起" : mine ? "展开" : "展开推演"}</span>
                      </button>
                      <div className="sim-body"><div>
                        {mine ? (
                          <>
                            <input
                              type="range" min={0} max={mine.result.curve.length - 1} step={1} value={mine.idx}
                              aria-label={sp.param}
                              onChange={(e) => setSim({ ...mine, idx: Number(e.target.value) })}
                            />
                            <div className="sim-read mono">
                              {open && simPoint && (
                                <span>{sp.param} = <b>{simPoint.x}{sp.unit}</b> → <b>{simPoint.y}</b></span>
                              )}
                            </div>
                          </>
                        ) : simBusy === f.id ? (
                          <p className="small dim thinking">M6 推演中…</p>
                        ) : simError ? (
                          <div className="small bad">{simError} <button className="btn ghost small" onClick={() => void runSim(f)}>重试</button></div>
                        ) : null}
                      </div></div>
                    </div>
                  );
                })()}
              </article>
            );
          })}
          {s.findingsStatus === "streaming" && <div className="f-card ghost thinking mono dim">M5 正在解读…</div>}
          {s.findingsStatus === "error" && (
            <div className="f-card ghost">
              <p className="dim">AI 解读没有完成。图表和计算结果不受影响。</p>
              <button className="btn ghost small" onClick={() => void rerunFindings()}>重新解读</button>
            </div>
          )}
        </div>
        <div className="f-note mono dim small">结论中的数字须能在 M4 计算结果中找到（M5 数字溯源校验）</div>
        <div className="actions end">
          <button className="btn primary sheen" onClick={() => dispatch({ type: "complete", step: 4, next: 5 })}>生成报告 →</button>
        </div>
      </aside>
    </div>
  );
}
