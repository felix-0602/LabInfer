# 组织知识（实验模板库 wiki）设计

负责回答：可复用的实验知识怎么沉淀和复用。模板的构成、生命周期、贡献与实例化流程，以及它在 `templates` 表（[sql.md](sql.md)）里的口径。不回答：单次实验的数据结构（[contracts.md](contracts.md)），存储与事务细节（[sql.md](sql.md)）。

## 定位

对应产品赛道表里的「组织知识：实验上下文卡片」。一次实验的知识可复用的部分是**实验的骨架**：目的、模型、角色绑定、常数、三层参照、质控规则包。把这些存成模板，下次同类实验只需确认，不必重填。这是把「有经验的人的配置」变成组织资产的地方。

## 模板的构成

模板是**不含数据的 ExperimentContext**：

- `name`、`purpose`：讲清楚这个实验做什么、判定什么。
- `model` + `model_params`：用哪个分析模型（契约模型注册表的 id），以及模型常数（摩尔质量、定容/移取体积等）。
- `variables.columns`：角色绑定（role → 列 key），M4 按角色取数。
- `reference`：三层参照的预置（文献数据集绑定、CRM 真值、限值或理论参照）。
- `qc_rules`：质控规则包，每条挂条文出处。

模板**不含** `datasets`（我的数据每次实验都不同），实例化时置空等待 M1 绑定。

## 生命周期与状态

| 状态 | 含义 | 来源 |
|---|---|---|
| `演示` | 当前演示案例使用的模板，随版本管理 | 代码内置（`contexts.py` 的 `TEMPLATES`） |
| `规划` | 产品路线上的候选实验 | 代码内置 |
| `自定义` | 用户或团队沉淀的模板 | `POST /api/m3/templates` 写入模板库 |

内置模板是代码常量，随仓库版本管理；模板库（存储里的 `templates` 表）存自定义模板，`GET /api/m3/templates` 返回内置与库的合并列表。同一个 id 不允许同时出现在两处，冲突返回 409。

## API（contracts 0.6.0）

| 方法与路径 | 作用 |
|---|---|
| `GET /api/m3/templates` | 内置 + 模板库合并列表（id、名称、model、必需角色、公式、参照预览、状态） |
| `POST /api/m3/templates` | 沉淀一个自定义模板：校验 model 在注册表内、必需角色齐全，写入库，状态置 `自定义` |
| `POST /api/m3/contexts` | 从模板实例化：深拷贝模板，换新 id，`datasets.mine = null` |

## 实例化边界

模板只在 M3 被读取。实例化之后，M4、M5、M8 面对的是 ExperimentContext，与模板再无关联；改模板不影响已创建的上下文。模板不存数据、不存结论，那些属于单次实验（datasets、analyses、findings）。

## 当前内置模板

| id | 状态 | 说明 |
|---|---|---|
| `tpl_alkali_titration` | 演示 | HCl 标定与碱灰总碱度（GB/T 601-2016），见 [product.md](product.md#演示案例) |
| `tpl_iodine_clock` | 规划 | 碘钟反应动力学（Arrhenius），等曲线类参照接入后转演示候选 |
