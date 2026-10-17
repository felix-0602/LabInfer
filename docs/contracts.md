# 数据契约

**当前版本：0.3.0（氨氮演示案例定稿）**

模块之间只通过本文件定义的数据结构交互。修改规则见 [versioning.md](versioning.md#契约版本)。

前半部分定义数据结构，后半部分定义 [HTTP 接口](#http-接口)。本版变更摘要见文末[变更记录](#变更记录)。

## 通用约定

- 所有顶层对象带 `schema_version` 字段，值为本文件的版本号。
- 数值统一用 JSON number，缺失值用 `null`。**识别不确定的值也写 `null`，不许编造**（M1、M2 同守此规）。
- 单位写在列定义里，数值本身不带单位。温度在数据集中保留原始单位，换算由 M4 完成。
- 数据点用 `{dataset_id, point_id}` 定位，`point_id` 在同一个数据集内唯一。
- **列角色（role）**：列的用途由 ExperimentContext 声明（如浓度列、信号列、取样体积列），M4 按角色取数套公式，不认识具体的列名。每个模型需要哪些角色见[模型注册表](#模型注册表)。
- **参照分层**：参照分三层，独立声明——文献数据集（方法学对比）、有证标准物质 CRM（真值核查）、法规限值（合规判定）。M4 的 `comparison` 对三层各出结构化判定，M5 引用时指向判定对象。

## Dataset 数据集

M1、M2 输出，M4 读取。列不限制名称，行用 `series` 标注类别，M4 据此分组：`std`（标准系列点）、`blank`（空白）、`sample:<名称>`（样品，平行样同名成组）、`qc:crm`（质控样）、`qc:spike`（加标样）。

```jsonc
{
  "schema_version": "0.3.0",
  "id": "ds_mine_01",
  "source": "my_experiment",          // my_experiment | literature
  "meta": {
    "title": "水质氨氮 标准系列与样品",
    "doi": null,                       // source=literature 时必填
    "figure": null,                    // 如 "图1(b)"
    "image_ref": "uploads/xxx.jpg"     // 原始图片
  },
  "columns": [
    { "key": "c", "name": "氨氮浓度", "unit": "mg/L" },
    { "key": "A", "name": "吸光度", "unit": "" },
    { "key": "V", "name": "取样体积", "unit": "mL" },     // 条件列：见行示例
    { "key": "dil", "name": "稀释倍数", "unit": "" }
  ],
  "rows": [
    // 标准系列行：浓度与吸光度都有值
    { "id": "p1", "series": "std", "values": { "c": 0.10, "A": 0.041 },
      "confidence": { "c": 0.99, "A": 0.94 }, "verified": false },
    // 样品行：浓度为 null（待 M4 反推），条件列有值
    { "id": "s1", "series": "sample:地表水1", "values": { "c": null, "A": 0.226, "V": 10, "dil": 1 },
      "confidence": { "A": 0.91 }, "verified": false },
    // 质控样行
    { "id": "q1", "series": "qc:crm", "values": { "c": null, "A": 0.281, "V": 10, "dil": 1 },
      "confidence": {}, "verified": false }
  ]
}
```

`confidence` 为识别置信度 0～1，可选，仅 M1 产出的数据集携带；低置信格子由用户在 M8 校正后置 `verified: true`。

## ExperimentContext 实验上下文

M3 输出，M4、M5 读取。

```jsonc
{
  "schema_version": "0.3.0",
  "id": "ctx_01",
  "name": "水质氨氮检测（HJ 535-2009 纳氏试剂法）",
  "purpose": "测定水样氨氮浓度，判定是否达到 GB 3838-2002 III 类限值",
  "model": "linear_calibration",
  "variables": {
    "columns": [                       // 角色→实际列的绑定
      { "key": "c",   "role": "concentration",   "unit": "mg/L" },
      { "key": "A",   "role": "signal",          "unit": "" },
      { "key": "V",   "role": "sample_volume",   "unit": "mL", "optional": true, "default": 50 },
      { "key": "dil", "role": "dilution_factor", "unit": "",   "optional": true, "default": 1 }
    ]
  },
  "datasets": { "mine": "ds_mine_01" },
  "reference": {
    "datasets": [                      // 第一层：文献数据集
      { "dataset_id": "ds_lit_01",
        "columns": { "concentration": "x", "signal": "y" },  // 文献数据集的列→角色
        "space": "raw",                // raw=原始量；transformed=已在模型拟合空间（M4 不再变换）
        "meta": { "doi": "10.3866/PKU.DXHX201807034", "figure": "图1(b)",
                  "note": "纳氏试剂法标准曲线" } }
    ],
    "crm": {                           // 第二层：有证标准物质真值
      "id": "GSB 07-3164-2014", "value": 0.716, "u95": 0.044, "unit": "mg/L" },
    "limits": [                        // 第三层：法规限值
      { "label": "GB 3838-2002 III 类", "value": 1.0, "unit": "mg/L", "operator": "<=" } ]
  },
  "qc_rules": [                        // 质控规则包，M4 执行，M5 引用条文
    { "rule_id": "calibration_r2",   "params": { "min": 0.999 }, "citation": "HJ 535-2009" },
    { "rule_id": "parallel_rpd",     "params": { "max": 0.10 },  "citation": "HJ 630-2011" },
    { "rule_id": "outlier_grubbs",   "params": { "alpha": 0.05 }, "citation": "GB/T 4883" },
    { "rule_id": "crm_within_u95",   "params": {},               "citation": "CRM 证书" }
  ]
}
```

`space` 解决「文献常画变换后的量（如 ln(1/t)–1/T）而我的数据是原始量」的问题：`transformed` 的参照数据集直接在拟合空间参与对比（product.md 待定事项落定）。

## 模型注册表

M4 按注册表实现，新增模型 = 新增一行 + 一个实现，路由与契约不变。

| model | 必需角色 | 可选角色 | 变换到拟合空间 | derived 字段 | M6 可推演参数 |
|---|---|---|---|---|---|
| `linear_calibration` | `concentration`, `signal` | `sample_volume`, `dilution_factor` | 恒等 | `sensitivity`, `slope_ci95` | `dilution_factor`, `sample_volume` |
| `arrhenius` | `temperature`, `time` | — | x→1/T（K），y→ln(1/t) | `Ea_kJ_per_mol`, `Ea_ci95` | `temperature` |

浓度反推公式（linear_calibration，样品行）：

`ρ = (A − intercept) / slope × (V定容 / V取样) × dilution`

其中 `V定容` 由模板参数提供（氨氮为 50 mL）。**这个换算必须由 M4 完成**——取样体积与稀释倍数是学生计算错误的高发区。

## AnalysisResult 分析结果

M4 输出，M5、M6、M8 读取。

```jsonc
{
  "schema_version": "0.3.0",
  "context_id": "ctx_01",
  "model": "linear_calibration",
  "transformed": [                     // 拟合空间的作图数据（linear 为恒等；M8 直接绘制）
    { "dataset_id": "ds_mine_01",
      "x_label": "c", "x_unit": "mg/L", "y_label": "A", "y_unit": "",
      "points": [{ "point_id": "p1", "x": 0.10, "y": 0.041 }] }
  ],
  "fits": [
    { "dataset_id": "ds_mine_01",
      "slope": 0.4026, "intercept": 0.0021, "r2": 0.99995, "n": 7,
      "derived": {                      // 开放对象，字段由模型注册表定义
        "sensitivity": 0.4026,
        "slope_ci95": [0.396, 0.409] } }
  ],
  "predictions": [                      // 样品反推结果（arrhenius 无此节）
    { "dataset_id": "ds_mine_01", "point_id": "s1",
      "value": 0.556, "u95": 0.031, "unit": "mg/L",   // u95 = 扩展不确定度（k=2，标曲传播）
      "factors": { "sample_volume_ml": 10, "final_volume_ml": 50, "dilution_factor": 1 },
      "as_reported": 2.78 }             // 换算回原水样的报告值
  ],
  "residuals": [
    { "dataset_id": "ds_mine_01", "point_id": "p5", "residual": 0.0038,
      "outlier": false, "method": "grubbs", "p": 0.21 }
  ],
  "qc_results": [                       // 质控规则逐条判定
    { "rule_id": "calibration_r2", "pass": true, "value": 0.99995, "limit": 0.999,
      "citation": "HJ 535-2009", "subjects": [] },
    { "rule_id": "parallel_rpd", "pass": true, "value": 0.0107, "limit": 0.10,
      "citation": "HJ 630-2011",
      "subjects": [{ "dataset_id": "ds_mine_01", "point_id": "s1" },
                    { "dataset_id": "ds_mine_01", "point_id": "s2" }] },
    { "rule_id": "crm_within_u95", "pass": true, "value": 0.721,
      "certified": 0.716, "u95": 0.044, "citation": "GSB 07-3164-2014",
      "subjects": [{ "dataset_id": "ds_mine_01", "point_id": "q1" }] }
  ],
  "comparison": {                       // 三层参照判定
    "vs_reference": [                   // 对文献：斜率（灵敏度）对比
      { "dataset_id": "ds_lit_01", "mine_slope": 0.4026, "ref_slope": 0.13933,
        "deviation_pct": 189.5 } ],
    "vs_limit": [                       // 对限值：逐样品合规判定
      { "point_id": "s1", "value": 2.78, "limit": 1.0,
        "label": "GB 3838-2002 III 类", "verdict": "exceed" } ],   // exceed | comply
    "vs_crm": { "point_id": "q1", "measured": 0.721, "certified": 0.716,
                "u95": 0.044, "within": true }
  }
}
```

## Finding 结论

M5 输出一个数组，M6、M7、M8 读取。

```jsonc
{
  "schema_version": "0.3.0",
  "id": "f1",
  "type": "anomaly",                   // pattern | conclusion | anomaly | suggestion
  "text": "标曲第 5 点（c=0.80）残差 0.0038，格拉布斯检验未判为离群……",
  "evidence": [                        // 至少一条，类型化引用
    { "type": "point",      "dataset_id": "ds_mine_01", "point_id": "p5" },
    { "type": "qc",         "rule_id": "outlier_grubbs" },
    { "type": "comparison", "target": "vs_limit[0]" },
    { "type": "fit",        "dataset_id": "ds_mine_01" }
  ],
  "simulatable": true,
  "simulation": { "param": "dilution_factor", "from": 1, "to": 10, "unit": "" }
}
```

`evidence[].type`：`point`（数据点）、`fit`（拟合对象）、`qc`（质控判定）、`comparison`（参照判定）。M8 联动时按 type 高亮对应元素。M5 校验器规则：`text` 中出现的数字必须能在 AnalysisResult 的数值集合中找到（±容差），`evidence` 引用的对象必须存在；不过校验的结论整条丢弃并回灌错误重生成一次，再失败则降级为模板文案。

## Simulation 参数推演

M6 的请求和返回，M8 调用。`param` 取值以[模型注册表](#模型注册表)的「M6 可推演参数」为准。

```jsonc
// 请求
{ "schema_version": "0.3.0", "context_id": "ctx_01", "finding_id": "f2",
  "param": "dilution_factor", "from": 1, "to": 10, "unit": "" }

// 返回（curve 在拟合空间，与 transformed 同坐标系）
{ "schema_version": "0.3.0", "finding_id": "f2",
  "predicted": { "dilution_factor": 5, "A": 0.112 },
  "curve": [{ "x": 0.556, "y": 0.226 }] }
```

---

## HTTP 接口

### 约定

- 基础路径 `/api`，请求和返回都是 UTF-8 JSON；上传图片用 `multipart/form-data`。
- 请求和返回里的契约对象都带 `schema_version`。主版本号不一致时返回 409。
- 出错时统一返回：

  ```jsonc
  { "error": { "code": "VLM_UNAVAILABLE", "message": "视觉模型暂时不可用", "detail": {} } }
  ```

  | 状态码 | 含义 |
  |---|---|
  | 400 | 参数缺失或格式错误 |
  | 404 | 资源不存在 |
  | 409 | `schema_version` 主版本不一致 |
  | 422 | 参数合法，但处理失败（例如校准点重合、无法换算、缺少必需角色列） |
  | 503 | 依赖的服务不可用（VLM、LLM） |

- **像素坐标**：指原图上的像素，不是屏幕像素。原点在左上角，u 向右、v 向下，可以是小数，写作 `[u, v]`。
- 图片地址由后端在返回里给出，前端不自己拼路径。
- 后端对外请求（VLM/LLM）仅允许 https，拒绝 localhost、环回、私有和保留地址。

### M2 曲线取数

负责人 Claude，状态：**已定**。边界见 [architecture.md](architecture.md#m2-曲线取数)。

| 方法与路径 | 作用 | 返回 |
|---|---|---|
| `POST /api/m2/figures` | 上传截图和文献信息 | Figure |
| `GET /api/m2/figures/{id}/image` | 取原图 | 图片文件 |
| `POST /api/m2/figures/{id}/detect` | 识别坐标轴和图例，给出校准建议 | FigureDetection |
| `POST /api/m2/figures/{id}/extract` | 按确认的校准提取一条曲线，写入共享存储 | ExtractResult |

#### 上传：`POST /api/m2/figures`

表单字段：`image`（必填，PNG / JPG）、`doi`（选填）、`figure`（选填，如 `图1(b)`）。

```jsonc
// 返回 201：Figure
{
  "schema_version": "0.3.0",
  "id": "fig_01",
  "image_url": "/api/m2/figures/fig_01/image",
  "width": 1280, "height": 960,                // 原图像素
  "sha256": "9f2c…",                            // 演示保底按它命中缓存
  "meta": { "doi": "10.3866/PKU.DXHX201807034", "figure": "图1(b)" }
}
```

#### 识别：`POST /api/m2/figures/{id}/detect`

请求体为空。VLM 不可用或识别失败时返回 503，M8 转入手动校准。

```jsonc
// 返回 200：FigureDetection
{
  "schema_version": "0.3.0",
  "figure_id": "fig_01",
  "plot_area": { "u0": 96, "v0": 40, "u1": 680, "v1": 512 },  // 绘图区边框
  "axes": {
    "x": {
      "label": "Concentration", "unit": "mg/L", "scale": "linear",   // scale: linear | log10
      "ticks": [                                              // 识别到的全部刻度
        { "px": [118, 512], "value": 0.0, "confidence": 0.97 },
        { "px": [380, 512], "value": 0.35, "confidence": 0.93 },
        { "px": [642, 512], "value": 0.70, "confidence": 0.95 }
      ]
    },
    "y": { "label": "Absorbance", "unit": "", "scale": "linear", "ticks": [ /* 同上 */ ] }
  },
  "calibration": { /* Calibration，见下，取每个轴相距最远的两个刻度 */ },
  "series": [
    { "id": "A", "label": "Nessler", "color": "#1f1f1f", "marker": "x", "confidence": 0.88 }
  ],
  "warnings": [],                                   // 例如 "y 轴只识别到 2 个刻度，无法计算残差"
  "engine": { "vlm": "glm-5.3-flash", "cached": false }  // cached=true 表示命中演示缓存
}
```

#### Calibration 校准

每个轴用两个参考点：参考点的像素位置和它在坐标轴上代表的数值。由 M2 给出建议，用户在 M8 里确认或拖动后提交。

```jsonc
{
  "x": { "scale": "linear", "p1": { "px": [118, 512], "value": 0.0 }, "p2": { "px": [642, 512], "value": 0.70 } },
  "y": { "scale": "linear", "p1": { "px": [96, 470], "value": 0.0 }, "p2": { "px": [96, 132], "value": 0.35 } }
}
```

#### 坐标换算

M2 和 M8 共用这一份定义（M8 只用于光标读数的显示）。假设截图里的坐标轴是水平、竖直的，没有旋转，所以 x 只用 u，y 只用 v。以 x 轴为例，p1、p2 分别是 (u₁, a₁)、(u₂, a₂)：

- 线性轴：`x = a₁ + (u − u₁) · (a₂ − a₁) / (u₂ − u₁)`
- 对数轴（log10）：`x = 10 ^ ( lg a₁ + (u − u₁) · (lg a₂ − lg a₁) / (u₂ − u₁) )`

y 轴相同，把 u 换成 v。两个参考点的像素坐标相同（u₁ = u₂）或对数轴上出现 a ≤ 0 时，返回 422。

**校准残差** `residual_px`：用这组校准把识别到的其余刻度的数值反算成像素位置，与实际位置之差的均方根。每个轴都只有两个刻度时，残差为 `null`。

#### 提取：`POST /api/m2/figures/{id}/extract`

```jsonc
// 请求：ExtractRequest
{
  "schema_version": "0.3.0",
  "calibration": { /* Calibration */ },
  "mode": "auto",                  // auto：按曲线颜色自动提取；manual：使用 points_px
  "series_id": "A",                // auto 时必填
  "points_px": null,               // manual 时必填：[[u, v], …]
  "columns": {                     // 写进数据集的列名和单位，默认取识别到的轴标题
    "x": { "name": "氨氮浓度", "unit": "mg/L" },
    "y": { "name": "吸光度", "unit": "" }
  }
}
```

```jsonc
// 返回 200：ExtractResult
{
  "schema_version": "0.3.0",
  "dataset": {                     // Dataset，source = literature，已写入共享存储
    "schema_version": "0.3.0",
    "id": "ds_lit_01",
    "source": "literature",
    "meta": { "title": "图1(b) · 纳氏试剂法标准曲线", "doi": "10.3866/PKU.DXHX201807034", "figure": "图1(b)",
              "image_ref": "/api/m2/figures/fig_01/image" },
    "columns": [ { "key": "x", "name": "氨氮浓度", "unit": "mg/L" }, { "key": "y", "name": "吸光度", "unit": "" } ],
    "rows": [ { "id": "L1", "series": "std", "values": { "x": 0.105, "y": 0.075 }, "verified": false } ]
  },
  "points_px": [ { "point_id": "L1", "px": [608.4, 455.1] } ],   // M8 用来在原图上叠加数据点
  "residual_px": 0.4,
  "warnings": []                   // auto 模式没找到点时 rows 为空，并在这里说明原因
}
```

- 同一张图、同一条曲线重复提取，覆盖同一个 `dataset_id`。
- 用户在 M8 里拖动或删除提取出的点后，以 `mode: "manual"` 和修正后的 `points_px` 再提交一次，结果会覆盖原数据。
- 换算只发生在 M2。M8 不会自己算出数值再写入数据集。

### M8 依赖的其他接口

状态：**已定（zcode 确认，2026-10-17）**。

| 模块 | 方法与路径 | 请求 | 返回 |
|---|---|---|---|
| 共享存储 | `GET /api/datasets/{id}` | — | Dataset |
| 共享存储 | `PUT /api/datasets/{id}` | Dataset（用户校正后，`verified: true`） | Dataset |
| M3 | `GET /api/m3/templates` | — | 模板列表：id、名称、model、必需角色、公式、预置参照、状态（演示 / 规划） |
| M3 | `POST /api/m3/contexts` | `{ template_id }` | ExperimentContext |
| M3 | `GET` / `PUT /api/m3/contexts/{id}` | ExperimentContext | ExperimentContext |
| M1 | `POST /api/m1/records` | 表单：`image`、`context_id` | Dataset（`source: my_experiment`，带 `confidence`；识别不确定的格子值置 `null`） |
| M4 | `POST /api/m4/analyze` | `{ context_id }` | AnalysisResult（含 `qc_results`、三层 `comparison`） |
| M5 | `POST /api/m5/findings` | `{ context_id }` | SSE 流：`event: finding` 逐条推 Finding JSON，`event: done` 收尾，`event: error` 带 error 对象 |
| M6 | `POST /api/m6/simulate` | Simulation 请求 | Simulation 返回 |
| M7 | `POST /api/m7/export` | `{ context_id, format: "md" \| "docx" \| "png", include: { figure, anomalies, suggestions, quality_control, sources } }` | 文件 |

M5 的 SSE 事件载荷都是单行 JSON。断流时 M8 按 503 兜底处理。

---

## 变更记录

### 0.3.0（2026-10-17）

演示案例由银镜反应改为水质氨氮检测（HJ 535-2009）带动的契约升级：

- Dataset：行 `series` 约定类别（`std`/`blank`/`sample:*`/`qc:crm`/`qc:spike`）；支持条件列（取样体积、稀释倍数）。
- ExperimentContext：`variables` 从 x/y 两列升级为角色绑定；新增 `reference` 三层参照（文献数据集 + CRM 真值 + 法规限值，含 `space: raw/transformed` 声明，落定 product.md 待定事项）；新增 `qc_rules` 质控规则包。
- 新增模型注册表：`linear_calibration`（氨氮）与 `arrhenius`（碘钟，第二模板）并列，`derived` 改为按模型的开放对象。
- AnalysisResult：新增 `predictions`（样品反推，含扩展不确定度与体积/稀释换算）、`qc_results`（质控逐条判定挂条文）、`comparison` 三层判定；`residuals` 离群判定改为格拉布斯（GB/T 4883）。
- Finding：`evidence` 改为类型化引用（point/fit/qc/comparison）。**此为不兼容变更**；因 0.2.0 尚无代码消费方，在草案期内直接修订，不升主版本。
- HTTP：「M8 依赖的其他接口」由提议转已定；M5 明确 SSE 事件协议；M7 `include` 增加 `quality_control`；后端出网加 https-only 与私网拒绝约束。
- 示例数值更新为氨氮演示案例的真实口径（斜率 0.4026 等来自实测拟合，文献斜率 0.13933 来自《大学化学》2019 图1(b) 印刷方程）。

### 0.2.0（2026-10-16）

初版后补记：M2 HTTP 接口定稿；M8 依赖接口列为提议。
