import { useRef, type CSSProperties, type PointerEvent } from "react";
import bg from "../../../design/assets/GEN-02.webp";
// 封面主视觉：银镜试管 GEN-01
import hero from "../../../design/assets/GEN-01.webp";
import { CountUp, reducedMotion, stagger } from "../motion";
import { useWorkbench } from "../workbench";

export function Cover() {
  const { s, loadDemo } = useWorkbench();
  // 问号只在走到分析页之后才被填上（storyboard S0）
  const solved = s.done.has(3) || s.done.has(4);
  const c = solved ? s.analysis?.fits[0]?.derived?.c_hcl : null;
  const root = useRef<HTMLDivElement>(null);

  // 视差：指针位置写进 CSS 变量，各图层按自己的深度位移，不触发 React 重渲染
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== "mouse" || reducedMotion() || !root.current) return;
    const r = root.current.getBoundingClientRect();
    root.current.style.setProperty("--mx", ((e.clientX - r.left) / r.width * 2 - 1).toFixed(3));
    root.current.style.setProperty("--my", ((e.clientY - r.top) / r.height * 2 - 1).toFixed(3));
  };

  return (
    <div className="cover tex-grain" ref={root} style={{ backgroundImage: `url(${bg})` }} onPointerMove={onMove}>
      <div className="cover-top mono">
        <span>LABINFER — RESEARCH INSTRUMENT</span>
        <span>HACKATHON 2026 · 科研创新赛道</span>
        <span>N° 001</span>
      </div>
      <div className="halftone fade-radial cover-glow" />
      <div className="cover-hero">
        <span className="glint" style={{ "--img": `url(${hero})` } as CSSProperties}>
          <img src={hero} alt="" />
          <i className="drop" />
        </span>
      </div>
      <div className="cover-giant display">
        <div className="line">LAB</div>
        <div className="line fill glitch-static" data-text="INFER"><span className="glitch" data-text="INFER">INFER</span></div>
      </div>
      <div className="crease-v" style={{ left: "50%" }} />
      <div className="crease-h" style={{ top: "58%" }} />
      <span className="side-label">HCl STANDARDIZATION · Na₂CO₃ PRIMARY STANDARD</span>
      <div className="ruler-v" style={{ left: 24, top: 120, height: 100 }} />
      <div className="cross" style={{ left: 44, top: 96 }} />
      <div className="cross" style={{ right: 44, top: 96 }} />
      <div className="cover-tag">
        <h1 className="rv" style={stagger(0)}>拍下数据，截下文献。<br />得到的不只是结果，<b>还有结论。</b></h1>
        <p className="rv" style={stagger(1)}>规律、能证明什么、哪里不对、下次怎么改。</p>
        <button className="btn primary sheen rv" style={stagger(2)} onClick={loadDemo} disabled={!!s.busy || s.online === null}>
          {s.busy ?? "载入演示案例 · HCl 标定与碱灰总碱度 →"}
        </button>
      </div>
      <div className="cover-readout mono">
        <div className="rv" style={stagger(0)}>CASE&nbsp;&nbsp;&nbsp;<b>001 · TITRATION</b></div>
        <div className="rv" style={stagger(1)}>MODEL&nbsp;&nbsp;<b>STANDARDIZATION</b></div>
        <div className="rv" style={stagger(2)}>c(HCl)&nbsp;{c != null
          ? <b className="solved"><CountUp value={c} digits={4} delay={1500} duration={1200} /> mol·L⁻¹</b>
          : <span className="q blink">? mol·L⁻¹</span>}</div>
        <div className="rv" style={stagger(3)}>REF&nbsp;&nbsp;&nbsp;&nbsp;GB/T 601-2016</div>
      </div>
      <div className="cover-bottom mono">
        <span>01 CONTEXT — 02 DATA — 03 LITERATURE — 04 ANALYSIS — 05 EXPORT</span>
        <span>{s.online === false ? "BACKEND OFFLINE · 将载入演示保底" : "FROM DATA TO CONCLUSION"}</span>
      </div>
    </div>
  );
}
