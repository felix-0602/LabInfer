import anchor from "../../../design/assets/GEN-06.webp";
import { FieldLabel, GuideEntry } from "../guide";
import { stagger } from "../motion";
import { Vignette } from "../vignette";
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
      <section className="pane main-pane s1-main">
        <div className="ghost-num s1-ghost">01</div>
        <div className="reg" style={{ right: 64, top: 52 }} />
        <div className="colorbar" style={{ right: 96, top: 55 }}><i /><i /><i /><i /><i /><i /></div>
        <div className="eyebrow mono rv" style={stagger(0)}>STEP 01 · 实验上下文 · 预置模板</div>
        <h1 className="h-title rv" style={stagger(1)}>{title}</h1>
        {sub && <div className="h-sub display rv" style={stagger(2)}>{sub.replace("）", "")}</div>}
        <dl className="kv rv-lines">
          <dt>目的</dt><dd>{ctx.purpose}</dd>
          <dt>模型</dt><dd><FieldLabel path="model" fallback={ctx.model} /></dd>
          {tpl && (<><dt>公式</dt><dd className="mono cobalt">{tpl.formula}</dd></>)}
          <dt>变量</dt>
          <dd className="chips">
            {ctx.variables.columns.map((c) => (
              <FieldLabel key={c.key} path={`variables.${c.key}`} fallback={`${c.key} · ${c.role}`}>
                <span className="val">{c.unit}{c.optional ? " · 可选" : ""}</span>
              </FieldLabel>
            ))}
          </dd>
          <dt>模型常数</dt>
          <dd className="chips">
            {Object.entries(ctx.model_params ?? {}).map(([k, v]) => (
              <FieldLabel key={k} path={`model_params.${k}`} fallback={k}>
                <span className="val">{paramText(v)}</span>
              </FieldLabel>
            ))}
          </dd>
          <dt>参照</dt>
          <dd>
            {ctx.reference.limits.map((l, i) => (
              <div key={l.label}>
                <FieldLabel path={`reference.limits[${i}]`} fallback={l.label}>
                  <span className="mono"> {l.operator} {l.value}{l.unit}</span>
                </FieldLabel>
              </div>
            ))}
            {ctx.reference.datasets.length === 0 && <div className="dim">无文献数据集（参照为理论值与标准条文）</div>}
          </dd>
          <dt>质控规则</dt>
          <dd>
            {ctx.qc_rules.map((r) => (
              <div key={r.rule_id} className="qc-row">
                <FieldLabel path={`qc_rules.${r.rule_id}`} fallback={r.rule_id}>
                  {!ctx.guide?.field_notes[`qc_rules.${r.rule_id}`] && RULE_NAMES[r.rule_id] ? ` ${RULE_NAMES[r.rule_id]}` : null}
                </FieldLabel>
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
      <aside className="pane side-pane tex-grain">
        <Vignette id="GEN-06" className="s1-anchor" src={anchor} caption="OBJ. 01 · MOLECULAR MODEL · 建模：把实验抽象成结构与公式" />
        <GuideEntry page="context" className="rv" style={stagger(3)} />
        <div className="eyebrow mono rv" style={stagger(3)}>实验模板库 · {s.templates.length} 项</div>
        <ul className="tpl-list">
          {s.templates.map((t, i) => (
            <li key={t.id} className={"rv" + (t.model === ctx.model ? " on" : "")} style={stagger(4 + i)}>
              <div><b>{t.name}</b> <span className={"tag mono" + (t.status === "演示" ? " cobalt" : "")}>{t.status}</span>{t.has_guide && <span className="tag mono">有导读</span>}</div>
              <div className="mono dim small">{t.formula}</div>
            </li>
          ))}
          {s.templates.length === 0 && <li className="dim">模板库离线</li>}
        </ul>
      </aside>
    </div>
  );
}
