import { useLayoutEffect, useRef, type ReactNode } from "react";
import { GuideProvider } from "./guide";
import { STEPS, useWorkbench } from "./workbench";

export function Shell({ children }: { children: ReactNode }) {
  const { s, dispatch } = useWorkbench();
  const current = STEPS.find((x) => x.step === s.step);
  const ids = [s.ctx?.id, s.dataset?.id].filter(Boolean).join(" · ");
  const stage = useRef<HTMLElement>(null);
  const railIndex = STEPS.findIndex((x) => x.step === s.step);

  // 换屏后回到顶部，新屏的进场动画从第一行开始
  useLayoutEffect(() => { stage.current?.scrollTo(0, 0); }, [s.step]);

  return (
    <div className="shell">
      {/* 导读面板与浮卡作为 shell 的网格子元素，叠在工作区上 */}
      <GuideProvider guide={s.ctx?.guide ?? null}>
      <nav className="rail">
        <button className="logo" onClick={() => dispatch({ type: "go", step: 0 })} title="回到封面">L<i>I</i></button>
        {railIndex >= 0 && <span className="rail-ind" style={{ transform: `translateY(${railIndex * 72}px)` }} />}
        {STEPS.map(({ step, label }) => {
          const reachable = !!s.ctx && (step <= s.step || s.done.has(step) || s.done.has((step - 1) as typeof step));
          return (
            <button
              key={step}
              className={"rail-step" + (s.step === step ? " on" : "")}
              disabled={!reachable}
              onClick={() => dispatch({ type: "go", step })}
            >
              <span className="mono">0{step}{s.done.has(step) && <span className="ok"> ✓</span>}</span>
              <span>{label}</span>
            </button>
          );
        })}
        <div className="halftone fade-t rail-mood" />
        <div className="rail-foot mono">SCHEMA {s.ctx?.schema_version ?? "—"}</div>
      </nav>
      <header className={"topbar" + (s.busy ? " is-busy" : "")}>
        <b>{s.ctx?.name.split("（")[0] ?? "LabInfer"}</b>
        <span className="mono dim">{ids}</span>
        <span className="spacer" />
        {s.busy && <span key={s.busy} className="busy mono">{s.busy}…</span>}
        <span className={"badge mono" + (s.shadow ? " warn" : "")}>{s.shadow ? "演示保底数据" : "真实数据"}</span>
      </header>
      {s.notice && (
        <div key={s.notice.text} className={"notice " + s.notice.tone}>
          {s.notice.text}
          <button className="link" onClick={() => dispatch({ type: "patch", patch: { notice: null } })}>知道了</button>
        </div>
      )}
      <main className="stage" ref={stage}><div className="screen" key={s.step}>{children}</div></main>
      <footer className="statusbar mono">
        <i className="barcode" />
        <span>{current?.module}</span>
        <span className="spacer" />
        <span>{s.online === false ? "后端离线" : s.online ? "后端在线" : "探测后端中"}</span>
      </footer>
      </GuideProvider>
    </div>
  );
}
