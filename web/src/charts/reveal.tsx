import type { CSSProperties, ReactNode, SVGProps } from "react";
import "./reveal.css";
import { fmt } from "./scale";

// 图表动画模板：每张图都按同一条时间线进场，新图表只要把元素放进对应的「层」，动效自动对齐。
//
//   时间线（reveal.css 里的 --c-at-* 变量统一控制）
//   0ms     Frame   网格、坐标轴、轴标题淡入
//   120ms   Band    参考区（允许带、变色区、计量点线）纵向展开
//   160ms   Draw    主曲线 / 拟合线描出来（pathLength=1 + dasharray）
//   560ms+  Mark    数据点逐个弹出，每个间隔 --c-step（80ms），i 是序号
//   700ms   Fade    标注、次要曲线、图例
//   80ms+   Bar     横条从左长出，按行序号错开
//   随时    Sim     推演叠加层，key 变化就重播
//   随时    Flash   结论流式出现时，它引用的点闪一圈（flash.key 变化即重播）
//
// 适配一张新图表：
//   1. 外层用 <Chart w h label>，坐标比例照旧用 scale.ts 的 linear / niceTicks
//   2. 网格坐标轴放进 <Frame>（可直接用 <GridY>/<GridX>），参考区放 <Band>，主线用 <Draw>/<DrawLine>
//   3. 每个数据点包一层 <Mark i id onHover>，里面画圆点、标签和 <Flash>；横条图用 <Bar i> + <GrowRect>
//   props 类型直接继承 ChartInteraction，Analysis 页的 chartProps 就能原样传进来
//   切 tab 时外面的 .chart-box 换 key，整张图重放；prefers-reduced-motion 下所有层直接落在终态。

/** 图表共用的交互属性：高亮、异常、悬停联动、结论闪烁 */
export interface ChartInteraction {
  highlight: Set<string>;
  // 红色只给异常：由 M5 异常结论引用的点决定，前端不自行判定
  anomalies: Set<string>;
  onHover: (pointId: string | null) => void;
  // 结论流式出现时，它引用的点闪一下（key 变化即重播）
  flash?: { ids: Set<string>; key: number };
}

export function Chart({ w, h, label, children }: { w: number; h: number; label: string; children: ReactNode }) {
  return <svg className="chart" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label}>{children}</svg>;
}

type G = SVGProps<SVGGElement>;
const layer = (cls: string) => function Layer({ className, ...rest }: G) {
  return <g className={cls + (className ? " " + className : "")} {...rest} />;
};

/** 网格、坐标轴、轴标题 */
export const Frame = layer("c-frame");
/** 参考区：允许带、变色区、计量点线 */
export const Band = layer("c-band");
/** 标注、次要曲线、图例 */
export const Fade = layer("c-fade");
/** 推演叠加层：给它一个随推演值变化的 key */
export const Sim = layer("c-sim");

/** 主曲线：自动描线 */
export function Draw({ className, ...rest }: SVGProps<SVGPathElement>) {
  return <path {...rest} className={"c-draw" + (className ? " " + className : "")} pathLength={1} />;
}
/** 主直线（拟合线等）：自动描线 */
export function DrawLine({ className, ...rest }: SVGProps<SVGLineElement>) {
  return <line {...rest} className={"c-draw" + (className ? " " + className : "")} pathLength={1} />;
}

/** 一个数据点：按序号 i 错开弹出，悬停联动 */
export function Mark({ i, id, onHover, className, children }: {
  i: number; id: string; onHover: ChartInteraction["onHover"]; className?: string; children: ReactNode;
}) {
  return (
    <g className={"pt-group c-pop" + (className ? " " + className : "")} style={{ "--i": i } as CSSProperties}
      onMouseEnter={() => onHover(id)} onMouseLeave={() => onHover(null)}>
      {children}
    </g>
  );
}

/** 结论引用到这个点时闪一圈；没被引用就不渲染 */
export function Flash({ flash, id, cx, cy, bad }: { flash?: ChartInteraction["flash"]; id: string; cx: number; cy: number; bad?: boolean }) {
  if (!flash?.ids.has(id)) return null;
  return <circle key={flash.key} className={"flash" + (bad ? " bad" : "")} cx={cx} cy={cy} r={6} />;
}

/** 横条图的一行：整行淡入，条从左长出 */
export function Bar({ i, children }: { i: number; children: ReactNode }) {
  return <g className="c-row" style={{ "--i": i } as CSSProperties}>{children}</g>;
}
/** 横条本身：从左长出 */
export function GrowRect({ className, ...rest }: SVGProps<SVGRectElement>) {
  return <rect {...rest} className={"c-grow" + (className ? " " + className : "")} />;
}

/** 横向网格 + 纵轴刻度 */
export function GridY({ ticks, sy, x0, x1, digits = 2 }: { ticks: number[]; sy: (v: number) => number; x0: number; x1: number; digits?: number }) {
  return <>{ticks.map((t) => (
    <g key={"y" + t}>
      <line className="grid" x1={x0} x2={x1} y1={sy(t)} y2={sy(t)} />
      <text className="tick" x={x0 - 8} y={sy(t) + 4} textAnchor="end">{fmt(t, digits)}</text>
    </g>
  ))}</>;
}

/** 纵向网格 + 横轴刻度 */
export function GridX({ ticks, sx, y0, y1, digits = 2 }: { ticks: number[]; sx: (v: number) => number; y0: number; y1: number; digits?: number }) {
  return <>{ticks.map((t) => (
    <g key={"x" + t}>
      <line className="grid" x1={sx(t)} x2={sx(t)} y1={y0} y2={y1} />
      <text className="tick" x={sx(t)} y={y1 + 18} textAnchor="middle">{fmt(t, digits)}</text>
    </g>
  ))}</>;
}
