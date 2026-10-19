import type { AxisCalibration } from "../types";

// 画布光标读数用的像素→数值换算，公式与 M2 相同（contracts.md「坐标换算」）。
// 只用于显示，写进数据集的数值以 M2 提取接口的结果为准（architecture.md · M8）。
export function pxToValue(axis: "x" | "y", cal: AxisCalibration, px: [number, number]): number | null {
  const i = axis === "x" ? 0 : 1;
  const c1 = cal.p1.px[i], c2 = cal.p2.px[i];
  let a1 = cal.p1.value, a2 = cal.p2.value;
  if (c1 === c2) return null;
  if (cal.scale === "log10") {
    if (a1 <= 0 || a2 <= 0) return null;
    a1 = Math.log10(a1);
    a2 = Math.log10(a2);
  }
  const t = a1 + (px[i] - c1) * (a2 - a1) / (c2 - c1);
  return cal.scale === "log10" ? 10 ** t : t;
}
