import anchor from "../../../design/assets/GEN-06.webp";
import { Anchor, stagger } from "../motion";
import { useWorkbench } from "../workbench";

const RULE_NAMES: Record<string, string> = {
  standardization_rpad: "标定相对平均偏差",
  parallel_rpd: "平行测定相对平均偏差",
  outlier_grubbs: "格拉布斯离群检验",
};

// 模型常数展示：数值原样，数组连成区间，对象按值拼接（如 indicator → 甲基橙 3.1–4.4）
function paramText(v: unknown): string {
  if (Array.isArray(v)) return v.map(paramText).join("–");
  if (v && typeof v === "object") return Object.values(v).map(paramText).join(" ");
  return String(v);
}

export function ContextScreen() {
  const { s, dispatch } = useWorkbench();
  const ctx = s.ctx;
  if (!ctx) return null;
  const tpl = s.templates.find((t) => t.model === ctx.model && t.name === ctx.name);
  const [title, sub] = ctx.name.split("（");

  return (
    <div className="split">
      <section className="pane main-pane">
        <div className="eyebrow mono rv" style={stagger(0)}>STEP 01 · 实验上下文 · 预置模板</div>
        <h1 className="h-title rv" style={stagger(1)}>{title}</h1>
        {sub && <div className="h-sub display rv" style={stagger(2)}>{sub.replace("）", "")}</div>}
        <dl className="kv rv-lines">
          <dt>目的</dt><dd>{ctx.purpose}</dd>
          <dt>模型</dt><dd className="mono">{ctx.model}</dd>
          {tpl && (<><dt>公式</dt><dd className="mono cobalt">{tpl.formula}</dd></>)}
          <dt>变量</dt>
          <dd className="chips">
            {ctx.variables.columns.map((c) => (
              <span key={c.key} className="chip mono">{c.key} · {c.role} · {c.unit}{c.optional ? " · 可选" : ""}</span>
            ))}
          </dd>
          <dt>模型常数</dt>
          <dd className="chips">
            {Object.entries(ctx.model_params ?? {}).map(([k, v]) => (
              <span key={k} className="chip mono">{k} = {paramText(v)}</span>
            ))}
          </dd>
          <dt>参照</dt>
          <dd>
            {ctx.reference.limits.map((l) => (
              <div key={l.label}>{l.label} <span className="mono">{l.operator} {l.value}{l.unit}</span></div>
            ))}
            {ctx.reference.datasets.length === 0 && <div className="dim">无文献数据集（参照为理论值与标准条文）</div>}
          </dd>
          <dt>质控规则</dt>
          <dd>
            {ctx.qc_rules.map((r) => (
              <div key={r.rule_id}>
                {RULE_NAMES[r.rule_id] ?? r.rule_id} <span className="mono dim">{r.rule_id}</span>
                {r.citation && <div className="dim small">{r.citation}</div>}
              </div>
            ))}
          </dd>
        </dl>
        <div className="actions rv" style={stagger(9)}>
          <button className="btn primary sheen" onClick={() => dispatch({ type: "complete", step: 1, next: 2 })}>
            确认，上传我的数据 →
          </button>
        </div>
      </section>
      <aside className="pane side-pane">
        <Anchor src={anchor} caption="OBJ. 01 · MODEL · 把实验抽象成结构与公式" />
        <div className="eyebrow mono rv" style={stagger(3)}>实验模板库 · {s.templates.length} 项</div>
        <ul className="tpl-list">
          {s.templates.map((t, i) => (
            <li key={t.id} className={"rv" + (t.model === ctx.model ? " on" : "")} style={stagger(4 + i)}>
              <div><b>{t.name}</b> <span className={"tag mono" + (t.status === "演示" ? " cobalt" : "")}>{t.status}</span></div>
              <div className="mono dim small">{t.formula}</div>
            </li>
          ))}
          {s.templates.length === 0 && <li className="dim">模板库离线</li>}
        </ul>
      </aside>
    </div>
  );
}
