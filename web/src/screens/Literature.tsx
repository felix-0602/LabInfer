import { useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";
import orb from "../../../design/assets/GEN-03.webp";
import prism from "../../../design/assets/GEN-08.webp";
// 左侧期刊微距底纹：程序绘制（design/render/journal.py），只做情绪，内容不可读
import journal from "../../../design/assets/PHOTO-02.webp";
import { api } from "../api";
import { pxToValue } from "../charts/calib";
import { fmt } from "../charts/scale";
import type { AxisCalibration, AxisScale, ExtractResult, Figure, FigureDetection, Px, ReferenceDataset } from "../types";
import { stagger } from "../motion";
import { GuideEntry } from "../guide";
import { Vignette } from "../vignette";
import { errorText, useWorkbench } from "../workbench";

type Axis = "x" | "y";
type Handle = "x1" | "x2" | "y1" | "y2";
const HANDLES: Handle[] = ["x1", "x2", "y1", "y2"];

// 每个轴两个参考点，px 为 null 表示还没放（识别失败或该轴刻度不足）
interface AxisDraft { scale: AxisScale; p1: { px: Px | null; value: string }; p2: { px: Px | null; value: string } }
type CalDraft = Record<Axis, AxisDraft>;

const emptyAxis = (): AxisDraft => ({ scale: "linear", p1: { px: null, value: "" }, p2: { px: null, value: "" } });
const fromSuggestion = (c: AxisCalibration | null): AxisDraft =>
  c ? { scale: c.scale, p1: { px: c.p1.px, value: String(c.p1.value) }, p2: { px: c.p2.px, value: String(c.p2.value) } } : emptyAxis();

const axisOf = (h: Handle): Axis => (h[0] as Axis);
const pointOf = (h: Handle): "p1" | "p2" => (h[1] === "1" ? "p1" : "p2");

function toAxisCalibration(d: AxisDraft): AxisCalibration | null {
  const v1 = Number(d.p1.value), v2 = Number(d.p2.value);
  if (!d.p1.px || !d.p2.px || d.p1.value.trim() === "" || d.p2.value.trim() === "" || !Number.isFinite(v1) || !Number.isFinite(v2)) return null;
  return { scale: d.scale, p1: { px: d.p1.px, value: v1 }, p2: { px: d.p2.px, value: v2 } };
}

// 文献数据集的列 x / y 绑定到模型角色（contracts.md · 模型注册表）
function roleColumns(model: string, roles: string[]): Record<string, string> {
  if (model === "titration_standardization") return { titrant_volume: "x", ph: "y" };
  if (model === "linear_calibration") return { concentration: "x", signal: "y" };
  return roles.length >= 2 ? { [roles[0]]: "x", [roles[1]]: "y" } : {};
}

type Drag = { kind: "handle"; h: Handle } | { kind: "point"; i: number; moved: boolean };

export function Literature() {
  const { s, dispatch, attachReference } = useWorkbench();
  const fileRef = useRef<HTMLInputElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [doi, setDoi] = useState("");
  const [figNo, setFigNo] = useState("");
  const [fig, setFig] = useState<Figure | null>(null);
  const [det, setDet] = useState<FigureDetection | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [detectError, setDetectError] = useState<string | null>(null);
  const [cal, setCal] = useState<CalDraft>({ x: emptyAxis(), y: emptyAxis() });
  const [active, setActive] = useState<Handle | null>(null);
  const [seriesId, setSeriesId] = useState<string | null>(null);
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [points, setPoints] = useState<Px[]>([]);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState<Px | null>(null);
  const [view, setView] = useState<"both" | "image" | "layer">("both");
  const [vEq, setVEq] = useState("");
  // related（口径不同）加入对比前的二次确认：第一次点击只点亮，再点才真正加入
  const [armRelated, setArmRelated] = useState(false);
  const drag = useRef<Drag | null>(null);

  const ctx = s.ctx;
  const isTitration = ctx?.model === "titration_standardization";
  const calX = toAxisCalibration(cal.x), calY = toAxisCalibration(cal.y);
  const calReady = !!calX && !!calY;
  const placed = HANDLES.filter((h) => cal[axisOf(h)][pointOf(h)].px).length;
  const series = det?.series.find((x) => x.id === seriesId) ?? null;
  const canAuto = !!series?.color;
  const intent = det?.intent ?? null;
  const intentBlocked = intent?.verdict === "different";
  const needsRelatedConfirm = intent?.verdict === "related" && !armRelated;

  const upload = async (file: Blob, name: string) => {
    setBusy("正在上传截图");
    setError(null);
    try {
      const f = await api.uploadFigure(file, name, doi.trim(), figNo.trim());
      setFig(f);
      setResult(null);
      setPoints([]);
      setArmRelated(false);
      setBusy(null);
      setDetecting(true);
      try {
        const d = await api.detectFigure(f.id, ctx?.id);
        setDet(d);
        setCal({ x: fromSuggestion(d.calibration.x), y: fromSuggestion(d.calibration.y) });
        const first = d.series.find((x) => x.color) ?? d.series[0] ?? null;
        setSeriesId(first?.id ?? null);
        setMode(first?.color ? "auto" : "manual");
        setActive(!d.calibration.x ? "x1" : !d.calibration.y ? "y1" : null);
      } catch (e) {
        // 识别不可用（503）：转手动校准与手动点取（architecture.md · M2 降级）
        setDet(null);
        setDetectError(errorText(e));
        setCal({ x: emptyAxis(), y: emptyAxis() });
        setSeriesId(null);
        setMode("manual");
        setActive("x1");
      } finally {
        setDetecting(false);
      }
    } catch (e) {
      setBusy(null);
      setError(`上传失败：${errorText(e)}`);
    }
  };

  const toPx = (e: { clientX: number; clientY: number }): Px | null => {
    const svg = svgRef.current;
    const m = svg?.getScreenCTM();
    if (!svg || !m) return null;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    return [Math.round(p.x * 10) / 10, Math.round(p.y * 10) / 10];
  };

  const setHandle = (h: Handle, px: Px) =>
    setCal((c) => ({ ...c, [axisOf(h)]: { ...c[axisOf(h)], [pointOf(h)]: { ...c[axisOf(h)][pointOf(h)], px } } }));

  const onCanvasDown = (e: ReactPointerEvent<SVGSVGElement>) => {
    if (drag.current) return;
    const px = toPx(e);
    if (!px) return;
    if (active) {
      setHandle(active, px);
      const next = HANDLES.find((h) => h !== active && !cal[axisOf(h)][pointOf(h)].px);
      setActive(next ?? null);
    } else if (mode === "manual") {
      setPoints((p) => [...p, px].sort((a, b) => a[0] - b[0]));
      setDirty(true);
    }
  };

  const onMove = (e: ReactPointerEvent<SVGSVGElement>) => {
    const px = toPx(e);
    setCursor(px);
    const d = drag.current;
    if (!d || !px) return;
    if (d.kind === "handle") setHandle(d.h, px);
    else {
      d.moved = true;
      setPoints((p) => p.map((q, i) => (i === d.i ? px : q)));
      setDirty(true);
      setMode("manual");
    }
  };

  const onUp = () => {
    const d = drag.current;
    drag.current = null;
    // 点一下不拖动 = 删除该点；修正过的点以 manual 模式重新提交，沿用同一个 series_id
    if (d?.kind === "point" && !d.moved) {
      setPoints((p) => p.filter((_, i) => i !== d.i));
      setDirty(true);
      setMode("manual");
    }
    if (d?.kind === "point") setPoints((p) => [...p].sort((a, b) => a[0] - b[0]));
  };

  const extract = async () => {
    if (!fig || !calX || !calY) return;
    setBusy(mode === "auto" ? "M2 正在按颜色提取" : "M2 正在换算手动点");
    setError(null);
    try {
      const r = await api.extractFigure(fig.id, {
        calibration: { x: calX, y: calY },
        mode,
        series_id: seriesId,
        points_px: mode === "manual" ? points : null,
      });
      setResult(r);
      setPoints(r.points_px.map((p) => p.px));
      setDirty(false);
      if (mode === "auto" && r.points_px.length === 0) setMode("manual");
    } catch (e) {
      setError(`提取失败：${errorText(e)}`);
    } finally {
      setBusy(null);
    }
  };

  const attach = () => {
    if (!result || !ctx) return;
    if (needsRelatedConfirm) { setArmRelated(true); return; }   // 口径不同：第一次点击只确认
    const v = Number(vEq);
    const entry: ReferenceDataset = {
      dataset_id: result.dataset.id,
      columns: roleColumns(ctx.model, ctx.variables.columns.filter((c) => !c.optional).map((c) => c.role ?? c.key)),
      space: "raw",
      meta: {
        doi: result.dataset.meta.doi ?? null,
        figure: result.dataset.meta.figure ?? null,
        ...(isTitration && vEq.trim() !== "" && Number.isFinite(v) ? { v_eq_ml: v } : {}),
      },
    };
    setArmRelated(false);
    void attachReference(entry);
  };

  const skip = (
    <button className="btn ghost" disabled={!s.analysis || !!s.busy} onClick={() => dispatch({ type: "complete", step: 3, next: 4 })}>
      跳过，进入分析 →
    </button>
  );

  // ---------- 空状态 ----------
  if (!fig || s.shadow) {
    return (
      <div className="split">
        <section className="pane main-pane center lit-empty tex-grain">
          <div className="display ghost-word">FIGURE → DATA</div>
          <div className="journal duo-day"><img src={journal} alt="" /></div>
          <div className="halftone fade-r" />
          <div className="cross" style={{ left: 32, top: 32 }} />
          <div className="cross" style={{ right: 32, top: 32 }} />
          <Vignette id="GEN-03" className="s3-orb" src={orb} />
          <h2>{isTitration ? "拖入教材或论文里的滴定曲线" : "把论文里的图交给它"}</h2>
          <p className="dim small">PNG / JPG · 建议宽度 ≥ 1200 px · 也可以直接粘贴截图</p>
          {s.shadow ? (
            <p className="dim">演示保底模式下没有后端，文献取数不可用。这个模板的参照是理论值与标准条文，可以直接进入分析。</p>
          ) : (
            <div
              className="lit-drop"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const f = e.dataTransfer.files[0];
                if (f) void upload(f, f.name);
              }}
              onPaste={(e) => {
                const f = [...e.clipboardData.files][0];
                if (f) void upload(f, f.name || "paste.png");
              }}
              tabIndex={0}
            >
              <div className="meta-in">
                <input className="input" placeholder="来源：DOI / 链接 / 报告号" value={doi} onChange={(e) => setDoi(e.target.value)} />
                <input className="input" placeholder="图号，如 图1(b)" value={figNo} onChange={(e) => setFigNo(e.target.value)} />
              </div>
              <div className="actions center">
                <button className="btn primary" disabled={!!busy} onClick={() => fileRef.current?.click()}>{busy ?? "选择截图…"}</button>
                {skip}
              </div>
              <input ref={fileRef} type="file" accept="image/png,image/jpeg" hidden onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void upload(f, f.name);
              }} />
            </div>
          )}
          {s.shadow && <div className="actions">{skip}</div>}
          {error && <p className="bad small">{error}</p>}
          {!s.analysis && <p className="mono dim small">{s.busy ?? "等待 M4 计算结果"}</p>}
          <GuideEntry page="literature" />
        </section>
      </div>
    );
  }

  // ---------- 校准画布 ----------
  const readout = cursor && calX && calY
    ? `px (${cursor[0]}, ${cursor[1]}) → x = ${fmt(pxToValue("x", calX, cursor) ?? NaN, 4)}，y = ${fmt(pxToValue("y", calY, cursor) ?? NaN, 4)}`
    : cursor ? `px (${cursor[0]}, ${cursor[1]})` : "移动光标查看读数";
  const k = Math.max(fig.width, fig.height) / 600; // 标记尺寸随原图像素缩放
  const xs = result?.dataset.columns.find((c) => c.key === "x");
  const ys = result?.dataset.columns.find((c) => c.key === "y");

  return (
    <div className="s3b">
      <aside className="pane lp">
        <ol className="stepper">
          <li className={calReady ? "" : "on"}>
            <h4>校准坐标轴</h4>
            <p className="dim small">
              {det ? `AI 识别了 ${det.axes.x.ticks.length + det.axes.y.ticks.length} 个刻度，请核对数值。` : "视觉模型不可用，请在图上依次点出 4 个校准点并填写数值。"}
              拖动画布上的十字可以微调。
            </p>
            <div className="calib-list">
              {HANDLES.map((h) => {
                const a = cal[axisOf(h)], p = a[pointOf(h)];
                return (
                  <div key={h} className={"calib-row" + (active === h ? " active" : "")}>
                    <button className="h mono" onClick={() => setActive(active === h ? null : h)} title="点这里，再在图上点一下放置">{h.toUpperCase()}</button>
                    <span className="px mono">{p.px ? `(${Math.round(p.px[0])}, ${Math.round(p.px[1])})` : "未放置"}</span>
                    <input className="val mono" inputMode="decimal" value={p.value} placeholder="数值"
                      onChange={(e) => setCal((c) => ({ ...c, [axisOf(h)]: { ...a, [pointOf(h)]: { ...p, value: e.target.value } } }))} />
                  </div>
                );
              })}
            </div>
            {(["x", "y"] as Axis[]).map((ax) => (
              <div key={ax} className="scale-row small">
                <span className="mono dim">{ax.toUpperCase()} 轴</span>
                {(["linear", "log10"] as AxisScale[]).map((sc) => (
                  <button key={sc} className={"pill" + (cal[ax].scale === sc ? " on" : "")}
                    onClick={() => setCal((c) => ({ ...c, [ax]: { ...c[ax], scale: sc } }))}>{sc === "linear" ? "线性" : "对数"}</button>
                ))}
              </div>
            ))}
          </li>
          <li className={calReady && !result ? "on" : ""}>
            <h4>选择曲线</h4>
            <div className="series">
              {det?.series.map((x) => (
                <button key={x.id} className={x.id === seriesId ? "on" : ""} onClick={() => { setSeriesId(x.id); setMode(x.color ? "auto" : "manual"); }}>
                  <i style={{ background: x.color ?? "var(--silver)" }} />{x.id} · {x.label || "未命名曲线"}
                  <span className="n mono">{x.color ? Math.round(x.confidence * 100) + "%" : "无颜色"}</span>
                </button>
              ))}
              {!det?.series.length && <div className="dim small">没有识别到曲线，用手动点取。</div>}
            </div>
          </li>
          {intent && (
            <li className={intent.verdict === "same" ? "on" : ""}>
              <h4>与你的实验对比</h4>
              <div className={"intent v-" + intent.verdict}>
                <b>{{ same: "同类，可直接对比", related: "相关，口径不同", different: "不匹配" }[intent.verdict]}</b>
                <ul>
                  {intent.reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
                {intent.chart && (intent.chart.x_quantity || intent.chart.y_quantity) && (
                  <p className="dim small mono">图上读到的：{intent.chart.type} · x={intent.chart.x_quantity || "?"} · y={intent.chart.y_quantity || "?"}{intent.chart.titrant ? ` · 滴定剂=${intent.chart.titrant}` : ""}</p>
                )}
              </div>
            </li>
          )}
          <li className={result ? "on" : ""}>
            <h4>提取数据点</h4>
            <div className="scale-row small">
              <button className={"pill" + (mode === "auto" ? " on" : "")} disabled={!canAuto} onClick={() => setMode("auto")}>自动</button>
              <button className={"pill" + (mode === "manual" ? " on" : "")} onClick={() => { setMode("manual"); setActive(null); }}>手动点取</button>
            </div>
            <p className="dim small">
              {mode === "manual" ? `在图上点击添加点，点一下已有的点删除，拖动可修正。已放 ${points.length} 个。` : "按曲线颜色自动提取，提取后仍可拖动或删除点。"}
            </p>
          </li>
        </ol>
        {det?.warnings.map((w) => <p key={w} className="warn small">{w}</p>)}
        {detectError && <p className="warn small">识别不可用：{detectError}</p>}
      </aside>

      <section className="canvas mat">
        <div className="toolbar">
          {(["image", "layer", "both"] as const).map((v) => (
            <button key={v} className={view === v ? "on" : ""} onClick={() => setView(v)}>{{ image: "原图", layer: "提取层", both: "叠加" }[v]}</button>
          ))}
          <span className="sep" />
          <button onClick={() => { setFig(null); setDet(null); setResult(null); setDetectError(null); }}>换一张</button>
        </div>
        <div className={"fig" + (detecting ? " scanning" : "")}>
          <div className="fig-inner" style={{ "--ar": fig.width / fig.height } as CSSProperties}>
            <div className="crops" />
            {view !== "layer" && <img src={fig.image_url} alt="文献曲线截图" draggable={false} />}
            <svg
              ref={svgRef}
              className={"overlay" + (active || mode === "manual" ? " placing" : "")}
              viewBox={`0 0 ${fig.width} ${fig.height}`}
              onPointerDown={onCanvasDown}
              onPointerMove={onMove}
              onPointerUp={onUp}
              onPointerLeave={() => { setCursor(null); onUp(); }}
            >
              {det?.plot_area && view !== "image" && (
                <rect className="plot-area" x={det.plot_area.u0} y={det.plot_area.v0}
                  width={det.plot_area.u1 - det.plot_area.u0} height={det.plot_area.v1 - det.plot_area.v0} />
              )}
              {view !== "image" && points.map((p, i) => (
                <circle key={i} className="lit-pt" cx={p[0]} cy={p[1]} r={5 * k}
                  onPointerDown={(e) => { e.stopPropagation(); drag.current = { kind: "point", i, moved: false }; }} />
              ))}
              {HANDLES.map((h) => {
                const px = cal[axisOf(h)][pointOf(h)].px;
                if (!px) return null;
                const a = axisOf(h);
                // 标签避让：贴右侧改放左下并右对齐、贴底部改放点上方——不压图片刻度和相邻标签
                const nearRight = px[0] > fig.width * 0.8;
                const nearBottom = px[1] > fig.height * 0.85;
                return (
                  <g key={h} className={"handle" + (active === h ? " active" : "")}
                    onPointerDown={(e) => { e.stopPropagation(); drag.current = { kind: "handle", h }; }}>
                    {a === "x"
                      ? <line className="guide" x1={px[0]} x2={px[0]} y1={0} y2={fig.height} />
                      : <line className="guide" y1={px[1]} y2={px[1]} x1={0} x2={fig.width} />}
                    <circle cx={px[0]} cy={px[1]} r={9 * k} />
                    <line x1={px[0] - 11 * k} x2={px[0] + 11 * k} y1={px[1]} y2={px[1]} />
                    <line y1={px[1] - 11 * k} y2={px[1] + 11 * k} x1={px[0]} x2={px[0]} />
                    <text x={nearRight ? px[0] - 12 * k : px[0] + 12 * k}
                      y={nearBottom ? px[1] - 12 * k : px[1] + 22 * k}
                      textAnchor={nearRight ? "end" : "start"}
                      style={{ fontSize: 12 * k }}>
                      {h.toUpperCase()} · {cal[a][pointOf(h)].value || "?"}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
        <div className="banner">
          <span className="dot" />
          <span>
            {detecting ? "正在识别坐标轴与图例…" : active ? `在图上点击放置 ${active.toUpperCase()}` : `4 个校准点已放 ${placed} 个`}
            {result?.residual_px != null && ` · 换算残差 ${result.residual_px} px`}
          </span>
          <span className="sp" />
          <button className="btn primary small" disabled={!calReady || !!busy || (mode === "manual" && points.length === 0) || (mode === "auto" && !canAuto)} onClick={extract}>
            {busy ?? (result ? (dirty ? "提交修正 →" : "重新提取") : "提取数据点 →")}
          </button>
        </div>
        <div className="readout mono">{readout}<span className="sp" />坐标换算由 M2 的确定性代码完成，画布读数仅供参考</div>
      </section>

      <aside className="pane rp">
        <GuideEntry page="literature" />
        <div className="panel-h"><b>提取结果</b><span className="mono id">{result?.dataset.id ?? "—"}</span></div>
        <dl className="kv-mini">
          <dt>来源</dt><dd>{fig.meta.doi ?? <span className="warn">未填 DOI</span>}</dd>
          <dt>图号</dt><dd>{fig.meta.figure ?? "—"}</dd>
          <dt>曲线</dt><dd>{series ? `${series.id} · ${series.label || "未命名"}` : "手动点取"}</dd>
          <dt>坐标</dt><dd>{cal.x.scale === "linear" ? "线性" : "对数"} / {cal.y.scale === "linear" ? "线性" : "对数"}</dd>
        </dl>
        <div className="table-wrap">
          <table className="mini-table mono">
            <thead><tr><th>ID</th><th>{xs?.name ?? "x"} {xs?.unit}</th><th>{ys?.name ?? "y"} {ys?.unit}</th></tr></thead>
            <tbody>
              {result?.dataset.rows.map((r, ri) => (
                <tr key={r.id} className="rv" style={stagger(ri)}><td>{r.id}</td><td>{r.values.x}</td><td>{r.values.y}</td></tr>
              ))}
              {!result && <tr><td colSpan={3} className="dim">提取后在这里列出</td></tr>}
            </tbody>
          </table>
        </div>
        {result?.warnings.map((w) => <p key={w} className="warn small">{w}</p>)}
        {dirty && result && <p className="warn small">点位有修改，提交修正后才会写回数据集。</p>}
        {error && <p className="bad small">{error}</p>}
        {isTitration && result && !(Number(vEq) > 0) && (
          <p className="warn small">滴定实验要先在上方填文献图的计量点体积 v_eq（曲线最陡一段中点对应的体积），加入对比才会启用。</p>
        )}
        {intentBlocked && (
          <p className="bad small">这张图与你的实验不匹配（见左侧「与你的实验对比」），不能加入对比。</p>
        )}
        {needsRelatedConfirm && result && (
          <p className="warn small">这张图口径不同（见左侧说明）。确认对比有意义的话，再点一次加入对比。</p>
        )}
        {isTitration && (
          <label className="field small">
            <span className="dim">文献图的计量点体积 v_eq（mL），M4 按它换到滴定分数</span>
            <input className="input" inputMode="decimal" value={vEq} onChange={(e) => setVEq(e.target.value)} placeholder="由图读出" />
          </label>
        )}
        <Vignette id="GEN-08" className="s3-anchor" src={prism} caption="OBJ. 03 · PRISM · 分离：把曲线从图里剥离出来" />
        <div className="actions end">
          {skip}
          <button className="btn primary" disabled={!result || !result.dataset.rows.length || dirty || !!s.busy || intentBlocked
            || (isTitration && !(Number(vEq) > 0))} onClick={attach}>
            {needsRelatedConfirm ? "口径不同，确认加入 →" : "加入对比 →"}
          </button>
        </div>
      </aside>
    </div>
  );
}
