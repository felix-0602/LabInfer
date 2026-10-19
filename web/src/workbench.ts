import { createContext, useContext } from "react";
import { ApiError } from "./api";
import type { AnalysisResult, Dataset, ExperimentContext, Finding, Template } from "./types";

// 页面状态只在浏览器内存里（architecture.md · M8）。刷新后从后端重新拉取。

export type Step = 0 | 1 | 2 | 3 | 4 | 5;

export const STEPS: { step: Step; label: string; module: string }[] = [
  { step: 1, label: "上下文", module: "M3 · 实验上下文" },
  { step: 2, label: "我的数据", module: "M1 · 记录识别" },
  { step: 3, label: "文献取数", module: "M2 · 曲线取数" },
  { step: 4, label: "分析", module: "M4 计算 · M5 解读 · M6 推演" },
  { step: 5, label: "导出", module: "M7 · 报告导出" },
];

export interface State {
  step: Step;
  done: Set<Step>;
  // null = 还没探测；false = 后端不可用，走影子快照
  online: boolean | null;
  shadow: boolean;
  templates: Template[];
  ctx: ExperimentContext | null;
  dataset: Dataset | null;
  photoUrl: string | null;
  analysis: AnalysisResult | null;
  findings: Finding[];
  findingsStatus: "idle" | "streaming" | "done" | "error";
  busy: string | null;
  notice: { tone: "info" | "error"; text: string } | null;
}

export const initialState: State = {
  step: 0,
  done: new Set(),
  online: null,
  shadow: false,
  templates: [],
  ctx: null,
  dataset: null,
  photoUrl: null,
  analysis: null,
  findings: [],
  findingsStatus: "idle",
  busy: null,
  notice: null,
};

export type Action =
  | { type: "patch"; patch: Partial<State> }
  | { type: "go"; step: Step }
  | { type: "complete"; step: Step; next?: Step }
  | { type: "finding"; finding: Finding };

export function reducer(s: State, a: Action): State {
  switch (a.type) {
    case "patch":
      return { ...s, ...a.patch };
    case "go":
      return { ...s, step: a.step, notice: null };
    case "complete": {
      const done = new Set(s.done);
      done.add(a.step);
      return { ...s, done, step: a.next ?? s.step, notice: null };
    }
    case "finding":
      return { ...s, findings: [...s.findings.filter((f) => f.id !== a.finding.id), a.finding] };
  }
}

export interface Workbench {
  s: State;
  dispatch: (a: Action) => void;
  loadDemo: () => Promise<void>;
  recognize: (image: Blob, filename: string) => Promise<void>;
  confirmDataset: (ds: Dataset) => Promise<void>;
  rerunFindings: () => Promise<void>;
}

export const WorkbenchContext = createContext<Workbench | null>(null);

export function useWorkbench(): Workbench {
  const w = useContext(WorkbenchContext);
  if (!w) throw new Error("WorkbenchContext 未挂载");
  return w;
}

export function errorText(e: unknown): string {
  if (e instanceof ApiError) return `${e.message}（${e.code}）`;
  return e instanceof Error ? e.message : String(e);
}
