import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { flushSync } from "react-dom";

// 动效系统的 JS 部分：转场方向、数字滚动、锚点物件的镀铬掠光、分段切换的滑块。
// 时长与曲线定义在 motion.css 的 :root token 里，这里只放必须用 JS 驱动的部分。

export const reducedMotion = () =>
  typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

// 结论卡片流式出现的间隔（影子快照一次性到齐时，按这个间隔逐条放出）
export const STREAM_GAP = 260;

export type NavKind = "fwd" | "back" | "cover-out" | "cover-in";

// 切换步骤：支持 View Transitions 的浏览器用它做整屏转场，其余直接切换（屏内元素仍有进场动画）
export function navigate(kind: NavKind, update: () => void) {
  const root = document.documentElement;
  if (reducedMotion() || typeof document.startViewTransition !== "function") {
    update();
    return;
  }
  root.dataset.nav = kind;
  const vt = document.startViewTransition(() => flushSync(update));
  vt.finished.finally(() => { if (root.dataset.nav === kind) delete root.dataset.nav; });
}

const easeOutExpo = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

// 数字滚动到目标值。等宽数字，避免滚动时抖动；减少动态效果时直接显示结果
export function CountUp({ value, digits, delay = 0, duration = 900 }: { value: number; digits: number; delay?: number; duration?: number }) {
  const [shown, setShown] = useState(() => (reducedMotion() ? value : 0));
  const from = useRef(shown);

  useEffect(() => {
    if (reducedMotion()) { setShown(value); return; }
    const start = from.current;
    let raf = 0;
    const t0 = performance.now() + delay;
    const tick = (now: number) => {
      const t = Math.max(0, (now - t0) / duration);
      const v = start + (value - start) * easeOutExpo(t);
      from.current = v;
      setShown(v);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, delay, duration]);

  return <span className="num">{shown.toFixed(digits)}</span>;
}

// 意象锚点物件：进场时一道镀铬掠光沿物件轮廓扫过（遮罩取图片本身的 alpha）
export function Anchor({ src, caption, className }: { src: string; caption?: string; className?: string }) {
  return (
    <figure className={"anchor" + (className ? " " + className : "")}>
      <span className="glint" style={{ "--img": `url(${src})` } as CSSProperties}>
        <img src={src} alt="" />
      </span>
      {caption && <figcaption className="mono">{caption}</figcaption>}
    </figure>
  );
}

// 分段切换：选中态是一块滑动的底板，不是逐个按钮换底色
export function Segmented<T extends string>({ items, value, label, onChange, children }: {
  items: T[];
  value: T | null;
  label: (t: T) => string;
  onChange: (t: T) => void;
  children?: ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [ind, setInd] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  useLayoutEffect(() => {
    const el = box.current?.querySelector<HTMLButtonElement>("button.on");
    setInd(el ? { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight } : null);
  }, [value, items.length]);

  return (
    <div className="seg" ref={box}>
      {ind && <span className="seg-ind" style={{ transform: `translate(${ind.x}px, ${ind.y}px)`, width: ind.w, height: ind.h }} />}
      {items.map((t) => (
        <button key={t} className={t === value ? "on" : ""} onClick={() => onChange(t)}>{label(t)}</button>
      ))}
      {children}
    </div>
  );
}

// 交错进场：给第 i 个元素的延迟
export const stagger = (i: number): CSSProperties => ({ "--i": i } as CSSProperties);
