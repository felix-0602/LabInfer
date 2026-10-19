import type { AnalysisResult, Dataset, ExperimentContext, Finding, Simulation, Template } from "./types";

// 契约错误体：{ error: { code, message, detail } }
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "NETWORK", "后端连不上");
  }
  if (!res.ok) {
    let code = "HTTP_" + res.status;
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch { /* 非 JSON 错误体 */ }
    throw new ApiError(res.status, code, message);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<{ status: string; contract_version: string }>("/api/health"),
  templates: () => request<Template[]>("/api/m3/templates"),
  createContext: (template_id: string) => request<ExperimentContext>("/api/m3/contexts", json({ template_id })),
  getContext: (id: string) => request<ExperimentContext>(`/api/m3/contexts/${encodeURIComponent(id)}`),
  getDataset: (id: string) => request<Dataset>(`/api/datasets/${encodeURIComponent(id)}`),
  putDataset: (ds: Dataset) =>
    request<Dataset>(`/api/datasets/${encodeURIComponent(ds.id)}`, { ...json(ds), method: "PUT" }),
  recognize: (context_id: string, image: Blob, filename: string) => {
    const form = new FormData();
    form.append("context_id", context_id);
    form.append("image", image, filename);
    return request<Dataset>("/api/m1/records", { method: "POST", body: form });
  },
  analyze: (context_id: string) => request<AnalysisResult>("/api/m4/analyze", json({ context_id })),
  simulate: (body: { context_id: string; finding_id: string; param: string; from: number; to: number; unit: string }) =>
    request<Simulation>("/api/m6/simulate", json({ schema_version: "0.6.0", ...body })),
  exportReport: async (context_id: string, format: "md" | "docx", include: Record<string, boolean>) => {
    const res = await fetch("/api/m7/export", json({ context_id, format, include }));
    if (!res.ok) throw new ApiError(res.status, "EXPORT_FAILED", "导出失败");
    return res.blob();
  },
};

// M5 是 POST + SSE，EventSource 不支持 POST，用 fetch 流逐段解析。
export async function streamFindings(context_id: string, onFinding: (f: Finding) => void): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/api/m5/findings", json({ context_id }));
  } catch {
    throw new ApiError(503, "NETWORK", "AI 解读连不上");
  }
  if (!res.ok || !res.body) throw new ApiError(res.status, "LLM_UNAVAILABLE", "AI 解读暂时不可用");

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  let done = false;
  while (!done) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buf += chunk.value;
    let sep: number;
    while ((sep = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (event === "finding") onFinding(JSON.parse(data));
      else if (event === "error") {
        const err = JSON.parse(data)?.error ?? {};
        throw new ApiError(503, err.code ?? "LLM_ERROR", err.message ?? "AI 解读出错");
      } else if (event === "done") done = true;
    }
  }
  // 契约：断流（没收到 done）按 503 兜底
  if (!done) throw new ApiError(503, "STREAM_CLOSED", "AI 解读中途断开");
}
