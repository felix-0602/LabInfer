# SQL 存储设计

负责回答：数据落进关系库（SQLite）时的表结构、约束、事务与安全规则；JSON 与 SQLite 双后端的选择与切换。不回答：契约字段的含义（[contracts.md](contracts.md)），模板的业务规则（[wiki.md](wiki.md)）。

## 后端选择

| 后端 | 启用方式 | 用途 |
|---|---|---|
| JSON 文件（默认） | `LABINFER_STORAGE=json` 或不设 | 单用户演示，零依赖，原子写（tmp + `os.replace`） |
| SQLite | `LABINFER_STORAGE=sqlite` | 需要持久查询、事务与后续多人扩展时 |

两个后端实现同一个 `Store` 接口（`put_dataset`/`get_dataset`、`put_context`/`get_context`、`put_analysis`/`get_analysis`、`put_findings`/`get_findings`、`save_upload`、模板读写），路由层不感知后端。切换只改环境变量，数据不迁移（演示数据由 `scripts/seed_demo.py` 重新写入）。

SQLite 文件默认在 `server/data/labinfer.sqlite3`（WAL 模式）。演示缓存 `server/demo_cache/` 仍是文件，按图片 sha256 命名，与后端无关。

## 表结构

设计原则：**契约对象是开放结构（`derived`、`meta` 等字段随模型演进），全部列化会把契约拷进 DDL**。因此每张表把可查询的稳定维度提为列，完整对象存 `payload` JSON 列。改契约不动表。

```sql
CREATE TABLE IF NOT EXISTS datasets(
  id             TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  source         TEXT NOT NULL,          -- my_experiment | literature
  title          TEXT,
  payload        TEXT NOT NULL,          -- 完整 Dataset JSON
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS contexts(
  id              TEXT PRIMARY KEY,
  schema_version  TEXT NOT NULL,
  name            TEXT NOT NULL,
  model           TEXT NOT NULL,
  mine_dataset_id TEXT,                  -- datasets.id，未绑定为 NULL
  payload         TEXT NOT NULL,
  updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS analyses(
  context_id      TEXT PRIMARY KEY,      -- 一个上下文一份最新分析
  schema_version  TEXT NOT NULL,
  model           TEXT NOT NULL,
  payload         TEXT NOT NULL,
  updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS findings(
  context_id  TEXT NOT NULL,
  idx         INTEGER NOT NULL,          -- 结论在列表中的顺序
  fid         TEXT NOT NULL,
  ftype       TEXT NOT NULL,             -- pattern | conclusion | anomaly | suggestion
  text        TEXT NOT NULL,
  payload     TEXT NOT NULL,             -- 单条 Finding JSON（含 evidence）
  PRIMARY KEY(context_id, idx)
);

CREATE TABLE IF NOT EXISTS uploads(
  id         TEXT PRIMARY KEY,
  path       TEXT NOT NULL UNIQUE,
  sha256     TEXT,
  bytes      INTEGER,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS templates(    -- 组织知识：实验模板库，业务规则见 docs/wiki.md
  id             TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  name           TEXT NOT NULL,
  model          TEXT NOT NULL,
  status         TEXT NOT NULL,          -- 演示 | 规划 | 自定义
  payload        TEXT NOT NULL,
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
```

对象与表的对应：

| 契约对象 | 表 | 主键 | 说明 |
|---|---|---|---|
| Dataset | `datasets` | `id` | `source`、`title` 提列供筛选 |
| ExperimentContext | `contexts` | `id` | `model`、`mine_dataset_id` 提列供关联查询 |
| AnalysisResult | `analyses` | `context_id` | 覆盖写，只留最新 |
| Finding[] | `findings` | `(context_id, idx)` | 整表按 context 替换，行存单条 |
| 上传文件 | `uploads` | `id` | 文件本体仍在 `uploads/` 目录，表做索引 |
| 实验模板 | `templates` | `id` | wiki 层的唯一持久化落点 |

## 读写与事务

- 写操作用 `INSERT … ON CONFLICT DO UPDATE`（upsert），`updated_at` 由 SQL 侧刷新。
- `put_findings` 在一个事务里先 `DELETE WHERE context_id=?` 再批量 `INSERT`，保证整表替换的原子性。
- 连接以 `threading.Lock` 串行化（FastAPI 同步路由跑在线程池），WAL 模式允许读写并发。
- 读操作直接 `SELECT payload` 后 `json.loads`，查不到返回 `None`，与 JSON 后端语义一致。

## 安全规则（硬约束）

- **所有携带外部输入的 SQL 一律参数绑定（`?` 占位）**，禁止拼接、`format`、f-string 组装。id、context_id、payload 全部走绑定参数。
- 表名、列名只出现模块内的常量 DDL 里，不接收任何外部输入。
- 唯一例外是 `PRAGMA user_version = <int>`（PRAGMA 不支持绑定）。操作数是写死的代数字面量，模块内用断言与常量 `SCHEMA_VERSION` 对齐（常量升代而字面量未跟时启动即失败），非外部输入。

## 迁移

用 `PRAGMA user_version` 记录 schema 代数。启动时建表（`CREATE TABLE IF NOT EXISTS`），若代数落后则按 `MIGRATIONS` 列表前向执行。当前代数 1，无历史迁移。新增列走「新代数 + `ALTER TABLE … ADD COLUMN` + 默认值」。
