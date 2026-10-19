import { Fragment, useEffect, useState, type ReactNode } from "react";
import band from "../../../design/assets/GEN-04.webp";
import desk from "../../../design/assets/GEN-05.webp";
import anchor from "../../../design/assets/GEN-10.webp";
import { api } from "../api";
import { PrecisionChart } from "../charts/PrecisionChart";
import { TitrationChart } from "../charts/TitrationChart";
import { errorText, useWorkbench } from "../workbench";

type Format = "md" | "docx";
type IncludeKey = "figure" | "anomalies" | "suggestions" | "quality_control" | "sources";

const INCLUDE: { key: IncludeKey; label: string }[] = [
  { key: "figure", label: "包含图 1" },
  { key: "anomalies", label: "包含异常点讨论" },
  { key: "suggestions", label: "包含改进建议" },
  { key: "quality_control", label: "包含质量控制" },
  { key: "sources", label: "标注依据（标准条文、文献图号）" },
];

// M7 的 Markdown 只用到标题、段落、列表和表格，这里按行渲染成预览，不改写任何内容
function renderMarkdown(md: string, figure: ReactNode): ReactNode[] {
  const out: ReactNode[] = [];
  const lines = md.split("\n");
  let figurePlaced = !figure;
  let inSection = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        const cells = lines[i].split("|").slice(1, -1).map((c) => c.trim());
        if (!cells.every((c) => /^-+$/.test(c))) rows.push(cells);
        i++;
      }
      i--;
      out.push(
        <table key={i} className="md-table mono">
          <thead><tr>{rows[0]?.map((c, j) => <th key={j}>{c}</th>)}</tr></thead>
          <tbody>{rows.slice(1).map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
        </table>,
      );
    } else if (line.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].startsWith("- ")) items.push(lines[i++].slice(2));
      i--;
      out.push(<ul key={i}>{items.map((t, k) => <li key={k}>{t}</li>)}</ul>);
    } else if (/^#{1,3} /.test(line)) {
      const level = line.indexOf(" ");
      const text = line.slice(level + 1);
      out.push(level === 1 ? <h2 key={i}>{text}</h2> : <h3 key={i}>{text}</h3>);
      if (level > 1) inSection = true;
    } else if (line.trim()) {
      out.push(<p key={i}>{line}</p>);
      // 图 1 放在第一节正文之后
      if (!figurePlaced && inSection) {
        out.push(<Fragment key={"fig" + i}>{figure}</Fragment>);
        figurePlaced = true;
      }
    }
  }
  if (!figurePlaced) out.push(<Fragment key="fig-end">{figure}</Fragment>);
  return out;
}

export function Export() {
  const { s, dispatch } = useWorkbench();
  const [format, setFormat] = useState<Format>("md");
  const [include, setInclude] = useState<Record<IncludeKey, boolean>>({
    figure: true, anomalies: true, suggestions: true, quality_control: true, sources: true,
  });
  const [md, setMd] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const ctxId = s.ctx?.id;

  useEffect(() => {
    if (!ctxId || s.shadow) return;
    let live = true;
    setError(null);
    api.exportReport(ctxId, "md", include)
      .then((b) => b.text())
      .then((t) => { if (live) setMd(t); })
      .catch((e) => { if (live) setError(errorText(e)); });
    return () => { live = false; };
  }, [ctxId, s.shadow, include]);

  const download = async () => {
    if (!ctxId) return;
    dispatch({ type: "patch", patch: { busy: "M7 正在生成报告" } });
    try {
      const blob = await api.exportReport(ctxId, format, include);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${ctxId}-结果与讨论.${format}`;
      link.click();
      URL.revokeObjectURL(url);
      dispatch({ type: "complete", step: 5 });
      dispatch({ type: "patch", patch: { busy: null } });
    } catch (e) {
      dispatch({ type: "patch", patch: { busy: null, notice: { tone: "error", text: `导出失败：${errorText(e)}` } } });
    }
  };

  const copy = async () => {
    if (!md) return;
    await navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const a = s.analysis;
  const figure = include.figure && a ? (
    <figure className="report-fig">
      {a.titration_curve
        ? <TitrationChart curve={a.titration_curve} highlight={new Set()} anomalies={new Set()} onHover={() => {}} />
        : <PrecisionChart analysis={a} highlight={new Set()} anomalies={new Set()} onHover={() => {}} />}
      <figcaption>图 1　{a.titration_curve ? "理论滴定曲线与各份标定终点（灰带：指示剂变色区）" : "平行测定结果 ± U95 与允许带"}</figcaption>
    </figure>
  ) : null;

  return (
    <div className="s5">
      <section className="desk" style={{ backgroundImage: `url(${desk})` }}>
        <article className="page">
          <img className="page-band" src={band} alt="" />
          <div className="page-body">
            {s.shadow ? (
              <p className="dim">演示保底模式下没有后端，报告由 M7 生成，这里无法预览。后端恢复后刷新页面重试。</p>
            ) : error ? (
              <p className="bad">报告预览失败：{error}</p>
            ) : md === null ? (
              <p className="dim mono">M7 正在生成预览…</p>
            ) : (
              renderMarkdown(md, figure)
            )}
          </div>
        </article>
      </section>

      <aside className="pane opts">
        <div className="panel-h"><b>导出</b><span className="dim">结果与讨论</span></div>
        <button className={"opt" + (format === "md" ? " on" : "")} onClick={() => setFormat("md")}>
          <span className="fmt mono">MD</span><span>Markdown<small>粘贴进任何编辑器</small></span>
        </button>
        <button className={"opt" + (format === "docx" ? " on" : "")} onClick={() => setFormat("docx")}>
          <span className="fmt mono">DOCX</span><span>Word<small>可直接交实验报告</small></span>
        </button>
        <button className="opt" disabled title="M7 尚未实现 png 格式">
          <span className="fmt mono">PNG</span><span>仅图表<small>M7 待实现</small></span>
        </button>
        <div className="checks">
          {INCLUDE.map(({ key, label }) => (
            <label key={key} className={"check" + (include[key] ? " on" : "")}>
              <input type="checkbox" checked={include[key]} onChange={(e) => setInclude({ ...include, [key]: e.target.checked })} />
              <i />{label}
            </label>
          ))}
        </div>
        <figure className="anchor small s5-anchor"><img src={anchor} alt="" /><figcaption className="mono">OBJ. 05 · NIB · 成文</figcaption></figure>
        <div className="actions">
          <button className="btn ghost" disabled={!md} onClick={copy}>{copied ? "已复制" : "复制 Markdown"}</button>
          <button className="btn primary grow" disabled={s.shadow || !!s.busy} onClick={download}>
            导出 {format === "md" ? "Markdown" : "Word"}
          </button>
        </div>
      </aside>
    </div>
  );
}
