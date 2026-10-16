# 版本管理规范

## Worktree

**目的**：多个 agent 会话可能同时开发，每个会话必须在自己的 worktree 里工作，避免同时修改同一份工作目录。

- **一个会话一个 worktree，一个 worktree 一个分支。** 不在别的会话正在使用的 worktree 里改文件。
- **主工作目录固定在 `main` 分支**，只用来同步、合并和打标签，不在里面直接开发。
- worktree 统一放在仓库根目录的 `.worktrees/` 下（已加入 `.gitignore`），目录名为分支名中的 `/` 换成 `-`。

创建（在主工作目录执行）：

```bash
git worktree add .worktrees/feat-m2-axis-calibration -b feat/m2-axis-calibration main
```

合并后清理：

```bash
git worktree remove .worktrees/feat-m2-axis-calibration
git branch -d feat/m2-axis-calibration
```

注意：

- `.env` 等未纳入版本管理的文件不会出现在新 worktree 里，需要时自行复制。
- 两个会话的任务要改同一个模块时，不要并行开发，等前一个合并后再开下一个。
- 会话结束但工作没做完时，保留 worktree，并在交接时说明它的位置和进度。

## 分支

- `main`：任何时候都能跑通当前已完成的演示流程。不直接在 `main` 上提交代码。
- 功能分支：`feat/<模块>-<简述>`，如 `feat/m2-axis-calibration`。
- 修复分支：`fix/<模块>-<简述>`。
- 文档分支：`docs/<简述>`。
- 分支尽量短，完成一个可验证的功能点就合并回 `main`。
- 合并流程：在自己的 worktree 里 `git rebase main` 并确认能跑通，再到主工作目录执行 `git merge --no-ff <分支名>`。
- 每个模块只由负责人修改（负责人见 [architecture.md](architecture.md#模块)）。需要改别人的模块时，先和负责人沟通。

## 提交信息

格式：`<类型>(<范围>): <描述>`，描述用中文，说清楚做了什么。

| 类型 | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修复问题 |
| `refactor` | 不改变行为的重构 |
| `docs` | 只改文档 |
| `test` | 测试 |
| `chore` | 构建、依赖、配置等杂项 |

范围用模块编号（`m1`～`m8`），涉及契约时用 `contracts`，跨多个模块时可以省略。例如：

```
feat(m2): 支持对数坐标轴的像素换算
fix(m4): 修正摄氏度换算开尔文时的精度丢失
docs(contracts): Finding 增加 simulation 字段
```

改动影响了文档中的内容时，代码和文档放在同一次提交里。

## 契约版本

[contracts.md](contracts.md) 的版本号格式为 `主版本.次版本.修订号`：

| 改动 | 升哪一位 | 例子 |
|---|---|---|
| 不兼容：删字段、改字段名或类型、改单位 | 主版本 | `Dataset.rows[].values` 改成数组 |
| 兼容：新增可选字段、新增枚举值 | 次版本 | Finding 新增 `confidence` |
| 只改说明文字或示例 | 修订号 | 修正示例里的数值 |

流程：

1. 先在 `docs/` 分支修改 contracts.md 并升版本号，单独提交。
2. 通知所有读取或输出该结构的模块负责人。
3. 合并后，各模块再修改代码，并更新输出数据中的 `schema_version`。

## 标签

在里程碑完成时，在 `main` 上打标签：

| 标签 | 里程碑 |
|---|---|
| `v0.1` | M4 用手动录入的数据跑通计算和出图 |
| `v0.2` | M1、M2 接入，从图片走到对比图 |
| `v0.3` | M5 接入，完整 Must 闭环跑通 |
| `v1.0` | 答辩版本，冻结后只修演示中的问题 |

## 不提交

- API Key、`.env` 等密钥文件
- 模型权重等大文件
- 用户上传的临时文件

演示用的示例数据和保底结果需要提交。
