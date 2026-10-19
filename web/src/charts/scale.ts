// 只做画图用的坐标映射与刻度，不参与任何科学计算。

export function linear(d0: number, d1: number, r0: number, r1: number) {
  const k = (r1 - r0) / (d1 - d0 || 1);
  return (v: number) => r0 + (v - d0) * k;
}

export function niceTicks(lo: number, hi: number, count = 5): number[] {
  const span = hi - lo || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

export function pad([lo, hi]: [number, number], frac = 0.08): [number, number] {
  const d = (hi - lo || Math.abs(hi) || 1) * frac;
  return [lo - d, hi + d];
}

export function extent(vals: number[]): [number, number] {
  return [Math.min(...vals), Math.max(...vals)];
}

export const fmt = (v: number, digits = 4) => +v.toFixed(digits) + "";
