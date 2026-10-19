import { useCallback, useEffect, useMemo, useReducer } from "react";
import { api, streamFindings } from "./api";
import { loadShadow } from "./shadow";
import { Shell } from "./Shell";
import { Cover } from "./screens/Cover";
import { ContextScreen } from "./screens/ContextScreen";
import { MyData } from "./screens/MyData";
import { Literature } from "./screens/Literature";
import { Analysis } from "./screens/Analysis";
import { Export } from "./screens/Export";
import type { Dataset } from "./types";
import { WorkbenchContext, errorText, initialState, reducer, type Workbench } from "./workbench";

const DEMO_TEMPLATE = "tpl_alkali_titration";

export function App() {
  const [s, dispatch] = useReducer(reducer, initialState);
  const patch = (p: Partial<typeof s>) => dispatch({ type: "patch", patch: p });

  useEffect(() => {
    api.health()
      .then(() => api.templates())
      .then((templates) => patch({ online: true, templates }))
      .catch(() => patch({ online: false }));
  }, []);

  // 兜底：后端整体不可用时加载影子快照走完界面流程（contracts · 演示保底）
  const enterShadow = useCallback(async (reason: string) => {
    const snap = await loadShadow();
    const mine = snap.datasets.find((d) => d.id === snap.context.datasets.mine) ?? snap.datasets[0];
    patch({
      shadow: true,
      ctx: snap.context,
      dataset: mine,
      analysis: snap.analysis,
      findings: snap.findings,
      findingsStatus: "done",
      busy: null,
      notice: { tone: "info", text: `${reason}，已加载演示保底数据。推演和导出需要后端。` },
    });
    dispatch({ type: "go", step: 1 });
  }, []);

  const runFindings = useCallback(async (contextId: string) => {
    patch({ findings: [], findingsStatus: "streaming" });
    try {
      await streamFindings(contextId, (finding) => dispatch({ type: "finding", finding }));
      patch({ findingsStatus: "done" });
    } catch (e) {
      patch({ findingsStatus: "error", notice: { tone: "error", text: `AI 解读失败：${errorText(e)}` } });
    }
  }, []);

  const wb: Workbench = useMemo(() => ({
    s,
    dispatch,
    loadDemo: async () => {
      if (s.online === false) return enterShadow("后端不可用");
      patch({ busy: "正在载入演示模板" });
      try {
        const ctx = await api.createContext(DEMO_TEMPLATE);
        patch({ ctx, dataset: null, analysis: null, findings: [], findingsStatus: "idle", busy: null, shadow: false });
        dispatch({ type: "go", step: 1 });
      } catch (e) {
        await enterShadow(`载入模板失败：${errorText(e)}`);
      }
    },
    recognize: async (image: Blob, filename: string) => {
      if (!s.ctx) return;
      if (s.photoUrl) URL.revokeObjectURL(s.photoUrl);
      patch({ photoUrl: URL.createObjectURL(image), busy: "正在识别手写记录" });
      try {
        const dataset = await api.recognize(s.ctx.id, image, filename);
        patch({ dataset, busy: null, ctx: { ...s.ctx, datasets: { ...s.ctx.datasets, mine: dataset.id } } });
      } catch (e) {
        patch({ busy: null, notice: { tone: "error", text: `识别失败：${errorText(e)}。可以载入演示保底数据继续。` } });
      }
    },
    confirmDataset: async (ds: Dataset) => {
      if (!s.ctx) return;
      if (s.shadow) {
        patch({ dataset: ds });
        dispatch({ type: "complete", step: 2, next: 3 });
        return;
      }
      patch({ busy: "正在保存校正结果" });
      try {
        const saved = await api.putDataset(ds);
        patch({ dataset: saved, busy: "M4 正在计算" });
        const analysis = await api.analyze(s.ctx.id);
        patch({ analysis, busy: null });
        dispatch({ type: "complete", step: 2, next: 3 });
        void runFindings(s.ctx.id);
      } catch (e) {
        patch({ busy: null, notice: { tone: "error", text: `计算失败：${errorText(e)}` } });
      }
    },
    rerunFindings: async () => {
      if (s.ctx && !s.shadow) await runFindings(s.ctx.id);
    },
  }), [s, enterShadow, runFindings]);

  const screen = [<Cover />, <ContextScreen />, <MyData />, <Literature />, <Analysis />, <Export />][s.step];

  return (
    <WorkbenchContext.Provider value={wb}>
      {s.step === 0 ? screen : <Shell>{screen}</Shell>}
    </WorkbenchContext.Provider>
  );
}
