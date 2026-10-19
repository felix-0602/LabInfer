"""SQLite 存储后端。与 JSON 后端（storage.Store）同接口，路由层不感知后端。

安全硬约束：每条 SQL 都是单条字符串字面量，值一律走参数绑定（? 占位）；
不拼接、不 format、不用 f-string、不用相邻字符串隐式拼接组装 SQL。
表结构见 docs/sql.md。
"""

import hashlib
import json
import sqlite3
import threading
import uuid
from pathlib import Path

from .config import CONTRACT_VERSION, DATA_DIR
from .storage import new_id

SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS datasets(
  id             TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  source         TEXT NOT NULL,
  title          TEXT,
  payload        TEXT NOT NULL,
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS contexts(
  id              TEXT PRIMARY KEY,
  schema_version  TEXT NOT NULL,
  name            TEXT NOT NULL,
  model           TEXT NOT NULL,
  mine_dataset_id TEXT,
  payload         TEXT NOT NULL,
  updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS analyses(
  context_id      TEXT PRIMARY KEY,
  schema_version  TEXT NOT NULL,
  model           TEXT NOT NULL,
  payload         TEXT NOT NULL,
  updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS findings(
  context_id  TEXT NOT NULL,
  idx         INTEGER NOT NULL,
  fid         TEXT NOT NULL,
  ftype       TEXT NOT NULL,
  text        TEXT NOT NULL,
  payload     TEXT NOT NULL,
  PRIMARY KEY(context_id, idx)
);
CREATE TABLE IF NOT EXISTS uploads(
  id         TEXT PRIMARY KEY,
  path       TEXT NOT NULL UNIQUE,
  sha256     TEXT,
  bytes      INTEGER,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS templates(
  id             TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  name           TEXT NOT NULL,
  model          TEXT NOT NULL,
  status         TEXT NOT NULL,
  payload        TEXT NOT NULL,
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


class SqlStore:
    """单用户场景：threading.Lock 串行化写，WAL 允许读写并发。"""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else DATA_DIR / "labinfer.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock, self._conn:
            self._conn.executescript(_DDL)
            version = self._conn.execute("PRAGMA user_version").fetchone()[0]
            if version < SCHEMA_VERSION:
                # PRAGMA 不支持参数绑定（docs/sql.md 安全规则的唯一例外）；
                # 操作数是写死的代数字面量，断言与 SCHEMA_VERSION 对齐，
                # 常量升代而字面量未跟时启动即失败。维持单条字符串字面量，不引入 format/f-string。
                assert SCHEMA_VERSION == 1
                self._conn.execute("PRAGMA user_version = 1")

    def _ensure_id(self, data: dict, prefix: str) -> dict:
        data.setdefault("id", new_id(prefix))
        return data

    @property
    def root(self) -> Path:
        """与 JSON 后端对齐的数据根目录（库文件所在目录）。"""
        return self.path.parent

    # ---- datasets ----

    def put_dataset(self, ds: dict) -> dict:
        self._ensure_id(ds, "ds")
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO datasets(id, schema_version, source, title, payload) VALUES(?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET schema_version=excluded.schema_version, source=excluded.source, title=excluded.title, payload=excluded.payload, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
                (ds["id"], ds.get("schema_version", ""), ds.get("source", ""),
                 ds.get("meta", {}).get("title"), _dumps(ds)))
        return ds

    def get_dataset(self, id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT payload FROM datasets WHERE id = ?", (id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    # ---- contexts ----

    def put_context(self, ctx: dict) -> dict:
        self._ensure_id(ctx, "ctx")
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO contexts(id, schema_version, name, model, mine_dataset_id, payload) VALUES(?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET schema_version=excluded.schema_version, name=excluded.name, model=excluded.model, mine_dataset_id=excluded.mine_dataset_id, payload=excluded.payload, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
                (ctx["id"], ctx.get("schema_version", CONTRACT_VERSION), ctx.get("name", ""),
                 ctx.get("model", ""), ctx.get("datasets", {}).get("mine"), _dumps(ctx)))
        return ctx

    def get_context(self, id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT payload FROM contexts WHERE id = ?", (id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    # ---- analyses ----

    def put_analysis(self, ctx_id: str, result: dict) -> dict:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO analyses(context_id, schema_version, model, payload) VALUES(?, ?, ?, ?) ON CONFLICT(context_id) DO UPDATE SET schema_version=excluded.schema_version, model=excluded.model, payload=excluded.payload, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
                (ctx_id, result.get("schema_version", ""), result.get("model", ""),
                 _dumps(result)))
        return result

    def get_analysis(self, ctx_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT payload FROM analyses WHERE context_id = ?", (ctx_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    # ---- findings ----

    def put_findings(self, ctx_id: str, findings: list[dict]) -> list[dict]:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM findings WHERE context_id = ?", (ctx_id,))
            self._conn.executemany(
                "INSERT INTO findings(context_id, idx, fid, ftype, text, payload) VALUES(?, ?, ?, ?, ?, ?)",
                [(ctx_id, i, f.get("id", f"f{i}"), f.get("type", ""), f.get("text", ""),
                  _dumps(f)) for i, f in enumerate(findings)])
        return findings

    def get_findings(self, ctx_id: str) -> list[dict] | None:
        rows = self._conn.execute(
            "SELECT payload FROM findings WHERE context_id = ? ORDER BY idx",
            (ctx_id,)).fetchall()
        if not rows:
            return None
        return [json.loads(r["payload"]) for r in rows]

    # ---- uploads（文件本体仍在目录，表做索引） ----

    def save_upload(self, data: bytes, suffix: str = "") -> Path:
        name = uuid.uuid4().hex + suffix
        p = self.path.parent / "uploads" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO uploads(id, path, sha256, bytes) VALUES(?, ?, ?, ?)",
                (name, str(p), hashlib.sha256(data).hexdigest(), len(data)))
        return p

    # ---- templates（组织知识层，业务规则见 docs/wiki.md） ----

    def put_template(self, tpl: dict) -> dict:
        self._ensure_id(tpl, "tpl")
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO templates(id, schema_version, name, model, status, payload) VALUES(?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET schema_version=excluded.schema_version, name=excluded.name, model=excluded.model, status=excluded.status, payload=excluded.payload, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
                (tpl["id"], tpl.get("schema_version", CONTRACT_VERSION), tpl.get("name", ""),
                 tpl.get("model", ""), tpl.get("status", "自定义"), _dumps(tpl)))
        return tpl

    def get_template(self, id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT payload FROM templates WHERE id = ?", (id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_templates(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT payload FROM templates ORDER BY updated_at, id").fetchall()
        return [json.loads(r["payload"]) for r in rows]
