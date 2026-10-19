import anchor from "../../../design/assets/GEN-03.webp";
import { useWorkbench } from "../workbench";

// M2 曲线取数在 feat/m2-curve-extract 上开发，合并后在这里接入校准画布。
// 契约 0.5.0：滴定演示的参照是理论值与标准条文，这一步可以跳过。
export function Literature() {
  const { s, dispatch } = useWorkbench();
  const hasLitRefs = (s.ctx?.reference.datasets.length ?? 0) > 0;
  return (
    <div className="split">
      <section className="pane main-pane center">
        <div className="display ghost-word">FIGURE → DATA</div>
        <figure className="anchor"><img src={anchor} alt="" /></figure>
        <h2>把论文里的图交给它</h2>
        <p className="dim">
          {hasLitRefs
            ? "文献取数画布正在接入中。"
            : "这个模板的参照是理论值与 GB/T 601-2016 条文，不需要文献曲线，可以直接进入分析。"}
        </p>
        <div className="actions">
          <button className="btn primary" disabled={!s.analysis} onClick={() => dispatch({ type: "complete", step: 3, next: 4 })}>
            跳过，进入分析 →
          </button>
        </div>
        {!s.analysis && <p className="mono dim small">{s.busy ?? "等待 M4 计算结果"}</p>}
      </section>
    </div>
  );
}
