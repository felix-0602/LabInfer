# 数据契约

**当前版本：0.1.0（草案，开发启动前定稿）**

模块之间只通过本文件定义的数据结构交互。修改规则见 [versioning.md](versioning.md#契约版本)。

传输方式（HTTP 接口路径等）在开发启动时补充到本文件。

## 通用约定

- 所有顶层对象带 `schema_version` 字段，值为本文件的版本号。
- 数值统一用 JSON number，缺失值用 `null`。
- 单位写在列定义里，数值本身不带单位。温度在数据集中保留原始单位，换算由 M4 完成。
- 数据点用 `{dataset_id, point_id}` 定位，`point_id` 在同一个数据集内唯一。

## Dataset 数据集

M1、M2 输出，M4 读取。

```jsonc
{
  "schema_version": "0.1.0",
  "id": "ds_mine_01",
  "source": "my_experiment",          // my_experiment | literature
  "meta": {
    "title": "银镜反应 温度-出镜时间",
    "doi": null,                       // source=literature 时必填
    "figure": null,                    // 如 "Fig. 3b"
    "image_ref": "uploads/xxx.jpg"     // 原始图片
  },
  "columns": [
    { "key": "T", "name": "水浴温度", "unit": "°C" },
    { "key": "t", "name": "出镜时间", "unit": "s" }
  ],
  "rows": [
    {
      "id": "p1",
      "series": null,                  // 文献图中有多条曲线时填曲线名
      "values": { "T": 40, "t": 312 },
      "confidence": { "T": 0.98, "t": 0.71 },  // 识别置信度 0～1，可选
      "verified": false                // 用户是否已确认或校正
    }
  ]
}
```

## ExperimentContext 实验上下文

M3 输出，M4、M5 读取。

```jsonc
{
  "schema_version": "0.1.0",
  "id": "ctx_01",
  "name": "银镜反应动力学",
  "purpose": "测定表观活化能 Ea，验证 Arrhenius 规律",
  "model": "arrhenius",                // 第一版仅支持 arrhenius
  "variables": {
    "x": { "column": "T", "unit": "°C" },
    "y": { "column": "t", "unit": "s" }
  },
  "datasets": {
    "mine": "ds_mine_01",
    "reference": ["ds_lit_01"]
  },
  "references": [
    { "doi": "10.xxxx/xxxx", "note": "参照曲线来源" }
  ]
}
```

## AnalysisResult 分析结果

M4 输出，M5、M6、M8 读取。

```jsonc
{
  "schema_version": "0.1.0",
  "context_id": "ctx_01",
  "model": "arrhenius",
  "transformed": [                     // 换算后的作图数据
    {
      "dataset_id": "ds_mine_01",
      "x_label": "1/T", "x_unit": "K^-1",
      "y_label": "ln(1/t)", "y_unit": "ln(s^-1)",
      "points": [{ "point_id": "p1", "x": 0.003193, "y": -5.743 }]
    }
  ],
  "fits": [
    {
      "dataset_id": "ds_mine_01",
      "slope": -6512.3,
      "intercept": 15.05,
      "r2": 0.987,
      "derived": { "Ea_kJ_per_mol": 54.1, "Ea_ci95": [49.8, 58.4] }
    }
  ],
  "residuals": [
    { "dataset_id": "ds_mine_01", "point_id": "p3", "residual": 0.41, "z": 2.3, "outlier": true }
  ],
  "comparison": {
    "mine": "ds_mine_01",
    "reference": "ds_lit_01",
    "Ea_deviation_pct": 8.2
  }
}
```

## Finding 结论

M5 输出一个数组，M6、M7、M8 读取。

```jsonc
{
  "schema_version": "0.1.0",
  "id": "f3",
  "type": "anomaly",                   // pattern 规律 | conclusion 能证明什么 | anomaly 异常 | suggestion 建议
  "text": "50°C 处出镜时间明显偏离拟合直线……",
  "evidence": [{ "dataset_id": "ds_mine_01", "point_id": "p3" }],  // 至少一条
  "simulatable": false,
  "simulation": null                   // simulatable=true 时必填，见下
}
```

可推演时 `simulation` 的格式：

```jsonc
{ "param": "T", "from": 40, "to": 60, "unit": "°C" }
```

## Simulation 参数推演

M6 的请求和返回，M8 调用。

```jsonc
// 请求
{ "schema_version": "0.1.0", "context_id": "ctx_01", "finding_id": "f5",
  "param": "T", "from": 40, "to": 60, "unit": "°C" }

// 返回
{ "schema_version": "0.1.0", "finding_id": "f5",
  "predicted": { "T": 60, "t": 118 },
  "curve": [{ "x": 0.003193, "y": -5.743 }] }   // 与 transformed 相同的坐标系
```
