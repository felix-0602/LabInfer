import {
  createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState,
  type CSSProperties, type ReactNode,
} from "react";
import "./guide.css";
import { reducedMotion } from "./motion";
import type { Guide, GuideSection, GuideSource } from "./types";

// 教学导读层（契约 0.8.0 · docs/wiki.md#表达标准）的前端：
//   Rich        结论、讲解阶梯、导读正文里的 [文字](term:id) / [62.58](num:62.578) 标记
//   卡片        术语解释卡与 01 页字段人话共用一张浮卡，同一时间只开一张
//   GuidePanel  右侧阅读面板，01 / 03 / 04 三页共用，一次读一节，带目录与上一节、下一节
//   GuideEntry  01、03 页的导读入口：本页各节的标题与一句话摘要

export type GuidePage = "context" | "literature" | "all";

interface CardData {
  kicker?: string;      // 卡片顶上的小字：原始字段键名，或「术语」
  title: string;
  plain: string;
  help?: string;
  source?: GuideSource | null;
}

interface GuideApi {
  guide: Guide | null;
  openCard: (card: CardData, el: HTMLElement) => void;
  openTerm: (termId: string, el: HTMLElement) => void;
  openGuide: (page: GuidePage, sectionId?: string) => void;
  sectionFor: (rungId: string) => GuideSection | null;
}

const GuideCtx = createContext<GuideApi>({
  guide: null, openCard: () => {}, openTerm: () => {}, openGuide: () => {}, sectionFor: () => null,
});
export const useGuide = () => useContext(GuideCtx);

// 本页要显示的节：context / literature 按 show_in 过滤，all（从 04 页跳进来）先 01 的再 03 独有的
export function sectionsOf(guide: Guide, page: GuidePage): GuideSection[] {
  const by = (p: "context" | "literature") =>
    guide.sections.filter((x) => x.show_in.includes(p)).sort((a, b) => a.order - b.order);
  if (page !== "all") return by(page);
  const ctx = by("context");
  return [...ctx, ...by("literature").filter((x) => !ctx.includes(x))];
}

// 演示里只显示核实过的出处（verified: false 即「待核」，整节不因此消失）
const verifiedSource = (guide: Guide | null, id?: string | null) =>
  guide?.sources.find((x) => x.source_id === id && x.verified) ?? null;

const EXIT_MS = 180;

/** 在出场动画结束后再卸载；减少动态效果时立刻卸载 */
function useExit<T>(value: T | null): [T | null, boolean] {
  const [shown, setShown] = useState(value);
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    if (value) { setShown(value); setLeaving(false); return; }
    if (!shown) return;
    if (reducedMotion()) { setShown(null); return; }
    setLeaving(true);
    const t = setTimeout(() => { setShown(null); setLeaving(false); }, EXIT_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return [value ?? shown, leaving];
}

export function GuideProvider({ guide, children }: { guide: Guide | null; children: ReactNode }) {
  const [card, setCard] = useState<{ data: CardData; el: HTMLElement } | null>(null);
  const [panel, setPanel] = useState<{ page: GuidePage; index: number } | null>(null);

  const openCard = useCallback((data: CardData, el: HTMLElement) => {
    // 再点同一个触发点 = 收起
    setCard((c) => (c?.el === el ? null : { data, el }));
  }, []);

  const openTerm = useCallback((termId: string, el: HTMLElement) => {
    const t = guide?.glossary.find((x) => x.term_id === termId);
    if (!t) return;
    openCard({ kicker: "术语", title: t.term, plain: t.plain, help: t.help, source: verifiedSource(guide, t.source) }, el);
  }, [guide, openCard]);

  const openGuide = useCallback((page: GuidePage, sectionId?: string) => {
    if (!guide) return;
    const list = sectionsOf(guide, page);
    setCard(null);
    setPanel({ page, index: Math.max(0, list.findIndex((x) => x.section_id === sectionId)) });
  }, [guide]);

  const sectionFor = useCallback((rungId: string) => guide?.sections.find((x) => x.rung_id === rungId) ?? null, [guide]);

  // 换实验（guide 变了）时收起所有浮层
  useEffect(() => { setCard(null); setPanel(null); }, [guide]);

  const api = useMemo(() => ({ guide, openCard, openTerm, openGuide, sectionFor }), [guide, openCard, openTerm, openGuide, sectionFor]);

  return (
    <GuideCtx.Provider value={api}>
      {children}
      {guide && (
        <GuidePanel guide={guide} state={panel} onIndex={(index) => setPanel((p) => (p ? { ...p, index } : p))}
          onClose={() => { setCard(null); setPanel(null); }} />
      )}
      <FloatCard card={card} onClose={() => setCard(null)} />
    </GuideCtx.Provider>
  );
}

/* ---------------- 标记渲染 ---------------- */

const MARK = /\[([^\]]+)\]\((term|num):([^)\s]+)\)/g;

/** 渲染 M5 / 导读文本里的两类标记；不认识的术语按原文显示 */
export function Rich({ text }: { text: string }) {
  const { guide } = useGuide();
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(MARK)) {
    const [all, label, kind, val] = m;
    const at = m.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    if (kind === "term" && guide?.glossary.some((x) => x.term_id === val)) out.push(<Term key={at} id={val}>{label}</Term>);
    else if (kind === "num") out.push(<Num key={at} shown={label} full={val} />);
    else out.push(label);
    last = at + all.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return <>{out}</>;
}

function Term({ id, children }: { id: string; children: ReactNode }) {
  const { openTerm } = useGuide();
  return (
    <button type="button" className="term" onClick={(e) => { e.stopPropagation(); openTerm(id, e.currentTarget); }}>
      {children}
    </button>
  );
}

// 正文按报告位数写，点开看分析结果里的全精度原值
function Num({ shown, full }: { shown: string; full: string }) {
  const [open, setOpen] = useState(false);
  if (shown === full) return <span className="num">{shown}</span>;
  return (
    <button type="button" className={"num-mark num" + (open ? " open" : "")} title={open ? "收起全精度" : "看全精度"}
      onClick={(e) => { e.stopPropagation(); setOpen(!open); }}>
      <span key={String(open)}>{open ? full : shown}</span>
    </button>
  );
}

/** 多段正文：空行分段 */
export function RichBody({ text }: { text: string }) {
  return <>{text.split(/\n{2,}/).map((p, i) => <p key={i}><Rich text={p} /></p>)}</>;
}

/* ---------------- 浮卡 ---------------- */

function FloatCard({ card, onClose }: { card: { data: CardData; el: HTMLElement } | null; onClose: () => void }) {
  const [shown, leaving] = useExit(card);
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number; above: boolean } | null>(null);

  useLayoutEffect(() => {
    if (!card || !ref.current) return;
    const r = card.el.getBoundingClientRect();
    const w = ref.current.offsetWidth, h = ref.current.offsetHeight;
    const above = r.bottom + 10 + h > window.innerHeight - 40 && r.top - 10 - h > 60;
    setPos({
      left: Math.min(Math.max(12, r.left + r.width / 2 - w / 2), window.innerWidth - w - 12),
      top: above ? r.top - 10 - h : r.bottom + 10,
      above,
    });
  }, [card]);

  // 点卡外、按 Esc、页面滚动：收起
  useEffect(() => {
    if (!card) return;
    const down = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!ref.current?.contains(t) && !card.el.contains(t)) onClose();
    };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    const scroll = (e: Event) => { if (!ref.current?.contains(e.target as Node)) onClose(); };
    document.addEventListener("pointerdown", down);
    document.addEventListener("keydown", key, true);
    document.addEventListener("scroll", scroll, true);
    return () => {
      document.removeEventListener("pointerdown", down);
      document.removeEventListener("keydown", key, true);
      document.removeEventListener("scroll", scroll, true);
    };
  }, [card, onClose]);

  if (!shown) return null;
  const d = shown.data;
  return (
    <div ref={ref} role="dialog" aria-label={d.title}
      className={"float-card" + (pos?.above ? " above" : "") + (leaving ? " leaving" : "")}
      style={pos ? { left: pos.left, top: pos.top } : { visibility: "hidden", left: 0, top: 0 }}>
      {d.kicker && <div className="kicker mono">{d.kicker}</div>}
      <b className="fc-title">{d.title}</b>
      <p>{d.plain}</p>
      {d.help && <p className="help">{d.help}</p>}
      {d.source && <div className="src mono">出处 · {d.source.title}{d.source.locator ? ` · ${d.source.locator}` : ""}</div>}
    </div>
  );
}

/* ---------------- 阅读面板 ---------------- */

const PAGE_LABEL: Record<GuidePage, string> = { context: "01 实验上下文", literature: "03 文献取数", all: "全部章节" };

function GuidePanel({ guide, state, onIndex, onClose }: {
  guide: Guide;
  state: { page: GuidePage; index: number } | null;
  onIndex: (i: number) => void;
  onClose: () => void;
}) {
  const [shown, leaving] = useExit(state);
  const [toc, setToc] = useState(false);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const back = useRef<HTMLElement | null>(null);
  const list = shown ? sectionsOf(guide, shown.page) : [];

  // 打开时把焦点放到关闭按钮，关上后还给打开它的元素
  useEffect(() => {
    if (state) {
      back.current = document.activeElement as HTMLElement | null;
      closeBtn.current?.focus({ preventScroll: true });
    } else {
      back.current?.focus?.({ preventScroll: true });
      setToc(false);
    }
  }, [!!state]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { body.current?.scrollTo(0, 0); }, [state?.index]);

  useEffect(() => {
    if (!state) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" && e.altKey) onIndex(Math.min(state.index + 1, list.length - 1));
      if (e.key === "ArrowLeft" && e.altKey) onIndex(Math.max(state.index - 1, 0));
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  });

  if (!shown) return null;
  const i = Math.min(shown.index, list.length - 1);
  const sec = list[i];
  if (!sec) return null;
  const prev = list[i - 1], next = list[i + 1];
  const sources = (sec.sources ?? []).map((id) => verifiedSource(guide, id)).filter((x): x is GuideSource => !!x);

  return (
    <div className={"guide-layer" + (leaving ? " leaving" : "")}>
      <div className="guide-scrim" onClick={onClose} />
      <aside className="guide-panel" role="dialog" aria-modal="true" aria-label="实验导读">
        <header className="gp-head">
          <span className="eyebrow mono">导读 · {PAGE_LABEL[shown.page]}</span>
          {guide.status === "draft" && <span className="badge mono warn">AI 生成，待核</span>}
          <span className="spacer" />
          <button className="gp-x" ref={closeBtn} onClick={onClose} aria-label="关闭导读">×</button>
        </header>
        <nav className="gp-progress" aria-label="章节">
          <button className={"gp-toc-btn mono" + (toc ? " on" : "")} aria-expanded={toc} onClick={() => setToc(!toc)}>
            {String(i + 1).padStart(2, "0")} / {String(list.length).padStart(2, "0")} · 目录
          </button>
          <div className="gp-ticks">
            {list.map((x, k) => (
              <button key={x.section_id} className={k === i ? "on" : k < i ? "read" : ""} title={x.title}
                aria-label={x.title} onClick={() => { onIndex(k); setToc(false); }} />
            ))}
          </div>
        </nav>
        {toc && (
          <ol className="gp-toc">
            {list.map((x, k) => (
              <li key={x.section_id} className={k === i ? "on" : ""} style={{ "--i": k } as CSSProperties}>
                <button onClick={() => { onIndex(k); setToc(false); }}>
                  <span className="mono">{String(k + 1).padStart(2, "0")}</span>
                  <span><b>{x.title}</b><span className="dim">{x.summary}</span></span>
                </button>
              </li>
            ))}
          </ol>
        )}
        <div className="gp-body" ref={body}>
          <article key={sec.section_id} className="gp-section">
            <div className="gp-num display">{String(i + 1).padStart(2, "0")}</div>
            <h2>{sec.title}</h2>
            <p className="gp-lead">{sec.summary}</p>
            <div className="gp-text"><RichBody text={sec.body} /></div>
            {sources.length > 0 && (
              <ul className="gp-src mono">
                {sources.map((x) => <li key={x.source_id}>出处 · {x.title}{x.locator ? ` · ${x.locator}` : ""}</li>)}
              </ul>
            )}
          </article>
        </div>
        <footer className="gp-foot">
          <button className="gp-nav prev" disabled={!prev} onClick={() => onIndex(i - 1)}>
            <span className="mono dim">← 上一节</span><span>{prev?.title ?? "已是第一节"}</span>
          </button>
          <button className="gp-nav next" disabled={!next} onClick={() => onIndex(i + 1)}>
            <span className="mono dim">下一节 →</span><span>{next?.title ?? "已读完"}</span>
          </button>
        </footer>
      </aside>
    </div>
  );
}

/* ---------------- 入口 ---------------- */

/** 本页导读入口：各节标题 + 一句话摘要，点哪节就从哪节读起 */
export function GuideEntry({ page, className, style }: { page: "context" | "literature"; className?: string; style?: CSSProperties }) {
  const { guide, openGuide } = useGuide();
  if (!guide) return null;
  const list = sectionsOf(guide, page);
  if (!list.length) return null;
  const chars = list.reduce((n, x) => n + x.body.replace(MARK, "$1").length, 0);
  return (
    <div className={"guide-entry" + (className ? " " + className : "")} style={style}>
      <div className="ge-head">
        <span className="eyebrow mono">导读 · {list.length} 节 · 约 {Math.max(1, Math.round(chars / 400))} 分钟</span>
        {guide.status === "draft" && <span className="badge mono warn">AI 生成，待核</span>}
        <span className="spacer" />
        <button className="link mono" onClick={() => openGuide(page)}>从头读 →</button>
      </div>
      <ol>
        {list.map((x, k) => (
          <li key={x.section_id} style={{ "--i": k } as CSSProperties}>
            <button onClick={() => openGuide(page, x.section_id)}>
              <span className="mono">{String(k + 1).padStart(2, "0")}</span>
              <span><b>{x.title}</b><span className="dim">{x.summary}</span></span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** 01 页字段人话：标签替换原始键名，键名缩到下面一行；点开看一句解释 */
export function FieldLabel({ path, fallback, children }: { path: string; fallback: string; children?: ReactNode }) {
  const { guide, openCard } = useGuide();
  const note = guide?.field_notes[path];
  if (!note) return <span className="field raw mono">{fallback}{children}</span>;
  const term = note.term_id ? guide?.glossary.find((x) => x.term_id === note.term_id) : null;
  return (
    <button type="button" className="field" onClick={(e) => openCard({
      kicker: fallback, title: note.label, plain: note.plain, help: term?.help,
      source: term ? verifiedSource(guide, term.source) : null,
    }, e.currentTarget)}>
      <span className="f-label">{note.label}{children}<i className="q" aria-hidden>?</i></span>
      <span className="f-key mono">{fallback}</span>
    </button>
  );
}
