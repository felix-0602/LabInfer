# 数据契约

**当前版本：0.7.0（滴定曲线参照、误差预算与讲解阶梯）**

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

M1、M2 输出，M4 读取。列不限制名称，行用 `series` 标注类别，M4 据此分组：`std`（标准系列点，或标定平行份）、`blank`（空白）、`sample:<名称>`（样品，平行样同名成组）、`qc:crm`（质控样）、`qc:spike`（加标样）。

```jsonc
{
  "schema_version": "0.5.0",
  "id": "ds_mine_01",
  "source": "my_experiment",          // my_experiment | literature
  "meta": {
    "title": "HCl 标定与碱灰总碱度 数据记录",
    "doi": null,                       // source=literature 时必填
    "figure": null,                    // 如 "图1(b)"
    "image_ref": "uploads/xxx.jpg"     // 原始图片
  },
  "columns": [
    { "key": "m",  "name": "基准 Na₂CO₃ 质量", "unit": "g" },   // 条件列：见行示例
    { "key": "V",  "name": "HCl 滴定体积",     "unit": "mL" },
    { "key": "ms", "name": "碱灰试样质量",     "unit": "g" }
  ],
  "rows": [
    // 标定行（series=std）：基准物质质量与滴定体积
    { "id": "p1", "series": "std", "values": { "m": 0.1549, "V": 28.54 },
      "confidence": { "m": 0.98, "V": 0.62 }, "verified": false },
    // 测定行（series=sample:*）：同一试样的三份平行滴定共用同一个 series 名
    { "id": "s1", "series": "sample:碱灰", "values": { "V": 29.55, "ms": 1.5919 },
      "confidence": {}, "verified": false }
  ]
}
```

`linear_calibration` 等模型的条件列（取样体积、稀释倍数）同样挂在行的 `values` 里，角色绑定见[模型注册表](#模型注册表)。

`confidence` 为识别置信度 0～1，可选，仅 M1 产出的数据集携带；低置信格子由用户在 M8 校正后置 `verified: true`。

## ExperimentContext 实验上下文

M3 输出，M4、M5 读取。

```jsonc
{
  "schema_version": "0.5.0",
  "id": "ctx_01",
  "name": "HCl 标定与碱灰总碱度（GB/T 601-2016 无水碳酸钠法）",
  "purpose": "以基准无水碳酸钠标定 HCl 浓度，测定碱灰总碱度（以 Na₂O 计），检查平行测定精密度",
  "model": "titration_standardization",
  "variables": {
    "columns": [                       // 角色→实际列的绑定
      { "key": "m",  "role": "mass",        "unit": "g" },   // 标定行：基准物质质量
      { "key": "V",  "role": "volume",      "unit": "mL" },  // 标定/测定行：滴定体积
      { "key": "ms", "role": "sample_mass", "unit": "g", "optional": true }
    ]
  },
  "datasets": { "mine": "ds_mine_01" },
  "reference": {
    "datasets": [                      // 第一层：文献数据集（滴定演示不用，曲线类模板用）
      { "dataset_id": "ds_lit_01",
        "columns": { "concentration": "x", "signal": "y" },  // 文献数据集的列→角色
        "space": "raw",                // raw=原始量；transformed=已在模型拟合空间（M4 不再变换）
        "meta": { "doi": "10.xxxx/xxxxx", "figure": "图1(b)", "note": "…" } }
    ],
    "crm": null,                       // 第二层：有证标准物质真值（按需声明）
    "limits": [                        // 第三层：限值或理论参照
      { "label": "纯 Na₂CO₃ 理论总碱度（以 Na₂O 计）", "value": 58.47,
        "unit": "%", "operator": "<=" } ]
  },
  "qc_rules": [                        // 质控规则包，M4 执行，M5 引用条文
    { "rule_id": "standardization_rpad", "params": { "max": 0.002 },
      "citation": "GB/T 601-2016 / 分析化学实验教学要求（相对平均偏差 ≤0.2%）" },
    { "rule_id": "parallel_rpd",       "params": { "max": 0.002 }, "citation": "分析化学实验平行测定要求" },
    { "rule_id": "outlier_grubbs",     "params": { "alpha": 0.05 }, "citation": "GB/T 4883" }
  ],
  "model_params": {                    // 模型常数（titration_standardization）
    "molar_mass_na2co3_g_mol": 105.99, "molar_mass_na2o_g_mol": 61.979,
    "stock_volume_ml": 250, "aliquot_volume_ml": 25,
    // 0.7.0 可选：滴定曲线与误差预算的常数，缺省时不输出对应节
    "pka1": 6.35, "pka2": 10.33,       // 碳酸 25 ℃
    "initial_water_ml": 30,            // 溶解基准物的水量（教材 25～35 mL 取中值）
    "indicator": { "name": "甲基橙", "ph_range": [3.1, 4.4] },
    "balance_error_g": 0.0001,         // 单次称量最大误差，差减法计两次
    "burette_error_ml": 0.01 },        // 单次读数最大误差，计两次
  "ladder": {                          // 0.7.0 可选：讲解阶梯，规则见 wiki.md#讲解阶梯
    "base_level": 3,
    "rungs": [
      { "rung_id": "L4-indicator", "level": 4, "title": "为什么用甲基橙",
        "concept": "Na₂CO₃ 有两个化学计量点，第二个落在甲基橙变色区内",
        "anchor": { "type": "comparison", "target": "titration_curve" },
        "trigger": null,               // null = 锚点存在即可出现；或 { "qc_fail": "standardization_rpad" }
        "source": "分析化学教材 酸碱滴定章" } ] }
}
```

`space` 解决「文献常画变换后的量（如 ln(1/t)–1/T）而我的数据是原始量」的问题：`transformed` 的参照数据集直接在拟合空间参与对比（product.md 待定事项落定）。

**滴定曲线参照（0.7.0）**：文献滴定曲线由 M2 取数，作为 `reference.datasets` 的一项，列角色为 `titrant_volume`（x）与 `ph`（y）。文献的浓度与学生不同，M4 统一换到滴定分数 a = V / V计量点 再叠加，因此参照项需在 `meta` 里给出文献图的计量点体积 `v_eq_ml`；若文献横轴本身就是滴定分数或百分数，声明 `space: "transformed"`，M4 不再换算。

## 模型注册表

M4 按注册表实现，新增模型 = 新增一行 + 一个实现，路由与契约不变。

| model | 必需角色 | 可选角色 | 变换到拟合空间 | derived 字段 | M6 可推演参数 |
|---|---|---|---|---|---|
| `linear_calibration` | `concentration`, `signal` | `sample_volume`, `dilution_factor` | 恒等 | `sensitivity`, `slope_ci95` | `dilution_factor`, `sample_volume` |
| `arrhenius` | `temperature`, `time` | — | x→1/T（K），y→ln(1/t) | `Ea_kJ_per_mol`, `Ea_ci95` | `temperature` |
| `titration_standardization` | `mass`, `volume` | `sample_mass` | 恒等（V–m 平面，过原点拟合） | `c_hcl`, `c_regression`, `rel_avg_dev_c`, `w_na2o_mean_pct`, `rel_avg_dev_w` | `titrant_volume_delta`, `co2_retained_fraction`（0.7.0） |

浓度反推公式（linear_calibration，样品行）：

`ρ = (A − intercept) / slope × (V定容 / V取样) × dil`

其中 `V定容` 由模板参数提供。**这个换算必须由 M4 完成**——取样体积与稀释倍数是学生计算错误的高发区。

滴定公式（titration_standardization，常数来自 `model_params`）：

- 标定段（`std` 行）：`c(HCl) = 2m / (M(Na₂CO₃)·V)`，等价于 GB/T 601-2016 的 `m·1000 / (V·52.994)`；逐份计算后取平均，精密度用相对平均偏差。
- 测定段（`sample:*` 行）：`w(Na₂O) = c̄·V·M(Na₂O)/2 × V容/V移 ÷ m样 ×100%`（滴定反应 Na₂CO₃ + 2HCl，故 n(Na₂O) = n(HCl)/2）。`V容/V移` 由模板参数提供（演示案例 250/25）。
- 推演（M6，`param=titrant_volume_delta`）：w ∝ V，曲线 x 为 ΔV（mL）、y 为 w(Na₂O)（%）。
- 理论滴定曲线（0.7.0）：对标定段称样量居中的一份，按电荷平衡 `[H⁺] + [Na⁺] = [OH⁻] + [HCO₃⁻] + 2[CO₃²⁻] + [Cl⁻]` 逐点解 pH（封闭体系，CO₂ 不逸出；计量点 pH 约 3.9，与教材 3.8～3.9 一致）。每份终点的偏差 `ΔV_i = V_i − 2m_i / (M(Na₂CO₃)·c̄)`，按 ΔV 放到曲线上。指示剂窗口为曲线上 pH 落在 `indicator.ph_range` 内的 ΔV 区间。
- 推演（M6，`param=co2_retained_fraction`，0～1）：计量点附近残留 CO₂ 的比例，1 = 未煮沸（封闭），0 = 已煮沸驱尽；曲线 x 为 ΔV（mL）、y 为 pH，用于展示煮沸让突跃变陡。
- 误差预算（0.7.0）：按教材最大误差口径，称量相对误差 `2·balance_error_g / m_i`、读数相对误差 `2·burette_error_ml / V_i`，两项方和根得到仪器可解释的相对偏差，与实测相对平均偏差对比。

## AnalysisResult 分析结果

M4 输出，M5、M6、M8 读取。下面第一个例子是通用形态（linear_calibration，三层参照齐全）；第二个是演示案例（titration_standardization）的真实输出节选。

```jsonc
{
  "schema_version": "0.5.0",
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

演示案例（titration_standardization）的输出节选，数值为真实演示数据：

```jsonc
{
  "schema_version": "0.5.0",
  "context_id": "ctx_demo",
  "model": "titration_standardization",
  "transformed": [                     // V–m 平面，M8 画散点 + 过原点拟合线
    { "dataset_id": "ds_mine_demo", "x_label": "m", "x_unit": "g",
      "y_label": "V", "y_unit": "mL",
      "points": [ { "point_id": "p1", "x": 0.1549, "y": 28.54 } ] }
  ],
  "fits": [
    { "dataset_id": "ds_mine_demo", "slope": 183.452866, "intercept": 0.0,
      "r2": 0.99976, "n": 3,
      "derived": { "c_hcl": 0.102735, "c_regression": 0.102859,
                   "rel_avg_dev_c": 0.013114,          // 1.31%
                   "w_na2o_mean_pct": 60.6313, "rel_avg_dev_w": 0.021404,  // 2.14%
                   "molar_mass_na2co3": 105.99, "molar_mass_na2o": 61.979 } }
  ],
  "predictions": [                      // 每个 sample 行一份 w(Na₂O)
    { "dataset_id": "ds_mine_demo", "point_id": "s1",
      "value": 59.098, "u95": 1.2497, "unit": "%",     // u95 只传播标定浓度（k=2）
      "input": { "V": 29.55 },
      "factors": { "c_hcl_mol_l": 0.102735, "sample_mass_g": 1.5919,
                   "stock_volume_ml": 250.0, "aliquot_volume_ml": 25.0 },
      "as_reported": 59.098 }
  ],
  "residuals": [                        // 标定段 c_i − c̄，离群用格拉布斯判
    { "dataset_id": "ds_mine_demo", "point_id": "p2", "residual": 0.002021,
      "outlier": false, "method": "grubbs", "p": null }
  ],
  "qc_results": [
    { "rule_id": "standardization_rpad", "pass": false, "value": 0.013114,
      "value_pct": 1.31, "limit": 0.002, "citation": "GB/T 601-2016 / 教学要求",
      "subjects": [ { "dataset_id": "ds_mine_demo", "point_id": "p1" } ] },
    { "rule_id": "parallel_rpd", "pass": false, "value": 0.021404,
      "value_pct": 2.14, "limit": 0.002, "citation": "分析化学实验平行测定要求",
      "subjects": [ { "dataset_id": "ds_mine_demo", "point_id": "s1" } ] },
    { "rule_id": "outlier_grubbs", "pass": true, "value": 1.074, "limit": 1.154,
      "citation": "GB/T 4883", "subjects": [] }
  ],
  "comparison": {
    "vs_reference": [],                 // 滴定演示不挂文献数据集
    "vs_limit": [
      { "point_id": "s1", "value": 59.098, "limit": 58.47,
        "label": "纯 Na₂CO₃ 理论总碱度（以 Na₂O 计）", "verdict": "exceed" } ],
    "vs_crm": null                      // 未声明 CRM 时为 null
  },
  "titration_curve": {                  // 0.7.0 可选：model_params 含 pka1/pka2 时输出
    "x_label": "ΔV", "x_unit": "mL", "y_label": "pH", "y_unit": "",
    "basis": { "point_id": "p3", "v_eq_ml": 30.67, "closed_system": true,
               "pka1": 6.35, "pka2": 10.33 },
    "theory": [ { "x": -1.0, "y": 5.2 } /* 计算值，步长由 M4 定 */ ],
    "ph_eq": 3.97,
    "indicator": { "name": "甲基橙", "ph_range": [3.1, 4.4],
                   "dv_window_ml": [-0.15, 0.46] /* 计算值：pH 4.4→3.1 */ },
    "endpoints": [                      // 学生终点，point_id 对应标定段行
      { "dataset_id": "ds_mine_demo", "point_id": "p2", "dv_ml": -0.649, "ph": 4.96 } ],
    "literature": [                     // 已换到同一 ΔV 坐标的文献曲线，未挂参照时为 []
      { "dataset_id": "ds_lit_02", "points": [ /* M2 取数后换算，示例省略 */ ] } ]
  },
  "error_budget": {                     // 0.7.0 可选：model_params 含 balance/burette 误差时输出
    "items": [
      { "source": "天平两次称量", "rel": 0.0013, "subject": { "dataset_id": "ds_mine_demo", "point_id": "p1" } },
      { "source": "滴定管两次读数", "rel": 0.0007, "subject": { "dataset_id": "ds_mine_demo", "point_id": "p1" } } ],
    "expected_rel_dev": 0.0015,         // 仪器可解释的相对偏差（取各份最大）
    "observed_rel_dev": 0.013114,       // 即 rel_avg_dev_c
    "ratio": 8.7
  }
}
```

`titration_curve` 与 `error_budget` 里标「计算值」的数由 M4 算出，示例只示意形状；M5 引用它们时照常过数字溯源校验。Finding 的 `evidence` 用 `{ "type": "comparison", "target": "titration_curve" }` 或 `"error_budget"` 指向这两节。

## Finding 结论

M5 输出一个数组，M6、M7、M8 读取。

```jsonc
{
  "schema_version": "0.5.0",
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
  "simulation": { "param": "dilution_factor", "from": 1, "to": 10, "unit": "" },
  "ladder": [                          // 0.7.0 可选：本条结论往上递的讲解，最多 2 级
    { "rung_id": "L5-error-type", "level": 5, "text": "……" } ]
}
```

`ladder[].rung_id` 必须是 ExperimentContext `ladder.rungs` 里存在且锚点出现在本条 `evidence` 中的一级；`text` 同样过数字溯源校验。

`verification`（0.7.0 可选，Could 7 虚拟实验台）：异常类结论经虚拟实验台 MCP 验证后的状态。

```jsonc
"verification": {
  "status": "refuted",                 // verified | refuted | unverified
  "hypothesis": "基准物吸水 1%",
  "calls": [                           // 工具调用记录，最多 3 条
    { "tool": "replay_with_fault", "args": { "fault": "primary_moisture", "value": 0.01 },
      "result": { "w_na2o_mean_pct": 59.06, "rel_avg_dev_c": 0.0131 } } ],
  "reason": "吸水 1% 只把总碱度推高约 1%，到不了实测 60.63%，也不改变 1.31% 的离散"
}
```

`calls[].result` 里的数与 `reason` 中的数同样过数字溯源校验（数值集合包含调用结果）。字段缺省等同 `unverified`。

`evidence[].type`：`point`（数据点）、`fit`（拟合对象）、`qc`（质控判定）、`comparison`（参照判定）。M8 联动时按 type 高亮对应元素。M5 校验器规则：`text` 中出现的数字必须能在 AnalysisResult 的数值集合中找到（±容差），`evidence` 引用的对象必须存在；不过校验的结论整条丢弃并回灌错误重生成一次，再失败则降级为模板文案。

## Simulation 参数推演

M6 的请求和返回，M8 调用。`param` 取值以[模型注册表](#模型注册表)的「M6 可推演参数」为准。

```jsonc
// 请求
{ "schema_version": "0.5.0", "context_id": "ctx_01", "finding_id": "f2",
  "param": "dilution_factor", "from": 1, "to": 10, "unit": "" }

// 返回（curve 在拟合空间，与 transformed 同坐标系）
{ "schema_version": "0.5.0", "finding_id": "f2",
  "predicted": { "dilution_factor": 5, "A": 0.112 },
  "curve": [{ "x": 0.556, "y": 0.226 }] }
```

`titration_volume_delta` 的返回：`curve` 的 x 为滴定体积系统偏差 ΔV（mL），y 为对应的 w(Na₂O)（%），例如

```jsonc
{ "schema_version": "0.5.0", "finding_id": "f_worst",
  "predicted": { "titrant_volume_delta_ml": -1, "w_na2o_pct": 60.578 },
  "curve": [{ "x": -2.0, "y": 58.578 }, { "x": 0.0, "y": 62.5779 }] }
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
  "schema_version": "0.5.0",
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
  "schema_version": "0.5.0",
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
  "schema_version": "0.5.0",
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
  "schema_version": "0.5.0",
  "dataset": {                     // Dataset，source = literature，已写入共享存储
    "schema_version": "0.5.0",
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
| M3 | `GET /api/m3/templates` | — | 模板列表：id、名称、model、必需角色、公式、预置参照、状态（演示 / 规划 / 自定义）。内置模板与模板库合并，业务规则见 [wiki.md](wiki.md) |
| M3 | `POST /api/m3/templates` | ExperimentContext 骨架（无 `datasets`；`model` 须在模型注册表内，必需角色齐全） | 写入模板库的模板，状态置 `自定义`；id 冲突返回 409 |
| M3 | `POST /api/m3/contexts` | `{ template_id }` | ExperimentContext（深拷贝模板，`datasets.mine = null`） |
| M3 | `GET` / `PUT /api/m3/contexts/{id}` | ExperimentContext | ExperimentContext |
| M1 | `POST /api/m1/records` | 表单：`image`、`context_id` | Dataset（`source: my_experiment`，带 `confidence`；识别不确定的格子值置 `null`） |
| M4 | `POST /api/m4/analyze` | `{ context_id }` | AnalysisResult（含 `qc_results`、三层 `comparison`） |
| M5 | `POST /api/m5/findings` | `{ context_id }` | SSE 流：`event: finding` 逐条推 Finding JSON，`event: done` 收尾，`event: error` 带 error 对象 |
| M6 | `POST /api/m6/simulate` | Simulation 请求 | Simulation 返回 |
| M7 | `POST /api/m7/export` | `{ context_id, format: "md" \| "docx" \| "png", include: { figure, anomalies, suggestions, quality_control, sources } }` | 文件 |
| 演示保底 | `GET /api/snapshot/{context_id}` | — | 全链路快照 JSON：`{ schema_version, context, datasets: [...], analysis, findings }` |

M5 的 SSE 事件载荷都是单行 JSON。断流时 M8 按 503 兜底处理。

`GET /api/snapshot/{context_id}` 返回演示保底所需的全部状态（我的数据集 + 参照数据集 + 分析结果 + 结论）。M8 在构建时拉取一次存为本地影子文件，后端整体不可用时加载影子数据走完界面流程。

### 演示切换对 M2 / M8 的边界约束（0.5.0，0.7.0 修订）

0.7.0 起滴定演示经过 M2：取教材或论文里的 HCl 滴定 Na₂CO₃ 滴定曲线，作为文献曲线参照（见 ExperimentContext「滴定曲线参照」）。以下为 0.5.0 原文，其中「不经过 M2」一句已被本段取代。

滴定演示不经过 M2 文献取数（参照是理论值与标准条文，不是文献曲线）。M2 的接口与能力不变，仍是曲线类模板的通用步骤；M8 的演示流程里对应步骤可跳过或作通用能力展示。M2、M8 的实现归各自负责人，本次切换不改它们的代码与设计稿。后端保证上表全部接口的请求/返回结构不变，只有取值口径随演示案例变化。M8 需要感知的变化只有三处：模板列表（`GET /api/m3/templates`）的演示项换成 `tpl_alkali_titration`；`AnalysisResult.fits[0].derived` 的字段集按模型注册表不同；M6 `param` 枚举增加 `titrant_volume_delta`。

---

## 变更记录

### 0.7.0（2026-10-18，提议，待 z 确认 M3/M4/M5/M6 部分）

滴定演示的可视化与讲解带动的兼容新增，全部为可选字段：

- ExperimentContext：`model_params` 新增 `pka1`、`pka2`、`initial_water_ml`、`indicator`、`balance_error_g`、`burette_error_ml`；新增 `ladder`（讲解阶梯，规则见 [wiki.md](wiki.md#讲解阶梯)）；文献滴定曲线作为 `reference.datasets` 一项，列角色 `titrant_volume`/`ph`，`meta.v_eq_ml` 供换算滴定分数。
- AnalysisResult：新增 `titration_curve`（理论曲线、指示剂窗口、学生终点 ΔV、换算后的文献曲线）与 `error_budget`（仪器误差预算对比实测离散）。
- Finding：新增 `ladder`（往上递的讲解，最多 2 级）；`evidence.comparison.target` 可取 `titration_curve`、`error_budget`。
- M6：`param` 枚举新增 `co2_retained_fraction`。
- Finding：新增 `verification`（虚拟实验台 MCP 验证状态与调用记录，Could 级）。
- M2/M8 边界：滴定演示恢复经过 M2（文献滴定曲线）。

### 0.6.0（2026-10-18）

组织知识与持久层带动的兼容新增：

- M3 新增 `POST /api/m3/templates`（沉淀自定义实验模板，id 冲突 409）；`GET /api/m3/templates` 的状态枚举增加 `自定义`。业务规则与生命周期见新增文档 [wiki.md](wiki.md)。
- 存储层新增 SQLite 后端（`LABINFER_STORAGE=sqlite` 启用），与 JSON 后端同接口；表结构与安全规则见新增文档 [sql.md](sql.md)。接口行为与默认后端不变。
- 新增文档 `docs/wiki.md`、`docs/sql.md` 并登记 README 索引。

### 0.5.0（2026-10-18）

演示案例由水质氨氮检测切换为 HCl 标定与碱灰总碱度（GB/T 601-2016）带动的兼容新增：

- 模型注册表新增 `titration_standardization`（必需角色 `mass`/`volume`，V–m 过原点拟合；`derived` 开放 `c_hcl`、`w_na2o_mean_pct` 等字段；M6 新参数 `titrant_volume_delta`）。
- `qc_rules` 新增规则 `standardization_rpad`（标定段相对平均偏差）；`parallel_rpd` 的取值改为**全组相对平均偏差**（此前只取前两个值的 RPD），两条规则的结果都附 `value_pct` 便于 M5 引用。
- Dataset 行 `series` 语义补充：`std` 亦用于标定平行份；条件列模式不变，按模型注册表的角色声明。
- ExperimentContext 的 `model_params` 首次承载模型常数（摩尔质量、定容/移取体积）。
- 示例与演示数据换成滴定案例的真实口径（c̄(HCl)=0.1027 mol/L，w̄(Na₂O)=60.63%，来自团队数据记录页 `design/assets/DEMO-01.jpg`）；氨氮示例退场，`linear_calibration` 模型保留在注册表供曲线类模板使用。
- M1 演示缓存改由 `scripts/seed_demo.py` 按记录页照片 sha256 烘焙，演示上传原图即命中，不依赖 VLM。

### 0.4.0（2026-10-17）

兼容新增：M8 依赖接口表增加演示保底快照 `GET /api/snapshot/{context_id}`（M8 构建时拉取存影子文件，后端不可用时本地加载）；M7 的 docx 格式落地实现。

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
