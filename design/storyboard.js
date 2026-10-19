/* =========================================================
   LabInfer 设计稿 · 脚本
   1. 素材位清单（唯一真相源）与加载
   2. 画框缩放
   3. 图表（理论滴定曲线）
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
    where: "S0 封面，画面中右，压在超大标题之上；03 视觉规范的质感示例",
    ratio: "7:9 竖幅",
    size: "1400 × 1800 px",
    format: "WebP，透明背景",
    content: "玻璃试管内壁镀着上沿不规则的银镜层，上沿之上散落成核银斑；液态银从管口溢出、沿外壁淌下；周围悬浮银珠。",
    style: "R2 铬银棋子、R6 液态金属。影棚：暗场 + 白色长条灯 + 钴蓝灯板，反射里带品牌色。",
    note: "脚本 render/tube.py。最早为银镜案例而做，演示案例改为滴定后仍用作封面：质感贴合整体审美，且 LabInfer 面向通用实验，封面物件不必绑定演示实验。",
  },
  {
    id: "GEN-11",
    kind: "GEN",
    name: "不需要：滴定管（曾计划的滴定案例封面）",
    where: "不再使用。封面保留银镜试管 GEN-01，这一条只留登记以便追溯",
    ratio: "7:9 竖幅（滴定管细长，可斜放 12° 撑满画幅）",
    size: "1400 × 1800 px",
    format: "WebP，透明背景",
    content: "酸式滴定管：玻璃管身带精确刻度（几何建模，0.1 mL 一格），铬银活塞；管内钴蓝液柱，弯月面清晰；管尖悬着一滴将落未落的钴蓝液滴。刻度旁可有一枚十字准星对准弯月面，呼应「读数」。",
    style: "沿用 GEN-01 的影棚：暗场 + 白色长条灯 + 钴蓝灯板，反射里带品牌色。R2 铬银、R10 玻璃。",
    note: "不制作，render/burette.py 不需要写。",
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
    name: "导出报告页眉：铬银碎片迸射",
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
    where: "S4 分析，标题行 c̄(HCl) 数值与图例之间",
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
    name: "滴定终点样片（程序渲染，不是照片）",
    where: "S0 封面右上角样片（演示案例专属）",
    ratio: "4:5 竖幅（页面会居中裁切）",
    size: "1000 × 1250 px（页面用 400 × 500 WebP）",
    format: "JPG 原图 + WebP",
    content: "滴定管尖悬着一滴将落未落的液滴，下方一滴正在下落，最下面是锥形瓶液面和一圈涟漪。暗场影棚，两条竖向长条灯 + 顶部柔光箱，液面把横向灯带反成一条被涟漪扭弯的亮线。",
    style: "只输出灰度，页面映射为「墨黑 → 钴蓝」双色调（duo-night）。",
    note: "脚本 render/specimen.py（numpy 有向距离场光线步进，2×2 超采样，约 2 分钟）。原定的真实照片来不及检索授权，改为自己画；不是实拍，不能当实验证据使用。",
  },
  {
    id: "PHOTO-02",
    kind: "PHOTO",
    name: "旧期刊印刷页微距（程序绘制，不是照片）",
    where: "S3a 文献取数空状态，背景左侧",
    ratio: "3:4 竖幅",
    size: "1200 × 1600 px（页面用 600 × 800 WebP）",
    format: "JPG 原图 + WebP",
    content: "双栏期刊页斜放在镜头下：一张 pH–V 滴定曲线插图（坐标轴、数据点、变色带），灰色区域用 45° 半调网点印出，正文是看不清的字块。透视倾斜 + 景深模糊，像微距拍到的印刷页。",
    style: "页面做「钴蓝 → 白」双色调（duo-day）并降到 40% 不透明度，作为情绪底纹，内容不可读。",
    note: "脚本 render/journal.py（Pillow 绘制，几秒出图）。没有真实论文的标题、作者或文字，不涉及授权。",
  },
  {
    id: "DEMO-01",
    kind: "DEMO",
    name: "手写实验记录照片",
    where: "S2 我的数据，左侧",
    ratio: "3:4 竖幅（手机竖拍即可）",
    size: "≥ 1500 × 2000 px",
    format: "JPG",
    content: "HCl 标定与碱灰总碱度的真实手写记录页（武汉工程大学《分析化学实验》实验 3）：标定段三份 m、V、c，测定段三份 V、w，以及平均值。已提供。",
    style: "真实拍摄，保留纸张、光线等自然痕迹，不需要修图。",
    note: "不能编造或用 AI 生成；照片中的数值必须与 M1 识别演示所用数据一致。",
  },
  {
    id: "DEMO-02",
    kind: "DEMO",
    name: "文献滴定曲线截图",
    where: "S3b 文献取数画布；S3a 识别后也会出现",
    ratio: "约 4:3（以原图为准）",
    size: "宽 ≥ 1200 px",
    format: "PNG",
    content: "教材或论文里 HCl 滴定 Na₂CO₃ 的滴定曲线（pH 对 V 或滴定分数），能看到两个计量点。需登记 DOI 或 ISBN 与图号，并读出图中计量点体积。坐标轴刻度要清楚可读。",
    style: "原样截图，不要裁掉坐标轴和图例。",
    note: "不能编造；本设计稿中的校准点位置是示意，接入真图后要按真实刻度重新标注。",
  },
];

const EXTS = ["webp", "png", "jpg"];

/* ---------- 1b. 锚点构图：秩序 × 破坏 ----------
   每件锚点物件不是孤立摆放，而是由同一张透明 PNG 派生出多层效果叠在一起：
   秩序层：超大描边词、过物件中心的刻度轴、角标框、引线标注、编号与条码
   破坏层：钴蓝剪影套印错位、半调网点剪影、水平切片错位、碎片、钴蓝压印色块、扫描线
   坐标都是物件图片内的百分比（物件框按图片宽高比 ar 等比缩放，所以坐标与图片对齐）。 */
const ANCHOR_FX = {
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

function h(tag, cls, style) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (style) Object.assign(n.style, style);
  return n;
}

const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ESC_MAP[c]);

function buildVignette(v) {
  const id = v.dataset.fx;
  const fx = ANCHOR_FX[id];
  if (!fx) return;
  v.classList.add("tex-grain");
  if (fx.word) {
    const w = h("div", "v-word", { left: fx.wordAt.left, top: fx.wordAt.top });
    w.textContent = fx.word;
    v.appendChild(w);
  }
  const stage = h("div", "v-stage");
  const box = h("div", "v-box");
  box.style.setProperty("--ar", fx.ar);
  stage.appendChild(box);
  v.appendChild(stage);

  // 秩序：过物件中心的刻度轴 + 角标框
  box.append(h("div", "v-axis-h"), h("div", "v-axis-v"), h("div", "corners"));
  // 破坏：半调剪影、钴蓝剪影（套印错位）
  const half = h("div", "v-half");
  half.style.translate = `${fx.half[0]}px ${fx.half[1]}px`;
  const sil = h("div", "v-sil");
  sil.style.translate = `${fx.sil[0]}px ${fx.sil[1]}px`;
  box.append(half, sil);
  // 本体
  const slot = h("div", "slot contain v-obj");
  slot.dataset.slot = id;
  box.appendChild(slot);
  // 压印色块
  const b = fx.block;
  box.appendChild(h("div", "v-block", { left: b.left + "%", top: b.top + "%", width: b.w + "%", height: b.h + "%" }));
  // 切片错位：切片底色压住原图对应的带，再整体平移
  fx.slices.forEach(([top, hgt, shift], i) => {
    const s = h("div", "v-slice", { clipPath: `inset(${top}% -20% ${100 - top - hgt}% -20%)` });
    s.style.setProperty("--shift", shift + "px");
    s.style.animationDelay = `${i * 1.3}s`;
    box.appendChild(s);
  });
  // 碎片
  fx.shards.forEach((sd) => {
    box.appendChild(h("div", "v-shard", { clipPath: `polygon(${sd.poly})`, transform: `translate(${sd.d[0]}px, ${sd.d[1]}px) rotate(${sd.r}deg)` }));
  });
  // 扫描线：只落在物件剪影内的一条带
  box.appendChild(h("div", "v-scan"));
  // 引线标注：圆点在物件上（百分比坐标），斜线段伸出 (dx, dy) 像素，端点挂标签
  fx.ann.forEach((a) => {
    const g = h("div", "v-tag", { left: a.x + "%", top: a.y + "%" });
    const len = Math.hypot(a.dx, a.dy);
    const ang = Math.atan2(a.dy, a.dx);
    g.innerHTML = `<i class="dot"></i><i class="lead" style="width:${len}px;transform:rotate(${ang}rad)"></i><span style="left:${a.dx}px;top:${a.dy}px">${a.t}</span>`;
    if (a.dx < 0) g.classList.add("left");
    box.appendChild(g);
  });
  // 编号与条码
  const ser = h("div", "v-serial");
  ser.innerHTML = `<i class="barcode"></i><span>${fx.serial}</span>`;
  v.appendChild(ser);
}

function initVignettes() {
  document.querySelectorAll(".vignette[data-fx]").forEach(buildVignette);
}

function placeholder(slot, def) {
  const ph = document.createElement("div");
  ph.className = "slot-ph";
  const span = (cls, text) => {
    const s = document.createElement("span");
    s.className = cls;
    s.textContent = text;
    return s;
  };
  if (def) {
    ph.append(
      span("badge", def.kind),
      span("sid", def.id),
      span("sname", def.name),
      span("sspec", `${def.ratio} · ${def.size} · ${def.format}`)
    );
  } else {
    ph.append(span("sid", `未登记的素材位 ${slot.dataset.slot}`));
  }
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
        // 锚点构图的各层效果都从这张图派生
        const v = slot.closest(".vignette");
        if (v) v.style.setProperty("--img", `url("${img.src}")`);
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
      <td>${esc(d.id)}</td>
      <td><span class="kind ${esc(d.kind)}">${esc(d.kind)}</span></td>
      <td><b>${esc(d.name)}</b><br><span style="color:var(--ink-3)">${esc(d.where)}</span></td>
      <td>${esc(d.ratio)}<br>${esc(d.size)}<br>${esc(d.format)}</td>
      <td>${esc(d.content)}</td>
      <td>${esc(d.style)}</td>
      <td>${esc(d.note)}</td>
      <td>${
        loaded[d.id]
          ? `<span class="status-ok">已填入<br>${esc(loaded[d.id])}</span>`
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

/* ---------- 3. 图表：HCl 滴定 Na₂CO₃ 的理论滴定曲线 ----------
   数据真实：三份标定的称样量与滴定体积取自 DEMO-01 手写记录页，c̄ = 0.102735 mol/L 为 M4 计算结果。
   曲线是确定性计算，不是示意：碳酸 pKa 6.35 / 10.33，按电荷平衡逐点解 pH（与 contracts 0.7.0 的
   titration_curve 口径一致）。正式页面由 M4 返回曲线，前端只绘制，这里在设计稿内复算一遍用来定版式。
   残留 CO₂ 比例 f：1 = 未煮沸（封闭体系），小于 1 时把溶解 CO₂ 封顶在计量点浓度的 f 倍，模拟近终点煮沸。 */
const TITR = {
  M: 105.99, c: 0.102735, V0: 30, pKa1: 6.35, pKa2: 10.33,
  std: [
    { id: "p1", m: 0.1549, V: 28.54 },
    { id: "p2", m: 0.1832, V: 33.0 },
    { id: "p3", m: 0.167, V: 31.19 },
  ],
  basis: "p3", // 称样量居中的一份
  window: [3.1, 4.4], // 甲基橙变色区
  boiled: 0.05,
};

const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs, parent, text) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (text != null) n.textContent = text;
  if (parent) parent.appendChild(n);
  return n;
}

function titrPH(m, V, f = 1) {
  const { M, c, V0 } = TITR;
  const Ka1 = 10 ** -TITR.pKa1, Ka2 = 10 ** -TITR.pKa2, Kw = 1e-14;
  const n0 = m / M, Vt = (V0 + V) / 1000;
  const CT = n0 / Vt, Na = (2 * n0) / Vt, Cl = (c * V) / 1000 / Vt;
  const Veq = ((2 * m) / M / c) * 1000;
  const cap = (f * n0) / ((V0 + Veq) / 1000);
  let lo = 0, hi = 14;
  for (let k = 0; k < 70; k++) {
    const p = (lo + hi) / 2, hh = 10 ** -p, D = hh * hh + Ka1 * hh + Ka1 * Ka2;
    const an = (hh * hh) / D * CT <= cap
      ? (CT * (Ka1 * hh + 2 * Ka1 * Ka2)) / D
      : (Ka1 * cap) / hh + (2 * Ka1 * Ka2 * cap) / (hh * hh);
    if (hh + Na - Kw / hh - an - Cl > 0) lo = p; else hi = p;
  }
  return (lo + hi) / 2;
}
const veq = (m) => ((2 * m) / TITR.M / TITR.c) * 1000;

function drawTitration(svg, { w, h, compact = false }) {
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const m = compact ? { l: 40, r: 16, t: 14, b: 30 } : { l: 64, r: 28, t: 52, b: 52 };
  const X = [-1, 1], Y = [2, 8];
  const sx = (v) => m.l + ((v - X[0]) / (X[1] - X[0])) * (w - m.l - m.r);
  const sy = (v) => h - m.b - ((v - Y[0]) / (Y[1] - Y[0])) * (h - m.t - m.b);
  const ink = "#0a0b10", ink3 = "#6b7180", cobalt = "#1e3bff", signal = "#e5242b";
  const fs = compact ? 9 : 11;
  const mono = "IBM Plex Mono, monospace";
  const base = TITR.std.find((p) => p.id === TITR.basis);
  const Vb = veq(base.m);
  const curve = (f) => {
    const pts = [];
    for (let d = X[0]; d <= X[1] + 1e-9; d += 0.01) pts.push([d, titrPH(base.m, Vb + d, f)]);
    return pts.map(([d, p]) => `${sx(d).toFixed(1)},${sy(Math.min(Math.max(p, Y[0]), Y[1])).toFixed(1)}`).join(" ");
  };

  // 甲基橙变色区：中性灰带（红色只留给异常）
  const [w0, w1] = TITR.window;
  el("rect", { x: m.l, y: sy(w1), width: w - m.l - m.r, height: sy(w0) - sy(w1), fill: "rgba(10,11,16,.06)" }, svg);
  if (!compact) el("text", { x: m.l + 8, y: sy(w1) + 14, "font-size": 10, "font-family": mono, fill: ink3 }, svg, `甲基橙 pH ${w0}–${w1}`);

  // 网格与刻度
  const g = el("g", {}, svg);
  for (let v = -1; v <= 1.001; v += 0.25) {
    const x = sx(v);
    el("line", { x1: x, x2: x, y1: m.t, y2: h - m.b, stroke: "rgba(10,11,16,.08)", "stroke-width": 0.5 }, g);
    el("line", { x1: x, x2: x, y1: h - m.b, y2: h - m.b + 5, stroke: ink, "stroke-width": 0.75 }, g);
    if (compact && Math.abs(v * 2 - Math.round(v * 2)) > 1e-6) continue;
    const t = v === 0 ? "0" : (v > 0 ? "+" : "−") + Math.abs(v).toFixed(2);
    el("text", { x, y: h - m.b + (compact ? 15 : 20), "text-anchor": "middle", "font-size": fs, "font-family": mono, fill: ink3 }, g, t);
  }
  for (let v = 2; v <= 8; v += 1) {
    const y = sy(v);
    el("line", { x1: m.l, x2: w - m.r, y1: y, y2: y, stroke: "rgba(10,11,16,.08)", "stroke-width": 0.5 }, g);
    el("line", { x1: m.l - 5, x2: m.l, y1: y, y2: y, stroke: ink, "stroke-width": 0.75 }, g);
    el("text", { x: m.l - 9, y: y + 3.5, "text-anchor": "end", "font-size": fs, "font-family": mono, fill: ink3 }, g, String(v));
  }
  el("line", { x1: m.l, x2: w - m.r, y1: h - m.b, y2: h - m.b, stroke: ink, "stroke-width": 1 }, g);
  el("line", { x1: m.l, x2: m.l, y1: m.t, y2: h - m.b, stroke: ink, "stroke-width": 1 }, g);
  el("line", { x1: sx(0), x2: sx(0), y1: m.t, y2: h - m.b, stroke: ink3, "stroke-width": 0.75, "stroke-dasharray": "3 3" }, g);
  if (!compact) {
    el("text", { x: w - m.r, y: h - 10, "text-anchor": "end", "font-size": 11, "font-family": mono, fill: ink }, g, "ΔV = 终点 − 计量点  (mL)");
    el("text", { x: m.l + 8, y: m.t + 16, "font-size": 11, "font-family": mono, fill: ink }, g, "pH");
    el("text", { x: sx(0) + 6, y: h - m.b - 8, "font-size": 10, "font-family": mono, fill: ink3 }, g, "计量点");
    // 顶部滴定管刻度：把 ΔV 换回 p3 那一份在滴定管上的读数
    el("line", { x1: m.l, x2: w - m.r, y1: m.t, y2: m.t, stroke: "rgba(10,11,16,.25)", "stroke-width": 0.5 }, g);
    for (let r = Math.ceil((Vb - 1) * 10) / 10; r <= Vb + 1; r += 0.1) {
      const x = sx(r - Vb), major = Math.abs(r * 2 - Math.round(r * 2)) < 1e-6;
      el("line", { x1: x, x2: x, y1: m.t - (major ? 6 : 3), y2: m.t, stroke: ink3, "stroke-width": 0.75 }, g);
      if (major) el("text", { x, y: m.t - 10, "text-anchor": "middle", "font-size": 10, "font-family": mono, fill: ink3 }, g, r.toFixed(1));
    }
    el("text", { x: w - m.r, y: m.t - 26, "text-anchor": "end", "font-size": 10, "font-family": mono, fill: ink3 }, g, `BURETTE · ${base.id} · mL`);
  }

  // 理论曲线：未煮沸（实线）；推演：已煮沸（点线）
  if (!compact) {
    el("polyline", { points: curve(TITR.boiled), fill: "none", stroke: cobalt, "stroke-width": 1.5, "stroke-dasharray": "2 4", "stroke-linecap": "round" }, svg);
    el("text", { x: sx(-0.62), y: sy(titrPH(base.m, Vb - 0.62, TITR.boiled)) - 10, "font-size": 11, "font-family": mono, fill: cobalt }, svg, "推演 · 近终点煮沸");
  }
  el("polyline", { points: curve(1), fill: "none", stroke: cobalt, "stroke-width": compact ? 1.25 : 1.75, "stroke-linejoin": "round" }, svg);

  // 我的终点：落在变色区外的用红圈
  TITR.std.forEach((p, i) => {
    const dv = p.V - veq(p.m), ph = titrPH(p.m, p.V);
    const out = ph > w1 || ph < w0;
    const cx = sx(dv), cy = sy(ph);
    if (out) el("circle", { cx, cy, r: compact ? 7 : 12, fill: "none", stroke: signal, "stroke-width": 1.5 }, svg);
    el("circle", { cx, cy, r: compact ? 3.5 : 5.5, fill: out ? signal : cobalt, stroke: "#fff", "stroke-width": compact ? 1 : 1.5 }, svg);
    if (compact) return;
    const sign = dv > 0 ? "+" : "−";
    const head = `${p.id} · ΔV ${sign}${Math.abs(dv).toFixed(2)} mL · pH ${ph.toFixed(2)}`;
    if (!out) {
      el("text", { x: cx + 12, y: cy - 10, "font-size": 10, "font-family": mono, fill: cobalt }, svg, head);
      return;
    }
    // 引线伸向空白处：p2 在左上，p3 在右下
    const left = dv < 0;
    const lx = left ? cx - 40 : cx + 40, ly = left ? cy - 70 : cy + 60;
    el("polyline", { points: `${cx + (left ? -9 : 9)},${cy + (left ? -9 : 9)} ${lx},${ly} ${left ? lx - 160 : lx + 160},${ly}`, fill: "none", stroke: signal, "stroke-width": 0.75 }, svg);
    const tg = el("g", { transform: `translate(${left ? lx - 160 : lx}, ${ly + 14})` }, svg);
    el("text", { "font-size": 11, "font-family": mono, fill: signal, "font-weight": 500 }, tg, head);
    el("text", { y: 16, "font-size": 11, "font-family": mono, fill: ink3 }, tg, ph > w1 ? "停早了：溶液应仍为黄色" : "滴过了：已越过变色区");
  });
}

function initCharts() {
  const a = document.getElementById("chart-analysis");
  if (a) drawTitration(a, { w: 860, h: 600 });
  const b = document.getElementById("chart-report");
  if (b) drawTitration(b, { w: 568, h: 230, compact: true });
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
initVignettes();
initFrames();
initCharts();
initSlots();
