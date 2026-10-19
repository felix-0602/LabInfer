import { useEffect, useMemo, useRef, useState } from "react";
import demoPhoto from "../../../design/assets/DEMO-01.jpg";
import anchor from "../../../design/assets/GEN-07.webp";
import type { Dataset, Row } from "../types";
import { Anchor, stagger } from "../motion";
import { useWorkbench } from "../workbench";

// 低于这个置信度的格子要用户过目（architecture.md · M1）
const LOW_CONFIDENCE = 0.8;

type CellKey = `${string}/${string}`;
const cellKey = (rowId: string, col: string): CellKey => `${rowId}/${col}`;

function needsReview(row: Row, col: string): boolean {
  if (!(col in row.values)) return false;
  const v = row.values[col];
  const c = row.confidence?.[col];
  return v === null || (c !== undefined && c < LOW_CONFIDENCE);
}

export function MyData() {
  const { s, recognize, confirmDataset } = useWorkbench();
  const fileRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<Dataset | null>(null);
  const [checked, setChecked] = useState<Set<CellKey>>(new Set());
  const [editing, setEditing] = useState<CellKey | null>(null);

  useEffect(() => {
    setDraft(s.dataset ? structuredClone(s.dataset) : null);
    setChecked(new Set());
  }, [s.dataset]);

  const pending = useMemo(() => {
    if (!draft) return [] as CellKey[];
    const out: CellKey[] = [];
    for (const r of draft.rows)
      for (const c of draft.columns)
        if (needsReview(r, c.key) && !checked.has(cellKey(r.id, c.key))) out.push(cellKey(r.id, c.key));
    return out;
  }, [draft, checked]);

  const useDemoPhoto = async () => {
    const blob = await (await fetch(demoPhoto)).blob();
    await recognize(blob, "DEMO-01.jpg");
  };

  const commit = (key: CellKey, raw: string) => {
    if (!draft) return;
    const [rowId, col] = key.split("/") as [string, string];
    const num = raw.trim() === "" ? null : Number(raw);
    if (num !== null && !Number.isFinite(num)) return;
    setDraft({
      ...draft,
      rows: draft.rows.map((r) => (r.id === rowId ? { ...r, values: { ...r.values, [col]: num } } : r)),
    });
    if (num !== null) setChecked(new Set(checked).add(key));
  };

  const moveToNextPending = (from: CellKey) => {
    const next = pending.find((k) => k !== from);
    setEditing(next ?? null);
  };

  const confirm = () => {
    if (!draft) return;
    void confirmDataset({ ...draft, rows: draft.rows.map((r) => ({ ...r, verified: true })) });
  };

  const photo = s.photoUrl ?? (s.dataset ? demoPhoto : null);

  return (
    <div className="split">
      <section className="pane photo-pane">
        {photo ? (
          <div className={"record-wrap" + (s.busy ? " scanning" : "")}><img className="record-photo develop" src={photo} alt="手写实验记录照片" /></div>
        ) : (
          <div className={"dropzone rv" + (s.busy ? " scanning" : "")}>
            <div className="display ghost-word">DATA</div>
            <p>上传手写实验记录的照片，M1 会把它识别成表格。</p>
            <div className="actions">
              <button className="btn primary" disabled={!!s.busy} onClick={useDemoPhoto}>使用演示记录页 DEMO-01</button>
              <button className="btn ghost" disabled={!!s.busy} onClick={() => fileRef.current?.click()}>选择照片…</button>
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void recognize(f, f.name);
              }}
            />
          </div>
        )}
        {photo && !s.shadow && (
          <div className="photo-tools">
            <button className="btn ghost small" disabled={!!s.busy} onClick={() => fileRef.current?.click()}>换一张照片</button>
            <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void recognize(f, f.name);
            }} />
            {s.dataset?.cached && <span className="mono dim small">命中演示缓存，未调用 VLM</span>}
          </div>
        )}
      </section>

      <aside className="pane side-pane wide">
        <h2 className="rv" style={stagger(0)}>核对识别结果</h2>
        <p className="dim rv" style={stagger(1)}>低置信度的格子已用钴蓝斜纹标出，点击即可修改，Tab 跳到下一个。确认后数据会被锁定。</p>
        {draft ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                {draft.columns.map((c) => <th key={c.key}>{c.name ?? c.key} <span className="mono dim">{c.unit}</span></th>)}
                <th>置信度</th>
              </tr>
            </thead>
            <tbody>
              {draft.rows.map((r, ri) => {
                const confs = Object.values(r.confidence ?? {});
                const minConf = confs.length ? Math.min(...confs) : null;
                return (
                  <tr key={r.id} className="rv" style={stagger(2 + ri)}>
                    <td className="mono dim">{r.id}<div className="small">{r.series}</div></td>
                    {draft.columns.map((c) => {
                      const key = cellKey(r.id, c.key);
                      const present = c.key in r.values;
                      const review = present && needsReview(r, c.key) && !checked.has(key);
                      const v = r.values[c.key];
                      return (
                        <td
                          key={c.key}
                          className={"mono cell" + (review ? " review" : "") + (checked.has(key) ? " fixed" : "")}
                          onClick={() => present && !s.shadow && setEditing(key)}
                        >
                          {editing === key ? (
                            <input
                              autoFocus
                              defaultValue={v ?? ""}
                              inputMode="decimal"
                              onBlur={(e) => { commit(key, e.target.value); setEditing(null); }}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") { commit(key, e.currentTarget.value); setEditing(null); }
                                if (e.key === "Escape") setEditing(null);
                                if (e.key === "Tab") { e.preventDefault(); commit(key, e.currentTarget.value); moveToNextPending(key); }
                              }}
                            />
                          ) : present ? (v ?? <span className="q">?</span>) : <span className="dim">—</span>}
                          {review && r.confidence?.[c.key] !== undefined && (
                            <span className="conf mono">{Math.round(r.confidence[c.key] * 100)}%</span>
                          )}
                        </td>
                      );
                    })}
                    <td>{minConf !== null && <span className="meter"><i style={{ width: `${minConf * 100}%` }} /></span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="empty dim">{s.busy ?? "还没有识别结果"}</div>
        )}
        <Anchor className="small" src={anchor} caption="OBJ. 02 · VERNIER CALIPER · 读数：把刻度变成数字" />
        <div className="actions end">
          {draft && (
            <span className="mono dim small">
              {draft.rows.length} 行 · {pending.length ? `${pending.length} 处待确认` : "全部已过目"}
            </span>
          )}
          <button className="btn primary sheen" disabled={!draft || !!s.busy} onClick={confirm}>
            {pending.length ? "仍有待确认，照此确认 →" : "确认数据 →"}
          </button>
        </div>
      </aside>
    </div>
  );
}
