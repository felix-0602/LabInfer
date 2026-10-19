import bg from "../../../design/assets/GEN-02.webp";
// 封面主视觉：银镜试管 GEN-01
import hero from "../../../design/assets/GEN-01.webp";
import { useWorkbench } from "../workbench";

export function Cover() {
  const { s, loadDemo } = useWorkbench();
  const c = s.analysis?.fits[0]?.derived?.c_hcl;
  return (
    <div className="cover" style={{ backgroundImage: `url(${bg})` }}>
      <div className="cover-top mono">
        <span>LABINFER — RESEARCH INSTRUMENT</span>
        <span>HACKATHON 2026 · 科研创新赛道</span>
        <span>N° 001</span>
      </div>
      <img className="cover-hero" src={hero} alt="" />
      <div className="cover-giant display">
        <div>LAB</div>
        <div className="fill">INFER</div>
      </div>
      <div className="cover-tag">
        <h1>拍下数据，截下文献。<br />得到的不只是结果，<b>还有结论。</b></h1>
        <p>规律、能证明什么、哪里不对、下次怎么改。</p>
        <button className="btn primary" onClick={loadDemo} disabled={!!s.busy || s.online === null}>
          {s.busy ?? "载入演示案例 · HCl 标定与碱灰总碱度 →"}
        </button>
      </div>
      <div className="cover-readout mono">
        CASE&nbsp;&nbsp;&nbsp;<b>001 · TITRATION</b><br />
        MODEL&nbsp;&nbsp;<b>STANDARDIZATION</b><br />
        c(HCl)&nbsp;{c != null ? <b>{c.toFixed(4)} mol·L⁻¹</b> : <span className="q">? mol·L⁻¹</span>}<br />
        REF&nbsp;&nbsp;&nbsp;&nbsp;GB/T 601-2016
      </div>
      <div className="cover-bottom mono">
        <span>01 CONTEXT — 02 DATA — 03 LITERATURE — 04 ANALYSIS — 05 EXPORT</span>
        <span>{s.online === false ? "BACKEND OFFLINE · 将载入演示保底" : "FROM DATA TO CONCLUSION"}</span>
      </div>
    </div>
  );
}
