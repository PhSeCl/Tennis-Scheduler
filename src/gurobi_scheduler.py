from __future__ import annotations

"""基于 Gurobi 的网球赛事调度策略实现。"""

from copy import deepcopy
from typing import Any

from constraints import NoPlayerOverlapConstraint, ScheduleConstraint
from cost_evaluator import BackToBackRule, CostEvaluator, EarlyStartRule, EmptyCourtRule
from hooks import SchedulerHook
from models import SchedulerConfig
from scheduler_engine import MatchNode, ScheduleState
from search_strategies import SearchStrategy

IMPORT_ERROR: Exception | None = None

try:
    import gurobipy as gp
    from gurobipy import GRB
except Exception as exc:  # pragma: no cover - 依赖缺失时走这里
    gp = None  # type: ignore[assignment]
    GRB = None  # type: ignore[assignment]
    IMPORT_ERROR = exc


def build_uv_install_hint() -> str:
    return (
        "未检测到可用的 gurobipy 环境。\n"
        "建议优先使用 uv：\n"
        "1) 临时运行：uv run --with gurobipy==12.0.1 python -X utf8 .\\src\\cli.py ... --solver gurobi\n"
        "2) 或将依赖加入项目环境：uv add gurobipy\n"
        "3) 同时确认 Gurobi 许可证可用，且版本与许可证兼容"
    )


def get_status_name(status_code: int) -> str:
    if GRB is None:
        return f"UNKNOWN({status_code})"

    status_map = {
        GRB.LOADED: "LOADED（已加载，尚未求解）",
        GRB.OPTIMAL: "OPTIMAL（最优）",
        GRB.INFEASIBLE: "INFEASIBLE（无可行解）",
        GRB.INF_OR_UNBD: "INF_OR_UNBD（无可行或无界）",
        GRB.UNBOUNDED: "UNBOUNDED（无界）",
        GRB.CUTOFF: "CUTOFF（被截断）",
        GRB.ITERATION_LIMIT: "ITERATION_LIMIT（达到迭代上限）",
        GRB.NODE_LIMIT: "NODE_LIMIT（达到节点上限）",
        GRB.TIME_LIMIT: "TIME_LIMIT（达到时间上限）",
        GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT（达到解数量上限）",
        GRB.INTERRUPTED: "INTERRUPTED（求解被中断）",
        GRB.NUMERIC: "NUMERIC（数值问题）",
        GRB.SUBOPTIMAL: "SUBOPTIMAL（得到可行但未证最优）",
    }
    return status_map.get(status_code, f"UNKNOWN({status_code})")


def safe_get_model_attr(model: Any, attr_name: str) -> float | None:
    try:
        return float(getattr(model, attr_name))
    except Exception:
        return None


def build_precedence_arcs(initial_nodes: dict[int, MatchNode]) -> list[tuple[int, int]]:
    arcs: list[tuple[int, int]] = []
    for node in initial_nodes.values():
        if node.left_prev_match is not None:
            arcs.append((node.left_prev_match.match_id, node.match_id))
        if node.right_prev_match is not None:
            arcs.append((node.right_prev_match.match_id, node.match_id))
    return arcs


def build_overlap_pairs(initial_nodes: dict[int, MatchNode]) -> list[tuple[int, int]]:
    match_ids = sorted(initial_nodes)
    pairs: list[tuple[int, int]] = []
    for i, match_id_a in enumerate(match_ids):
        players_a = initial_nodes[match_id_a].potential_players
        for match_id_b in match_ids[i + 1 :]:
            players_b = initial_nodes[match_id_b].potential_players
            if players_a & players_b:
                pairs.append((match_id_a, match_id_b))
    return pairs


def extract_supported_weights(
    evaluator: CostEvaluator,
    config: SchedulerConfig,
) -> tuple[float, float, float]:
    # 默认回退到 config，兼容未来可能出现的轻量 evaluator
    w1 = config.w1
    w2 = config.w2
    w3 = config.w3

    match_rules = getattr(evaluator, "match_rules", None)
    global_rules = getattr(evaluator, "global_rules", None)

    if match_rules is not None:
        w1 = 0.0
        w2 = 0.0
        for rule in match_rules:
            if isinstance(rule, EarlyStartRule):
                w1 = float(rule.weight)
            elif isinstance(rule, BackToBackRule):
                w2 = float(rule.weight)
            else:
                raise NotImplementedError(
                    f"Gurobi 调度器暂不支持规则: {rule.__class__.__name__}"
                )

    if global_rules is not None:
        w3 = 0.0
        for rule in global_rules:
            if isinstance(rule, EmptyCourtRule):
                w3 = float(rule.weight)
            else:
                raise NotImplementedError(
                    f"Gurobi 调度器暂不支持全局规则: {rule.__class__.__name__}"
                )

    return w1, w2, w3


class GurobiSearchStrategy(SearchStrategy):
    """使用时间索引 0-1 MIP 的 Gurobi 调度策略。"""

    def __init__(
        self,
        time_limit: float | None = None,
        mip_gap: float | None = 0.0,
        log_to_console: bool = False,
    ) -> None:
        self.time_limit = time_limit
        self.mip_gap = mip_gap
        self.log_to_console = log_to_console
        self.last_solve_info: dict[str, object] = {"solver": "gurobi"}

    def _ensure_gurobi_available(self) -> None:
        if gp is None or GRB is None:
            message = [build_uv_install_hint()]
            if IMPORT_ERROR is not None:
                message.append(f"底层导入错误: {IMPORT_ERROR}")
            raise RuntimeError("\n".join(message))

    def _create_env(self) -> Any:
        self._ensure_gurobi_available()
        try:
            env = gp.Env(empty=True)
            env.setParam("OutputFlag", 1 if self.log_to_console else 0)
            env.start()
            return env
        except gp.GurobiError as exc:
            raise RuntimeError(
                "Gurobi 环境启动失败。请检查许可证是否可用，或确认 gurobipy 与 Gurobi 版本匹配。"
                f"\n原始错误: {exc}"
            ) from exc

    def schedule(
        self,
        initial_nodes: dict[int, MatchNode],
        config: SchedulerConfig,
        evaluator: CostEvaluator,
        constraints: list[ScheduleConstraint] | None,
        hooks: list[SchedulerHook] | None = None,
    ) -> ScheduleState:
        if hooks is None:
            hooks = []
        if not constraints:
            constraints = []

        unsupported_constraints = [
            constraint
            for constraint in constraints
            if not isinstance(constraint, NoPlayerOverlapConstraint)
        ]
        if unsupported_constraints:
            names = ", ".join(type(item).__name__ for item in unsupported_constraints)
            raise NotImplementedError(f"Gurobi 调度器暂不支持这些硬约束: {names}")

        for hook in hooks:
            hook.on_scheduling_start(initial_nodes, config)

        total_matches = len(initial_nodes)
        if total_matches == 0:
            empty_state = ScheduleState(
                t=1,
                all_nodes=deepcopy(initial_nodes),
                ready_match_ids=set(),
                scheduled_count=0,
                cost=0.0,
            )
            self.last_solve_info = {
                "solver": "gurobi",
                "status_name": "OPTIMAL（空问题）",
                "runtime_seconds": 0.0,
                "objective_value": 0.0,
                "total_slots": 0,
            }
            for hook in hooks:
                hook.on_scheduling_end(empty_state)
            return empty_state

        w1, w2, w3 = extract_supported_weights(evaluator=evaluator, config=config)
        overlap_constraint_enabled = any(
            isinstance(constraint, NoPlayerOverlapConstraint)
            for constraint in constraints
        )

        match_ids = sorted(initial_nodes)
        slots = list(range(1, total_matches + 1))
        precedence_arcs = build_precedence_arcs(initial_nodes)
        overlap_pairs = build_overlap_pairs(initial_nodes)
        ordered_overlap_pairs = [
            (left, right) for left, right in overlap_pairs
        ] + [
            (right, left) for left, right in overlap_pairs
        ]

        env = None
        model = None
        try:
            env = self._create_env()
            model = gp.Model("tennis_scheduler_gurobi", env=env)

            if self.time_limit is not None and self.time_limit > 0:
                model.Params.TimeLimit = self.time_limit
            if self.mip_gap is not None and self.mip_gap >= 0:
                model.Params.MIPGap = self.mip_gap

            assign = model.addVars(match_ids, slots, vtype=GRB.BINARY, name="assign")
            slot_used = model.addVars(slots, vtype=GRB.BINARY, name="slot_used")
            idle_slack = model.addVars(slots, lb=0.0, vtype=GRB.CONTINUOUS, name="idle_slack")
            back_to_back = model.addVars(
                [(left, right, slot) for left, right in ordered_overlap_pairs for slot in slots[:-1]],
                vtype=GRB.BINARY,
                name="back_to_back",
            )

            start_expr = {
                match_id: gp.quicksum(slot * assign[match_id, slot] for slot in slots)
                for match_id in match_ids
            }

            model.addConstrs(
                (
                    gp.quicksum(assign[match_id, slot] for slot in slots) == 1
                    for match_id in match_ids
                ),
                name="assign_once",
            )

            model.addConstrs(
                (
                    gp.quicksum(assign[match_id, slot] for match_id in match_ids)
                    <= config.courts * slot_used[slot]
                    for slot in slots
                ),
                name="court_capacity",
            )
            model.addConstrs(
                (
                    gp.quicksum(assign[match_id, slot] for match_id in match_ids)
                    >= slot_used[slot]
                    for slot in slots
                ),
                name="slot_non_empty",
            )
            model.addConstrs(
                (
                    slot_used[slot] >= slot_used[slot + 1]
                    for slot in slots[:-1]
                ),
                name="slot_prefix",
            )

            model.addConstrs(
                (
                    start_expr[next_match] >= start_expr[prev_match] + 1
                    for prev_match, next_match in precedence_arcs
                ),
                name="precedence",
            )

            if overlap_constraint_enabled:
                model.addConstrs(
                    (
                        assign[left, slot] + assign[right, slot] <= 1
                        for left, right in overlap_pairs
                        for slot in slots
                    ),
                    name="player_overlap",
                )

            model.addConstrs(
                (
                    back_to_back[left, right, slot] <= assign[left, slot]
                    for left, right in ordered_overlap_pairs
                    for slot in slots[:-1]
                ),
                name="back_to_back_left",
            )
            model.addConstrs(
                (
                    back_to_back[left, right, slot] <= assign[right, slot + 1]
                    for left, right in ordered_overlap_pairs
                    for slot in slots[:-1]
                ),
                name="back_to_back_right",
            )
            model.addConstrs(
                (
                    back_to_back[left, right, slot]
                    >= assign[left, slot] + assign[right, slot + 1] - 1
                    for left, right in ordered_overlap_pairs
                    for slot in slots[:-1]
                ),
                name="back_to_back_link",
            )

            big_m = total_matches * max(config.courts, 1)
            for slot in slots:
                cumulative_scheduled = gp.quicksum(
                    assign[match_id, previous_slot]
                    for match_id in match_ids
                    for previous_slot in slots
                    if previous_slot <= slot
                )
                model.addConstr(
                    idle_slack[slot]
                    >= (slot - 1) * config.courts
                    - cumulative_scheduled
                    - big_m * (1 - slot_used[slot]),
                    name=f"idle_slack_lb[{slot}]",
                )
                model.addConstr(
                    idle_slack[slot] <= big_m * slot_used[slot],
                    name=f"idle_slack_ub[{slot}]",
                )

            early_start_expr = gp.quicksum(
                float(initial_nodes[match_id].meta.get("non_staying_count", 0))
                * w1
                * assign[match_id, 1]
                for match_id in match_ids
            )
            back_to_back_expr = gp.quicksum(
                w2 * back_to_back[left, right, slot]
                for left, right in ordered_overlap_pairs
                for slot in slots[:-1]
            )
            empty_court_expr = gp.quicksum(w3 * idle_slack[slot] for slot in slots)
            model.setObjective(
                early_start_expr + back_to_back_expr + empty_court_expr,
                GRB.MINIMIZE,
            )

            model.optimize()
            status = model.Status
            if status == GRB.INF_OR_UNBD:
                model.Params.DualReductions = 0
                model.optimize()
                status = model.Status

            status_name = get_status_name(status)
            runtime_seconds = safe_get_model_attr(model, "Runtime") or 0.0
            best_bound = safe_get_model_attr(model, "ObjBound")
            mip_gap = safe_get_model_attr(model, "MIPGap")

            if status == GRB.INFEASIBLE:
                raise RuntimeError("Gurobi 调度模型无可行解。")
            if status == GRB.UNBOUNDED:
                raise RuntimeError("Gurobi 调度模型无界，请检查约束建模。")
            if model.SolCount <= 0:
                raise RuntimeError(f"Gurobi 未返回可读取解，当前状态为: {status_name}")

            solved_nodes = deepcopy(initial_nodes)
            scheduled_slots: dict[int, int] = {}
            for match_id in match_ids:
                selected_slot = None
                for slot in slots:
                    if assign[match_id, slot].X > 0.5:
                        selected_slot = slot
                        break
                if selected_slot is None:
                    selected_slot = max(slots, key=lambda slot: assign[match_id, slot].X)
                solved_nodes[match_id].scheduled_time = int(selected_slot)
                scheduled_slots[match_id] = int(selected_slot)

            total_slots = max(scheduled_slots.values()) if scheduled_slots else 0
            best_state = ScheduleState(
                t=total_slots + 1,
                all_nodes=solved_nodes,
                ready_match_ids=set(),
                scheduled_count=total_matches,
                cost=float(model.ObjVal),
            )
            self.last_solve_info = {
                "solver": "gurobi",
                "status_code": int(status),
                "status_name": status_name,
                "objective_value": float(model.ObjVal),
                "best_bound": best_bound,
                "mip_gap": mip_gap,
                "runtime_seconds": runtime_seconds,
                "total_slots": total_slots,
            }

            for hook in hooks:
                hook.on_scheduling_end(best_state)
            return best_state
        finally:
            if model is not None:
                try:
                    model.dispose()
                except Exception:
                    pass
            if env is not None:
                try:
                    env.dispose()
                except Exception:
                    pass
