# 🎾 Tennis-Scheduler: 极速网球赛事智能编排引擎

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)

基于**图论拓扑降维 (Topological Reduction)**与**马尔可夫束搜索 (Beam Search)**构建的工业级网球赛事调度引擎。
可在毫秒级内解决包含单打、双打、混双等多项目混合编排的复杂业务场景，完美规避跨项目兼项冲突，生成全局最优的赛事排程表。

## ✨ 核心特性

- **拓扑数学降维**：自动将包含“轮空（Bye）”的不对称签表坍缩为最小状态的有向无环图（DAG），剥离实体追踪，完美解决“不知胜者是谁”条件下的连场判定。
- **全域防兼项（Cross-Event Overlap Prevention）**：底层引入基于潜在选手的集合交集运算（Set Intersection），不论混合安排多少个项目，**绝对不会让同一名选手在同一时间出现在两片场地上**。
- **动态规则引擎（Rule Engine）**：基于策略模式设计，自带三大核心约束（早场驻地限制、连场休息限制、赛程紧凑度限制）。只需新增一个 Rule 类即可无缝叠加新规则，底层算法核心 **0 代码修改**。
- **亚秒级推演**：利用克隆状态机和确定性优先队列进行 Beam Search 剪枝，将原本指数级 $O(2^n)$ 的组合爆炸问题降维至多项式时间，1秒内输出全局最优排表。

## 📂 架构概览 (Domain-Driven Design)

- `cli.py`：命令行统筹入口与优雅降级异常处理。
- `dag_builder.py`：数据防腐层，将扁平的 JSON 签表转换为严谨的 DAG 数学图论模型。
- `cost_evaluator.py`：软约束惩罚模块，提供高度可扩展的策略插件注册表。
- `scheduler_engine.py`：核心引擎层，负责时序状态机的裂变与启发式剪枝搜索。

## 🚀 极速上手

### 1. 准备数据

按照扁平格式准备选手字典（`players.json`）与抽签结果（如 `men_singles.json`）。系统天然支持单双打结构自适应。

### 2. 运行调度引擎

提供灵活的命令行参数，随时调整场地资源与业务权重：

```bash
python src/cli.py \
  --players data/players.json \
  --ms data/matchs/men_singles.json \
  --xd data/matchs/mixed_doubles.json \
  --courts 6 \
  --w1 10.0 \
  --w2 7.0 \
  --beam-width 10
