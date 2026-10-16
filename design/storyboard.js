/* =========================================================
   LabInfer 设计稿 · 脚本
   1. 素材位清单（唯一真相源）与加载
   2. 画框缩放
   3. 示意图表
   ========================================================= */

/* ---------- 1. 素材位清单 ----------
   图片统一放在 design/assets/，文件名 = 编号.扩展名（加载顺序 webp → png → jpg），刷新即生效。
   kind:
     GEN   = 我们自己生成：Blender 渲染 + ImageMagick 后处理，脚本在 design/render/，
             要改就改脚本后执行 render.sh 重新出图，不要手工替换图片
     PHOTO = 真实照片，需上网检索（注意授权）；页面会自动做钴蓝双色调，原图无需调色
     DEMO  = 演示数据图，必须是真实实验记录 / 真实论文截图，不能用 AI 生成或编造
     ART   = 美术手绘或设计的素材（当前没有）
   refs 对应设计稿「01 审美拆解」里的参考图编号 R1–R13。 */
const ASSET_SLOTS = [
  {
    id: "GEN-01",
    kind: "GEN",
    name: "封面主视觉：银镜试管",
    where: "S0 封面，画面中右，压在超大标题之上",
    ratio: "7:9 竖幅",
    size: "1400 × 1800 px",
    format: "WebP，透明背景",
    content: "玻璃试管内壁镀着上沿不规则的银镜层，上沿之上散落成核银斑；液态银从管口溢出、沿外壁淌下；周围悬浮银珠。",
    style: "R2 铬银棋子、R6 液态金属。影棚：暗场 + 白色长条灯 + 钴蓝灯板，反射里带品牌色。",
    note: "脚本 render/tube.py",
  },
  {
    id: "GEN-02",
    kind: "GEN",
    name: "封面背景：钴蓝暗场烟雾",
    where: "S0 封面，全幅背景",
    ratio: "16:10",
    size: "2880 × 1800 px",
    format: "WebP",
    content: "域扭曲噪声生成的钴蓝烟雾，在主视觉所在位置（画面 62%, 50%）偏亮，四周压暗；带星尘和胶片颗粒。平均亮度约 9%。",
    style: "R1 的蓝色烟雾与星点、R5 的胶片颗粒。",
    note: "脚本 render/smoke.py（night）",
  },
  {
    id: "GEN-03",
    kind: "GEN",
    name: "取数空状态：玻璃球放大镜",
    where: "S3a 文献取数空状态，拖放区中央",
    ratio: "1:1",
    size: "1000 × 1000 px",
    format: "WebP，透明背景",
    content: "淡钴蓝玻璃球，球心悬着发光十字准星和一段被放大的刻度尺，底部托着铬环与支架。",
    style: "R10、R11 的蓝色玻璃球与球心十字。",
    note: "脚本 render/orb.py",
  },
  {
    id: "GEN-04",
    kind: "GEN",
    name: "导出报告页眉：银镜碎片迸射",
    where: "S5 导出预览，报告页顶部横幅（也会进入导出的 Word / 图片）",
    ratio: "4.5:1 横幅",
    size: "2040 × 450 px",
    format: "WebP",
    content: "铬银、钴蓝玻璃、磨砂白玻璃碎片从右侧中心迸射，景深虚化；左侧 40% 留白。",
    style: "R9、R13 的蓝白碎晶。白底上的铬反射暗场，黑白分明。",
    note: "脚本 render/shards.py",
  },
  {
    id: "GEN-05",
    kind: "GEN",
    name: "浅色墨迹底",
    where: "S5 导出页桌面背景",
    ratio: "16:10",
    size: "2880 × 1800 px",
    format: "WebP",
    content: "冷白纸底，右上与左下两角有钴蓝墨迹晕开，中间留白给报告页。",
    style: "R1 上下边缘的蓝墨飞溅。",
    note: "脚本 render/smoke.py（day）",
  },
  {
    id: "GEN-06",
    kind: "GEN",
    name: "锚点 01：高分子链球棍模型",
    where: "S1 实验上下文，右栏上部",
    ratio: "约 1:1（已裁边）",
    size: "≈ 1000 px",
    format: "WebP，透明背景",
    content: "螺旋主链：铬银原子 + 钴蓝釉面侧基。寓意「建模」，把实验抽象成结构与公式。",
    style: "鲍林、沃森–克里克搭模型推结构的意象；暗场反射，放在浅色页面上黑白分明。",
    note: "脚本 render/anchors.py polymer",
  },
  {
    id: "GEN-07",
    kind: "GEN",
    name: "锚点 02：游标卡尺",
    where: "S2 我的数据，表格下方空白",
    ratio: "约 3:2（已裁边）",
    size: "≈ 1400 px 宽",
    format: "WebP，透明背景",
    content: "拉丝钢主尺 + 镜面游标滑块，主尺与游标刻度为几何建模。寓意「读数」。",
    style: "维尼尔（1631）游标；拉丝与镜面两种金属对比。",
    note: "脚本 render/anchors.py caliper",
  },
  {
    id: "GEN-08",
    kind: "GEN",
    name: "锚点 03：三棱镜分光",
    where: "S3b 文献取数，右栏提取结果下方",
    ratio: "约 3:2（已裁边）",
    size: "≈ 1500 px 宽",
    format: "WebP，透明背景",
    content: "一束白光射入三棱镜，另一侧散成由白到钴蓝的扇形光束。寓意「分离」，把曲线从图里剥离出来。",
    style: "牛顿 1666 年棱镜实验；光谱只用白到钴蓝，不用彩虹色。",
    note: "脚本 render/anchors.py prism",
  },
  {
    id: "GEN-09",
    kind: "GEN",
    name: "锚点 04：浑天仪",
    where: "S4 分析，标题行 Ea 数值与图例之间",
    ratio: "约 1:1（已裁边）",
    size: "≈ 1000 px",
    format: "WebP，透明背景",
    content: "赤道环、子午环、倾斜 23.4° 的刻度黄道带，中心钴蓝玻璃球，贯穿地轴与底座。寓意「从观测数据推出规律」。",
    style: "第谷的观测数据 → 开普勒定律，正是本产品要讲的故事。",
    note: "脚本 render/anchors.py armilla",
  },
  {
    id: "GEN-10",
    kind: "GEN",
    name: "锚点 05：钢笔尖与钴蓝墨滴",
    where: "S5 导出，右栏选项与按钮之间",
    ratio: "约 1:1（已裁边）",
    size: "≈ 900 px",
    format: "WebP，透明背景",
    content: "镜面钢笔尖（笔缝、导气孔），笔尖挂着一滴钴蓝墨水；页面上再从墨滴画一条点线流向导出按钮。寓意「成文」。",
    style: "实验记录本与论文手稿的意象。",
    note: "脚本 render/anchors.py nib",
  },
  {
    id: "PHOTO-01",
    kind: "PHOTO",
    name: "真实银镜反应照片",
    where: "S0 封面右上角样片（演示案例专属）",
    ratio: "4:5 竖幅（页面会居中裁切）",
    size: "≥ 1000 × 1250 px",
    format: "JPG",
    content: "真实做出来的银镜：试管或烧杯内壁的银镜特写，能看到镜面反射和不均匀的镀层边缘。越近越好，背景干净。",
    style: "页面自动处理：转灰度后映射为「墨黑 → 钴蓝」或「钴蓝 → 白」双色调，原图颜色无所谓，明暗对比要强。",
    note: "需确认可商用或可署名使用（如 Wikimedia Commons、Unsplash），记录来源链接；不要 AI 生成图，不要带水印。",
  },
  {
    id: "PHOTO-02",
    kind: "PHOTO",
    name: "旧期刊印刷页微距",
    where: "S3a 文献取数空状态，背景左侧",
    ratio: "3:4 竖幅",
    size: "≥ 1200 × 1600 px",
    format: "JPG",
    content: "印刷版科学期刊页面的微距照片：能看到曲线图、坐标轴、半调网点或油墨颗粒。暗示「论文里的图」。",
    style: "页面自动做「钴蓝 → 白」双色调并降低不透明度，作为情绪底纹，不需要内容可读。",
    note: "同 PHOTO-01 的授权要求；避免能看清具体论文标题和作者。",
  },
  {
    id: "DEMO-01",
    kind: "DEMO",
    name: "手写实验记录照片",
    where: "S2 我的数据，左侧",
    ratio: "3:4 竖幅（手机竖拍即可）",
    size: "≥ 1500 × 2000 px",
    format: "JPG",
    content: "银镜反应动力学实验的真实手写记录：至少包含水浴温度 T（°C）和出镜时间 t（s）两列，4–5 个温度梯度。",
    style: "真实拍摄，保留纸张、光线等自然痕迹，不需要修图。",
    note: "不能编造或用 AI 生成；照片中的数值必须与 M1 识别演示所用数据一致。",
  },
  {
    id: "DEMO-02",
    kind: "DEMO",
    name: "文献曲线截图",
    where: "S3b 文献取数画布；S3a 识别后也会出现",
    ratio: "约 4:3（以原图为准）",
    size: "宽 ≥ 1200 px",
    format: "PNG",
    content: "参照文献中的一张曲线图截图，需同时登记 DOI 与图号。坐标轴刻度要清楚可读。",
    style: "原样截图，不要裁掉坐标轴和图例。",
    note: "不能编造；本设计稿中的校准点位置是示意，接入真图后要按真实刻度重新标注。",
  },
];

const EXTS = ["webp", "png", "jpg"];

function placeholder(slot, def) {
  const ph = document.createElement("div");
  ph.className = "slot-ph";
  ph.innerHTML = def
    ? `<span class="badge">${def.kind}</span>
       <span class="sid">${def.id}</span>
       <span class="sname">${def.name}</span>
       <span class="sspec">${def.ratio} · ${def.size} · ${def.format}</span>`
    : `<span class="sid">未登记的素材位 ${slot.dataset.slot}</span>`;
  slot.appendChild(ph);
}

function loadSlot(slot) {
  const def = ASSET_SLOTS.find((d) => d.id === slot.dataset.slot);
  if (!def) return Promise.resolve(placeholder(slot, null));
  slot.dataset.kind = def.kind;
  slot.title = `${def.id} · ${def.name}`;
  return new Promise((resolve) => {
    let i = 0;
    const tryNext = () => {
      if (i >= EXTS.length) {
        placeholder(slot, def);
        return resolve(null);
      }
      const img = new Image();
      img.alt = def.name;
      img.onload = () => {
        slot.appendChild(img);
        resolve(img.src);
      };
      img.onerror = () => {
        i += 1;
        tryNext();
      };
      img.src = `assets/${def.id}.${EXTS[i]}`;
    };
    tryNext();
  });
}

async function initSlots() {
  const slots = [...document.querySelectorAll(".slot[data-slot]")];
  const loaded = {};
  await Promise.all(
    slots.map(async (s) => {
      const src = await loadSlot(s);
      if (src) loaded[s.dataset.slot] = src.split("/").pop();
    })
  );
  renderManifest(loaded);
}

function renderManifest(loaded) {
  const body = document.querySelector("#manifest tbody");
  if (!body) return;
  body.innerHTML = ASSET_SLOTS.map(
    (d) => `<tr>
      <td>${d.id}</td>
      <td><span class="kind ${d.kind}">${d.kind}</span></td>
      <td><b>${d.name}</b><br><span style="color:var(--ink-3)">${d.where}</span></td>
      <td>${d.ratio}<br>${d.size}<br>${d.format}</td>
      <td>${d.content}</td>
      <td>${d.style}</td>
      <td>${d.note}</td>
      <td>${
        loaded[d.id]
          ? `<span class="status-ok">已填入<br>${loaded[d.id]}</span>`
          : `<span class="status-miss">待填入</span>`
      }</td>
    </tr>`
  ).join("");
}

/* ---------- 2. 画框缩放：设计稿按 1440 × 900 绘制，等比缩放进画框 ---------- */
function initFrames() {
  const ro = new ResizeObserver((entries) => {
    for (const e of entries) e.target.style.setProperty("--s", e.contentRect.width / 1440);
  });
  document.querySelectorAll(".frame").forEach((f) => ro.observe(f));
}

/* ---------- 3. 示意图表 ----------
   示意数据，非真实实验；仅用于表现版式。数值由 Arrhenius 关系手工构造，
   拟合结果用 numpy.polyfit 计算：我的数据 Ea = 53.8 kJ/mol，R² = 0.978；文献示意 Ea = 50.0。 */
const DATA = {
  mine: [
    { id: "p1", T: 30, x: 3.299, y: -6.428 },
    { id: "p2", T: 40, x: 3.193, y: -5.743 },
    { id: "p3", T: 50, x: 3.095, y: -5.429, anomaly: true },
    { id: "p4", T: 60, x: 3.002, y: -4.5 },
    { id: "p5", T: 70, x: 2.914, y: -3.932 },
  ],
  lit: [
    { id: "L1", x: 3.354, y: -6.459 },
    { id: "L2", x: 3.245, y: -5.805 },
    { id: "L3", x: 3.143, y: -5.191 },
    { id: "L4", x: 3.047, y: -4.615 },
    { id: "L5", x: 2.957, y: -4.073 },
  ],
  // x 以 10^-3 K^-1 为单位，所以斜率除以 1000
  fitMine: { k: -6.46956, b: 14.85235 },
  fitLit: { k: -6.01395, b: 13.7117 },
  sim: { T: 80, x: 2.832, y: -3.468, t: 32 },
};

const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs, parent, text) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (text != null) n.textContent = text;
  if (parent) parent.appendChild(n);
  return n;
}

function drawArrhenius(svg, { w, h, compact = false }) {
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const m = compact ? { l: 44, r: 16, t: 14, b: 30 } : { l: 64, r: 28, t: 44, b: 52 };
  const X = [2.8, 3.4];
  const Y = [-6.8, -3.2];
  const sx = (v) => m.l + ((v - X[0]) / (X[1] - X[0])) * (w - m.l - m.r);
  const sy = (v) => h - m.b - ((v - Y[0]) / (Y[1] - Y[0])) * (h - m.t - m.b);
  const ink = "#0a0b10", ink3 = "#6b7180", cobalt = "#1e3bff", signal = "#e5242b";
  const fs = compact ? 9 : 11;
  const mono = "IBM Plex Mono, monospace";

  // 网格与刻度
  const g = el("g", {}, svg);
  for (let v = 2.8; v <= 3.401; v += 0.1) {
    const x = sx(v);
    el("line", { x1: x, x2: x, y1: m.t, y2: h - m.b, stroke: "rgba(10,11,16,.08)", "stroke-width": 0.5 }, g);
    el("line", { x1: x, x2: x, y1: h - m.b, y2: h - m.b + 5, stroke: ink, "stroke-width": 0.75 }, g);
    el("text", { x, y: h - m.b + (compact ? 15 : 20), "text-anchor": "middle", "font-size": fs, "font-family": mono, fill: ink3 }, g, v.toFixed(1));
  }
  for (let v = -6.5; v <= -3.49; v += 0.5) {
    const y = sy(v);
    el("line", { x1: m.l, x2: w - m.r, y1: y, y2: y, stroke: "rgba(10,11,16,.08)", "stroke-width": 0.5 }, g);
    el("line", { x1: m.l - 5, x2: m.l, y1: y, y2: y, stroke: ink, "stroke-width": 0.75 }, g);
    el("text", { x: m.l - 9, y: y + 3.5, "text-anchor": "end", "font-size": fs, "font-family": mono, fill: ink3 }, g, v.toFixed(1).replace("-", "−"));
  }
  el("line", { x1: m.l, x2: w - m.r, y1: h - m.b, y2: h - m.b, stroke: ink, "stroke-width": 1 }, g);
  el("line", { x1: m.l, x2: m.l, y1: m.t, y2: h - m.b, stroke: ink, "stroke-width": 1 }, g);
  if (!compact) {
    el("text", { x: w - m.r, y: h - 10, "text-anchor": "end", "font-size": 11, "font-family": mono, fill: ink }, g, "1/T  (10⁻³ K⁻¹)");
    el("text", { x: m.l + 8, y: m.t + 16, "font-size": 11, "font-family": mono, fill: ink }, g, "ln(1/t)");
    // 顶部温度尺：把 1/T 换回 °C，像仪器刻度
    el("line", { x1: m.l, x2: w - m.r, y1: m.t, y2: m.t, stroke: "rgba(10,11,16,.25)", "stroke-width": 0.5 }, g);
    [25, 30, 40, 50, 60, 70, 80].forEach((c) => {
      const x = sx(1000 / (c + 273.15));
      el("line", { x1: x, x2: x, y1: m.t - 4, y2: m.t, stroke: ink3, "stroke-width": 0.75 }, g);
      el("text", { x, y: m.t - 8, "text-anchor": "middle", "font-size": 10, "font-family": mono, fill: ink3 }, g, `${c}°C`);
    });
  }

  // 拟合线
  const line = (f, x0, x1, attrs) =>
    el("line", { x1: sx(x0), y1: sy(f.k * x0 + f.b), x2: sx(x1), y2: sy(f.k * x1 + f.b), ...attrs }, svg);
  line(DATA.fitLit, 2.93, 3.38, { stroke: ink, "stroke-width": 1, "stroke-dasharray": "5 4" });
  line(DATA.fitMine, 2.89, 3.32, { stroke: cobalt, "stroke-width": 1.5 });

  // 推演：沿拟合线外推到 80 °C
  if (!compact) {
    line(DATA.fitMine, DATA.sim.x, 2.914, { stroke: cobalt, "stroke-width": 1.5, "stroke-dasharray": "2 4" });
    const s = DATA.sim;
    el("circle", { cx: sx(s.x), cy: sy(s.y), r: 6, fill: "#fff", stroke: cobalt, "stroke-width": 1.5, "stroke-dasharray": "2 2" }, svg);
    const tg = el("g", { transform: `translate(${sx(s.x) + 14}, ${sy(s.y) + 4})` }, svg);
    el("text", { "font-size": 11, "font-family": mono, fill: cobalt }, tg, "推演 · 80 °C");
    el("text", { y: 15, "font-size": 11, "font-family": mono, fill: cobalt }, tg, "预测 t ≈ 32 s");
  }

  // 文献点：空心方块
  DATA.lit.forEach((p) => {
    const r = compact ? 3 : 4.5;
    el("rect", { x: sx(p.x) - r, y: sy(p.y) - r, width: r * 2, height: r * 2, fill: "#fff", stroke: ink, "stroke-width": 1.2 }, svg);
  });

  // 我的点：实心钴蓝
  DATA.mine.forEach((p) => {
    const cx = sx(p.x), cy = sy(p.y);
    if (p.anomaly) {
      el("circle", { cx, cy, r: compact ? 8 : 13, fill: "none", stroke: signal, "stroke-width": 1.5 }, svg);
      if (!compact) {
        // 预测位置与残差
        const yp = DATA.fitMine.k * p.x + DATA.fitMine.b;
        el("line", { x1: cx, y1: cy, x2: cx, y2: sy(yp), stroke: signal, "stroke-width": 1, "stroke-dasharray": "2 2" }, svg);
        el("circle", { cx, cy: sy(yp), r: 2.5, fill: signal }, svg);
        // 引线放在拟合线左下方的空白区，避开 p2 和文献点
        const ly = cy + 80;
        el("polyline", { points: `${cx - 9},${cy + 10} ${cx - 50},${ly - 4} ${cx - 250},${ly - 4}`, fill: "none", stroke: signal, "stroke-width": 0.75 }, svg);
        const tg = el("g", { transform: `translate(${cx - 250}, ${ly + 12})` }, svg);
        el("text", { "font-size": 11, "font-family": mono, fill: signal, "font-weight": 500 }, tg, "p3 · 50 °C · 残差 z = −2.0");
        el("text", { y: 16, "font-size": 11, "font-family": mono, fill: ink3 }, tg, "实测 228 s / 预测 176 s");
      }
    }
    el("circle", { cx, cy, r: compact ? 3.5 : 5.5, fill: p.anomaly ? signal : cobalt, stroke: "#fff", "stroke-width": compact ? 1 : 1.5 }, svg);
    if (!compact && !p.anomaly)
      el("text", { x: cx - 10, y: cy - 10, "text-anchor": "end", "font-size": 10, "font-family": mono, fill: cobalt }, svg, p.id);
  });
}

function initCharts() {
  const a = document.getElementById("chart-analysis");
  if (a) drawArrhenius(a, { w: 860, h: 600 });
  const b = document.getElementById("chart-report");
  if (b) drawArrhenius(b, { w: 568, h: 230, compact: true });
}

/* 单屏查看：index.html?frame=s3b 只显示这一屏，铺满窗口 */
function initSolo() {
  const id = new URLSearchParams(location.search).get("frame");
  document.querySelectorAll(".beat").forEach((b) => {
    const a = document.createElement("a");
    a.href = `?frame=${b.id}`;
    a.target = "_blank";
    a.className = "solo-link";
    a.textContent = "单屏查看 ↗";
    b.querySelector(".beat-notes").appendChild(a);
  });
  const beat = id && document.getElementById(id);
  if (!beat) return;
  const frame = beat.querySelector(".frame");
  document.body.replaceChildren(frame);
  document.body.classList.add("solo");
  document.title = `${id.toUpperCase()} · LabInfer 设计稿`;
}

initSolo();
initFrames();
initCharts();
initSlots();
