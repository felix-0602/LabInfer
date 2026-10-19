// 契约的前端视图（docs/contracts.md）。后端目前出 0.6.0，0.7.0 新增的节都是可选字段，有就画、没有就不显示。
// 只声明 M8 读到的字段，其余透传不改写。

export type Json = Record<string, unknown>;

export interface Column { key: string; name?: string; unit?: string; role?: string; optional?: boolean }

export interface Row {
  id: string;
  series: string;
  values: Record<string, number | null>;
  confidence?: Record<string, number>;
  verified?: boolean;
}

export interface Dataset {
  schema_version: string;
  id: string;
  source: "my_experiment" | "literature";
  meta: { title?: string; doi?: string | null; figure?: string | null; image_ref?: string };
  columns: Column[];
  rows: Row[];
  cached?: boolean;
  [k: string]: unknown;
}

export interface Limit { label: string; value: number; unit?: string; operator?: string }

export interface ExperimentContext {
  schema_version: string;
  id: string;
  name: string;
  purpose: string;
  model: string;
  // 多为数值常数；0.7.0 起也有对象（如 indicator: { name, ph_range }）
  model_params?: Record<string, unknown>;
  variables: { columns: Column[] };
  reference: { datasets: ReferenceDataset[]; crm: Json | null; limits: Limit[] };
  qc_rules: { rule_id: string; params: Json; citation?: string }[];
  datasets: { mine: string | null };
  [k: string]: unknown;
}

export interface ReferenceDataset {
  dataset_id: string;
  columns?: Record<string, string>;
  space?: "raw" | "transformed";
  meta?: { doi?: string | null; figure?: string | null; note?: string; v_eq_ml?: number };
}

export interface Template {
  id: string;
  name: string;
  model: string;
  required_roles: string[];
  formula: string;
  reference_preview: { n_datasets: number; crm: Json | null; limits: Limit[] };
  status: "演示" | "规划" | "自定义";
}

export interface PointRef { dataset_id: string; point_id: string }

export interface Fit {
  dataset_id: string;
  slope: number;
  intercept: number;
  r2: number;
  n: number;
  derived: Record<string, number>;
}

export interface Prediction {
  dataset_id: string;
  point_id: string;
  value: number;
  u95: number;
  unit: string;
  input: Record<string, number>;
  as_reported: number;
}

export interface QcResult {
  rule_id: string;
  pass: boolean;
  value: number;
  value_pct?: number;
  limit: number;
  subjects: PointRef[];
  citation?: string;
}

export interface LimitVerdict { point_id: string; value: number; limit: number; label: string; verdict: string }

export interface AnalysisResult {
  schema_version: string;
  context_id: string;
  model: string;
  transformed: {
    dataset_id: string;
    x_label: string; x_unit: string; y_label: string; y_unit: string;
    points: { point_id: string; x: number; y: number }[];
  }[];
  fits: Fit[];
  predictions: Prediction[];
  residuals: { dataset_id: string; point_id: string; residual: number; outlier: boolean }[];
  qc_results: QcResult[];
  comparison: { vs_reference: Json[]; vs_limit: LimitVerdict[]; vs_crm: Json | null };
  titration_curve?: TitrationCurve;
  error_budget?: ErrorBudget;
}

// 0.7.0：理论滴定曲线与学生终点，x 为 ΔV（mL），y 为 pH
export interface TitrationCurve {
  x_label: string; x_unit: string; y_label: string; y_unit: string;
  basis: { point_id: string; v_eq_ml: number; closed_system?: boolean; pka1?: number; pka2?: number };
  theory: { x: number; y: number }[];
  ph_eq: number;
  indicator: { name: string; ph_range: [number, number]; dv_window_ml: [number, number] };
  endpoints: { dataset_id: string; point_id: string; dv_ml: number; ph: number }[];
  literature: { dataset_id: string; points: { x: number; y: number }[] }[];
}

// 0.7.0：仪器可解释的相对偏差 vs 实测离散
export interface ErrorBudget {
  items: { source: string; rel: number; subject: PointRef }[];
  expected_rel_dev: number;
  observed_rel_dev: number;
  ratio: number;
}

export type Evidence =
  | { type: "point"; dataset_id: string; point_id: string }
  | { type: "fit"; dataset_id: string }
  | { type: "qc"; rule_id: string }
  | { type: "comparison"; target: string };

export interface Finding {
  schema_version: string;
  id: string;
  type: "pattern" | "conclusion" | "anomaly" | "suggestion" | string;
  text: string;
  evidence: Evidence[];
  simulatable: boolean;
  simulation: { param: string; from: number; to: number; unit: string } | null;
  ladder?: { rung_id: string; level: number; text: string }[];
  verification?: { status: "verified" | "refuted" | "unverified"; hypothesis: string; reason: string };
}

export interface Simulation {
  schema_version: string;
  finding_id: string;
  predicted: Record<string, number>;
  curve: { x: number; y: number }[];
}

export interface Snapshot {
  schema_version: string;
  context: ExperimentContext;
  datasets: Dataset[];
  analysis: AnalysisResult;
  findings: Finding[];
}

// ---- M2 曲线取数 ----

export type Px = [number, number];

export interface Figure {
  schema_version: string;
  id: string;
  image_url: string;
  width: number;
  height: number;
  sha256: string;
  meta: { doi: string | null; figure: string | null };
}

export type AxisScale = "linear" | "log10";

export interface AxisCalibration {
  scale: AxisScale;
  p1: { px: Px; value: number };
  p2: { px: Px; value: number };
}

// 识别建议里某个轴刻度不足时为 null，由用户在画布上手动放点
export interface Calibration { x: AxisCalibration | null; y: AxisCalibration | null }

export interface FigureDetection {
  schema_version: string;
  figure_id: string;
  plot_area: { u0: number; v0: number; u1: number; v1: number } | null;
  axes: Record<"x" | "y", { label: string; unit: string; scale: AxisScale; ticks: { px: Px; value: number; confidence: number }[] }>;
  calibration: Calibration;
  series: { id: string; label: string; color: string | null; marker: string | null; confidence: number }[];
  warnings: string[];
  engine?: { vlm?: string; cached?: boolean };
}

export interface ExtractResult {
  schema_version: string;
  dataset: Dataset;
  points_px: { point_id: string; px: Px }[];
  residual_px: number | null;
  warnings: string[];
}
