# 🎾 Tennis-Scheduler: 网球赛事智能编排引擎

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3-38B2AC?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Eel](https://img.shields.io/badge/Eel-Python-4B8BBE)](https://github.com/python-eel/Eel)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/PhSeCl/Tennis-Scheduler/pulls)
[![CI](https://github.com/PhSeCl/Tennis-Scheduler/actions/workflows/ci.yml/badge.svg)](https://github.com/PhSeCl/Tennis-Scheduler/actions)

解决多项目网球比赛兼项冲突、轮空不对称、连场休息等痛点的全自动排程工具。

> 📣 面向两类人：
>
> - **赛事组织者 / 裁判长**：无需读代码，只需要准备数据并运行命令。
> - **算法工程师**：可扩展规则、替换搜索策略、快速二次开发。

## ✨ 核心特性 (Key Features)

- **全域防兼项**：同一名选手绝不会在同一时间出现在两片场地上。
- **轮空自适应**：支持不对称签表与轮空晋级，自动消除无效比赛。
- **多项目混合排表**：单打、双打、混双可同时排，系统自动统一兼项约束。
- **快速推演**：束搜索剪枝，快速生成全局最优排程。
- **现代化桌面 GUI**：提供全可视化的选手管理、完美二叉树签表预览、排表参数控制台以及中英双语切换，极大降低使用门槛。

## ✅ 运行条件 (Requirements)

- Python 3.8+
- Node.js 16+
- Python 依赖：eel（见 requirements.txt）

## 🖥️ 图形界面使用指南 (GUI Quick Start)

项目已升级为本地桌面应用，新增 frontend/ 与 app.py 作为 GUI 入口。

### Step 1: 安装依赖

- 前端：

```bash
cd frontend
npm install
```

- 后端：

```bash
pip install -r requirements.txt
# 或
pip install eel
```

### Step 2: 开发模式运行

- 终端 A（前端）：

```bash
cd frontend
npm run dev
```

- 终端 B（后端）：

```bash
python app.py --dev
```

浏览器访问通常为：http://localhost:5173

### Step 3: 生产模式运行（本地桌面）

- 先构建前端：

```bash
cd frontend
npm run build
```

- 再启动 Eel：

```bash
cd ..
python app.py
```

## 💻 命令行使用指南 (CLI Quick Start)

### A. 准备选手数据 (players.json)

这是一个字典：**Key 是选手姓名**，**Value 包含是否驻地**。

```json
{
  "张三": {"is_staying_at_venue": true},
  "李四": {"is_staying_at_venue": false},
  "王五": {"is_staying_at_venue": true}
}
```

> `is_staying_at_venue` 用来控制“早场惩罚”，不住在场地的选手尽量不会被排在第一场。
> 项目提供了脱敏样例可参考：`data/sample_players.json`。

### A-1. 报名数据校验 (Data Gatekeeper)

在排表前建议先做一次逻辑校验，提前发现搭档不匹配、性别不符、单双打冲突等问题。

```bash
python tools/check_players.py \
  --players data/players.json \
  --report data/results.txt
```

> 校验未通过会返回非零状态码，并将完整错误列表写入报告文件。

### B. 准备抽签数据 (例如 men_singles.json)

抽签文件是一个**扁平数组**：**相邻两个元素表示第一轮的一场对阵**。

**单打示例**（注意轮空写法必须是中文字符串 `"轮空"`）：

```json
[
  {"player": "张三", "round": 0},
  {"player": "李四", "round": 0},
  {"player": "王五", "round": 0},
  {"player": "轮空", "round": 0}
]
```

**双打示例**（把 `player` 换成 `players` 数组即可）：

```json
[
  {"players": ["张三", "李四"], "round": 0},
  {"players": ["王五", "赵六"], "round": 0}
]
```

> 引擎会自动识别 `player` / `players`，无需区分单打双打接口。
> 项目提供了脱敏样例可参考：`data/matches/sample_*.json`。

### C. 一键运行 (Run the Engine)

```bash
python src/cli.py \
  --players data/players.json \
  --ms data/matches/men_singles.json \
  --xd data/matches/mixed_doubles.json \
  --courts 6 \
  --w1 10.0 \
  --w2 7.0 \
  --w3 2.5 \
  --beam-width 10
```

**惩罚权重说明（可按需求调整）：**

- `--w1`：早场惩罚权重（对应 `EarlyStartRule`）
- `--w2`：连场惩罚权重（对应 `BackToBackRule`）
- `--w3`：空场惩罚权重（对应 `EmptyCourtRule`）

权重越大，排程越倾向于避免对应情况。若希望快速生成结果可适度降低权重，若希望严格约束可提高权重。

**参数说明：**

| 参数 | 含义 | 是否必填 |
| --- | --- | --- |
| `--players` | 选手数据路径 | 必填 |
| `--ms, --ws, --md, --wd, --xd` | 男女单双混抽签路径 | 选填 |
| `--courts` | 可用场地数量 | 选填 |
| `--w1` | 早场惩罚权重 | 选填 |
| `--w2` | 连场惩罚权重 | 选填 |
| `--w3` | 空场惩罚权重 | 选填 |
| `--beam-width` | 搜索宽度（10-30 推荐） | 选填 |

### D. 查看赛程表

结果会保存在：`results/schedule_result_*.txt`

示例输出：

```text
==================================================
网球赛事极速智能编排结果
总惩罚分: 34.0 | 预计完赛总时间片: 5
==================================================

[时间片 1]
  - 场地 1: [男单 1/8决赛] 张三 vs 李四 (场次ID: 1001)
  - 场地 2: [混双 1/8决赛] 王五/赵六 vs 孙七/周八 (场次ID: 5001)

[时间片 2]
  - 场地 1: [男单 1/8决赛] 王五 vs 轮空 (场次ID: 1002)
```

## 🧪 测试要求 (Testing)

项目单元测试使用 `pytest`，覆盖率统计使用 `pytest-cov`。

```bash
python -m pip install pytest pytest-cov
pytest -q --cov=src --cov=tools --cov-report=term-missing --cov-fail-under=80
```

## 🧭 数据格式约束 (Data Constraints)

- 抽签数组长度必须是偶数（两两成对）。
- 首轮场次数必须是 $2^n$（例如 1、2、4、8、16）。
- 轮空必须写成中文字符串 `"轮空"`。
- 抽签项必须包含 `player` 或 `players` 字段。
- 抽签中的选手姓名若不在 `players.json` 中，会被视为未知（不参与早场惩罚统计）。

## 🧠 算法核心原理 (Algorithm Principles)

### 1) DAG 图论降维

签表本质是一棵完美二叉树，但我们并不知道每场比赛的胜者是谁。
通过构建有向无环图（DAG），将“依赖关系”编码为边约束，从而在未知胜者的情况下依然可以进行时间片调度。

### 2) 全域集合交集运算

每场比赛维护 `potential_players` 集合。
只要任意两场比赛集合有交集，就判定为**兼项冲突**并阻止它们排在同一时间片。

### 3) 马尔可夫状态隔离与束搜索剪枝

每个时间片是一个状态，状态通过深拷贝进行隔离。
使用 Beam Search 在组合爆炸的情况下进行剪枝：

> - 优先排满场地（减少空场）
> - 排不满则递减组合数量
> - 通过确定性排序避免随机震荡

## 🧩 二次开发指南 (Extension Guide)

当前架构支持四类扩展点：模型、硬约束、搜索策略、生命周期 Hook。
下面给出典型的扩展示例与接入方式。

### 1) 规则扩展（软约束/惩罚规则）

`cost_evaluator.py` 基于规则接口，扩展惩罚规则非常简单。

示例：实现“同协会规避规则” `AvoidSameAssociationRule`。

```python
from cost_evaluator import MatchRule


class AvoidSameAssociationRule(MatchRule):
    def __init__(self, weight: float) -> None:
        self._weight = weight

    @property
    def name(self) -> str:
        return "同协会规避规则"

    @property
    def description(self) -> str:
        return "避免同协会选手出现在同一场次"

    @property
    def weight(self) -> float:
        return self._weight

    def evaluate(self, match, t, scheduled_matches) -> float:
        # 在此实现自定义逻辑
        return 0.0
```

在 `cli.py` 中注册：

```python
r_custom = AvoidSameAssociationRule(weight=3.0)
evaluator = TennisTournamentEvaluator(
    match_rules=[r1, r2, r_custom],
    global_rules=[r3],
)
```

> 核心搜索引擎完全不需要修改，规则即插即用。

### 2) 硬约束扩展（必须满足的约束）

硬约束通过 `ScheduleConstraint` 注入，调度引擎只调用 `is_valid()`。

```python
from constraints import ScheduleConstraint


class NoSameAssociationConstraint(ScheduleConstraint):
  def is_valid(self, combo, state) -> bool:
    # 在此实现自定义“必须满足”的逻辑
    return True
```

在 `cli.py` 中注入：

```python
constraints = [NoPlayerOverlapConstraint(), NoSameAssociationConstraint()]
best_state = strategy.schedule(
  initial_nodes=all_nodes,
  config=config,
  evaluator=evaluator,
  constraints=constraints,
)
```

### 3) 搜索策略扩展（Strategy Pattern）

新增调度算法时，只需继承 `SearchStrategy` 并实现 `schedule()`。

```python
from search_strategies import SearchStrategy


class GreedySearchStrategy(SearchStrategy):
  def schedule(self, initial_nodes, config, evaluator, constraints, hooks=None):
    # 在此实现自定义搜索流程
    raise NotImplementedError
```

切换策略：

```python
strategy = GreedySearchStrategy()
best_state = strategy.schedule(
  initial_nodes=all_nodes,
  config=config,
  evaluator=evaluator,
  constraints=[overlap_constraint],
)
```

### 4) 生命周期 Hook 扩展（插件机制）

Hook 用于在排程前后注入扩展逻辑，例如导出、通知、监控等。

```python
from hooks import SchedulerHook


class ExportExcelHook(SchedulerHook):
  def on_scheduling_start(self, initial_nodes, config) -> None:
    pass

  def on_scheduling_end(self, best_state) -> None:
    # 在此导出 Excel / 发送通知
    pass
```

接入：

```python
hooks = [ConsoleLoggingHook(), ExportExcelHook()]
best_state = strategy.schedule(
  initial_nodes=all_nodes,
  config=config,
  evaluator=evaluator,
  constraints=[overlap_constraint],
  hooks=hooks,
)
```

### 5) 数据模型扩展（Data Models）

项目统一使用 `SchedulerConfig`、`Player`、`MatchData` 承载数据。
你可以在不改动核心引擎的前提下新增字段并逐步接入。

## 🧪 常见问题 (Troubleshooting)

- 报错“未找到文件”：请检查传入路径是否正确、文件是否存在。
- 报错“格式解析失败”：JSON 语法错误（缺逗号、引号不成对等）。
- 报错“首轮场次数必须为 2 的幂”：抽签数组长度不满足 $2^n \times 2$ 的要求。
- 报错“同一签位两侧不能同时为轮空”：同一场比赛不能双方都是“轮空”。

## 🗂️ 项目结构 (Project Layout)

```text
Tennis-Scheduler/
├─ .github/workflows/     # CI 配置
├─ data/                 # 示例数据（含 sample_*.json）
├─ results/              # 可选输出目录（若存在）
├─ tests/                # 单元测试
├─ tools/
│  └─ check_players.py    # 报名数据校验工具
└─ src/
  ├─ cli.py               # 命令行入口
  ├─ constraints.py       # 硬约束接口与实现
  ├─ cost_evaluator.py    # 规则与惩罚评估
  ├─ dag_builder.py       # 签表 -> DAG
  ├─ data_parser.py       # 抽签数据解析适配层
  ├─ hooks.py             # 生命周期 Hook 机制
  ├─ models.py            # 数据模型层
  ├─ scheduler_engine.py  # 调度核心状态模型
  └─ search_strategies.py # 搜索策略（BeamSearch 等）
```

---

## ⚠️ 免责声明 (Disclaimer)

- 本项目为个人开发学习用途，仅供学习与交流使用。
- 禁止用于任何商业用途或商业化场景。
- 结果仅供参考，开发者不对赛程结果的正确性或后果承担责任。
- 欢迎提交 Issue / PR，共同改进。
