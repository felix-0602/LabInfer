import type { CSSProperties, ReactNode } from "react";

// 锚点构图：秩序 × 破坏（design/index.html · 03 视觉规范；参数取自 design/storyboard.js 的 ANCHOR_FX）。
// 每件物件由同一张透明图派生出多层：
//   秩序层：超大描边词、过物件中心的刻度轴、角标框、引线标注、编号与条码
//   破坏层：钴蓝剪影套印错位、半调网点剪影、水平切片错位（偶尔抖动）、碎片、钴蓝压印色块、扫描线
// 坐标都是物件图片内的百分比（物件框按图片宽高比等比缩放，所以坐标与图片对齐）。破坏只发生在锚点区内。

interface Fx {
  ar: number;
  word: string | null;
  wordAt?: { left: string; top: string };
  sil: [number, number];
  half: [number, number];
  slices: [number, number, number][]; // [top%, height%, 平移 px]
  block: { left: number; top: number; w: number; h: number };
  shards: { poly: string; d: [number, number]; r: number }[];
  ann: { x: number; y: number; dx: number; dy: number; t: string }[];
  serial: string;
}

export type AnchorId = "GEN-03" | "GEN-06" | "GEN-07" | "GEN-08" | "GEN-09" | "GEN-10";

const FX: Record<AnchorId, Fx> = {
  "GEN-06": {
    ar: 782 / 783, word: "MODEL", wordAt: { left: "-2%", top: "2%" },
    sil: [-14, 10], half: [22, 16],
    slices: [[22, 7, 26], [61, 4, -18], [70, 2.5, 34]],
    block: { left: 58, top: 50, w: 30, h: 14 },
    shards: [{ poly: "62% 0, 100% 0, 100% 28%, 74% 34%", d: [26, -18], r: 6 }],
    ann: [
      { x: 64, y: 30, dx: 14, dy: -20, t: "C–C · 1.54 Å" },
      { x: 26, y: 27, dx: -16, dy: 18, t: "SIDE GROUP · R" },
      { x: 17, y: 93, dx: 22, dy: 0, t: "HELIX 3₁ · n = 20" },
    ],
    serial: "OBJ.01 · PAULING 1951",
  },
  "GEN-07": {
    ar: 1614 / 551, word: "READ", wordAt: { left: "-2%", top: "0" },
    sil: [-12, 9], half: [18, 14],
    slices: [[16, 10, 22], [52, 6, -16], [80, 5, 30]],
    block: { left: 44, top: 6, w: 12, h: 60 },
    shards: [{ poly: "0 62%, 26% 62%, 22% 100%, 0 100%", d: [-14, 16], r: -5 }],
    ann: [
      { x: 78, y: 24, dx: 6, dy: -40, t: "MAIN SCALE · 1 mm" },
      { x: 33, y: 30, dx: -10, dy: -44, t: "VERNIER · 0.02 mm" },
      { x: 13, y: 86, dx: 12, dy: 14, t: "JAWS · Ø ?" },
    ],
    serial: "OBJ.02 · VERNIER 1631",
  },
  "GEN-08": {
    ar: 1473 / 542, word: "SPLIT", wordAt: { left: "-2%", top: "0" },
    sil: [-10, 8], half: [16, 12],
    slices: [[34, 8, -20], [64, 5, 26], [86, 4, -12]],
    block: { left: 66, top: 58, w: 30, h: 34 },
    shards: [
      { poly: "30% 6%, 44% 6%, 37% 40%", d: [-22, -20], r: -12 },
      { poly: "48% 60%, 58% 80%, 46% 84%", d: [14, 18], r: 9 },
    ],
    ann: [
      { x: 8, y: 67, dx: -2, dy: 26, t: "WHITE IN" },
      { x: 47, y: 34, dx: 8, dy: -40, t: "n = 1.52" },
      { x: 92, y: 86, dx: -10, dy: 18, t: "SPECTRUM OUT" },
    ],
    serial: "OBJ.03 · NEWTON 1666",
  },
  "GEN-09": {
    ar: 646 / 952, word: "LAW", wordAt: { left: "4%", top: "18%" },
    sil: [-10, 6], half: [14, 10],
    slices: [[30, 6, 16], [55, 4, -14]],
    block: { left: 52, top: 36, w: 40, h: 12 },
    shards: [],
    ann: [
      { x: 8, y: 40, dx: -10, dy: -24, t: "23.4°" },
      { x: 50, y: 43, dx: 30, dy: 40, t: "KEPLER 1609" },
    ],
    serial: "OBJ.04 · 1609",
  },
  "GEN-10": {
    ar: 566 / 571, word: "WRITE", wordAt: { left: "0", top: "0" },
    sil: [-12, 10], half: [18, 12],
    slices: [[26, 7, 24], [48, 4, -18], [58, 3, 30]],
    block: { left: 52, top: 18, w: 34, h: 12 },
    shards: [{ poly: "70% 6%, 100% 20%, 92% 40%, 64% 26%", d: [18, -16], r: 8 }],
    ann: [
      { x: 42, y: 54, dx: -30, dy: -10, t: "BREATHER Ø 0.15" },
      { x: 6, y: 92, dx: -4, dy: -40, t: "INK · #1E3BFF" },
    ],
    serial: "OBJ.05 · MANUSCRIPT",
  },
  "GEN-03": {
    ar: 1, word: null,
    sil: [-14, 10], half: [20, 14],
    slices: [[30, 6, 20], [64, 4, -16]],
    block: { left: 60, top: 70, w: 34, h: 10 },
    shards: [],
    ann: [
      { x: 50, y: 44, dx: 30, dy: -26, t: "× 4 · LOUPE" },
      { x: 18, y: 63, dx: -14, dy: 16, t: "AXIS TICK" },
    ],
    serial: "OBJ.00 · LOUPE",
  },
};

const px = (x: number, y: number) => `${x}px ${y}px`;

export function Vignette({ id, src, caption, className, children }: {
  id: AnchorId;
  src: string;
  caption?: string;
  className?: string;
  children?: ReactNode;
}) {
  const fx = FX[id];
  return (
    <figure className={"anchor vfig" + (className ? " " + className : "")}>
      <div className="vignette tex-grain" style={{ "--img": `url(${src})` } as CSSProperties}>
        {fx.word && <div className="v-word display" style={fx.wordAt}>{fx.word}</div>}
        <div className="v-stage">
          <div className="v-box" style={{ "--ar": fx.ar } as CSSProperties}>
            <div className="v-axis-h" /><div className="v-axis-v" /><div className="corners" />
            <div className="v-half" style={{ translate: px(...fx.half) }} />
            <div className="v-sil" style={{ translate: px(...fx.sil) }} />
            <div className="v-obj glint"><img src={src} alt="" /></div>
            <div className="v-block" style={{ left: fx.block.left + "%", top: fx.block.top + "%", width: fx.block.w + "%", height: fx.block.h + "%" }} />
            {fx.slices.map(([top, h, shift], i) => (
              <div key={i} className="v-slice"
                style={{ clipPath: `inset(${top}% -20% ${100 - top - h}% -20%)`, "--shift": shift + "px", animationDelay: `${i * 1.3}s` } as CSSProperties} />
            ))}
            {fx.shards.map((s, i) => (
              <div key={i} className="v-shard" style={{ clipPath: `polygon(${s.poly})`, transform: `translate(${s.d[0]}px, ${s.d[1]}px) rotate(${s.r}deg)` }} />
            ))}
            <div className="v-scan" />
            {fx.ann.map((a) => (
              <div key={a.t} className={"v-tag" + (a.dx < 0 ? " left" : "")} style={{ left: a.x + "%", top: a.y + "%" }}>
                <i className="dot" />
                <i className="lead" style={{ width: Math.hypot(a.dx, a.dy), transform: `rotate(${Math.atan2(a.dy, a.dx)}rad)` }} />
                <span style={{ left: a.dx, top: a.dy }}>{a.t}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="v-serial"><i className="barcode" /><span>{fx.serial}</span></div>
      </div>
      {children}
      {caption && <figcaption className="mono">{caption}</figcaption>}
    </figure>
  );
}
