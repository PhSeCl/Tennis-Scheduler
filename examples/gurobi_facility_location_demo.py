from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass
from typing import Any

IMPORT_ERROR: Exception | None = None

try:
    import gurobipy as gp
    from gurobipy import GRB
except Exception as exc:  # pragma: no cover - 依赖缺失时走这里
    gp = None  # type: ignore[assignment]
    GRB = None  # type: ignore[assignment]
    IMPORT_ERROR = exc


@dataclass(frozen=True)
class Facility:
    facility_id: str
    x: float
    y: float
    capacity: int
    fixed_cost: float


@dataclass(frozen=True)
class Customer:
    customer_id: str
    x: float
    y: float
    demand: int


@dataclass(frozen=True)
class FacilityLocationData:
    facilities: list[Facility]
    customers: list[Customer]
    unit_service_cost: dict[tuple[str, str], float]
    seed: int


@dataclass
class ModelArtifacts:
    env: Any
    model: Any
    open_vars: Any
    assign_vars: Any
    data: FacilityLocationData
    facility_map: dict[str, Facility]
    customer_map: dict[str, Customer]


@dataclass(frozen=True)
class SolveResult:
    status_code: int
    status_name: str
    message: str
    objective_value: float | None
    best_bound: float | None
    mip_gap: float | None
    runtime_seconds: float
    fixed_cost_value: float | None
    service_cost_value: float | None
    open_facilities: list[str]
    assignments: dict[str, str]
    facility_loads: dict[str, int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gurobi + gurobipy 示例：容量约束设施选址问题"
    )
    parser.add_argument("--facilities", type=int, default=5, help="设施数量")
    parser.add_argument("--customers", type=int, default=12, help="客户数量")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument(
        "--capacity-factor",
        type=float,
        default=1.20,
        help="总容量相对总需求的放大倍数，必须大于等于 1.0",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=30.0,
        help="求解时间上限（秒）",
    )
    parser.add_argument(
        "--mip-gap",
        type=float,
        default=0.0,
        help="MIPGap 容忍度，例如 0.01 表示 1%%",
    )
    parser.add_argument(
        "--log-to-console",
        action="store_true",
        help="是否显示 Gurobi 原生日志",
    )
    parser.add_argument(
        "--compute-iis",
        action="store_true",
        help="模型无可行解时，尝试计算 IIS（不可行约束子系统）",
    )
    return parser.parse_args()


def euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)


def generate_test_data(
    num_facilities: int,
    num_customers: int,
    seed: int,
    capacity_factor: float = 1.20,
    coordinate_limit: float = 100.0,
) -> FacilityLocationData:
    if num_facilities <= 0:
        raise ValueError("设施数量必须为正整数")
    if num_customers <= 0:
        raise ValueError("客户数量必须为正整数")
    if capacity_factor < 1.0:
        raise ValueError("capacity_factor 必须大于等于 1.0，否则可能无法保证可行")

    rng = random.Random(seed)

    customers: list[Customer] = []
    total_demand = 0
    for idx in range(1, num_customers + 1):
        demand = rng.randint(8, 25)
        total_demand += demand
        customers.append(
            Customer(
                customer_id=f"C{idx}",
                x=round(rng.uniform(0, coordinate_limit), 2),
                y=round(rng.uniform(0, coordinate_limit), 2),
                demand=demand,
            )
        )

    raw_capacities = [rng.randint(30, 60) for _ in range(num_facilities)]
    target_total_capacity = math.ceil(total_demand * capacity_factor)
    scale = target_total_capacity / sum(raw_capacities)
    capacities = [max(10, int(round(value * scale))) for value in raw_capacities]

    capacity_shortfall = target_total_capacity - sum(capacities)
    if capacity_shortfall > 0:
        capacities[-1] += capacity_shortfall

    facilities: list[Facility] = []
    for idx in range(1, num_facilities + 1):
        capacity = capacities[idx - 1]
        fixed_cost = round(rng.randint(120, 280) + capacity * rng.uniform(1.6, 2.3), 2)
        facilities.append(
            Facility(
                facility_id=f"F{idx}",
                x=round(rng.uniform(0, coordinate_limit), 2),
                y=round(rng.uniform(0, coordinate_limit), 2),
                capacity=capacity,
                fixed_cost=fixed_cost,
            )
        )

    unit_service_cost: dict[tuple[str, str], float] = {}
    for customer in customers:
        for facility in facilities:
            distance = euclidean_distance(
                customer.x,
                customer.y,
                facility.x,
                facility.y,
            )
            # 单位服务成本 = 距离成本 + 少量基础成本，便于形成更真实的分配偏好
            unit_cost = round(1.0 + 0.45 * distance, 2)
            unit_service_cost[(customer.customer_id, facility.facility_id)] = unit_cost

    return FacilityLocationData(
        facilities=facilities,
        customers=customers,
        unit_service_cost=unit_service_cost,
        seed=seed,
    )


def create_gurobi_env(log_to_console: bool) -> Any:
    if gp is None or GRB is None:
        message = [
            "未检测到 gurobipy，无法运行 Gurobi 示例。",
            "最简安装步骤：",
            "1) 执行: pip install gurobipy",
            "2) 确认 Gurobi 许可证可用（学术许可证、试用许可证或 WLS 均可）",
        ]
        if IMPORT_ERROR is not None:
            message.append(f"底层导入错误: {IMPORT_ERROR}")
        raise RuntimeError("\n".join(message))

    try:
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 1 if log_to_console else 0)
        env.start()
        return env
    except gp.GurobiError as exc:
        raise RuntimeError(
            "Gurobi 环境启动失败。请检查许可证是否可用，或确认 gurobipy 与 Gurobi 版本匹配。"
            f"\n原始错误: {exc}"
        ) from exc


def build_model(
    data: FacilityLocationData,
    time_limit: float | None,
    mip_gap: float | None,
    log_to_console: bool,
) -> ModelArtifacts:
    env = create_gurobi_env(log_to_console=log_to_console)
    model = gp.Model("capacitated_facility_location", env=env)

    if time_limit is not None and time_limit > 0:
        model.Params.TimeLimit = time_limit
    if mip_gap is not None and mip_gap >= 0:
        model.Params.MIPGap = mip_gap

    facility_ids = [facility.facility_id for facility in data.facilities]
    customer_ids = [customer.customer_id for customer in data.customers]

    facility_map = {facility.facility_id: facility for facility in data.facilities}
    customer_map = {customer.customer_id: customer for customer in data.customers}

    open_vars = model.addVars(facility_ids, vtype=GRB.BINARY, name="open")
    assign_vars = model.addVars(customer_ids, facility_ids, vtype=GRB.BINARY, name="assign")

    fixed_cost_expr = gp.quicksum(
        facility_map[facility_id].fixed_cost * open_vars[facility_id]
        for facility_id in facility_ids
    )
    service_cost_expr = gp.quicksum(
        customer_map[customer_id].demand
        * data.unit_service_cost[(customer_id, facility_id)]
        * assign_vars[customer_id, facility_id]
        for customer_id in customer_ids
        for facility_id in facility_ids
    )

    model.setObjective(fixed_cost_expr + service_cost_expr, GRB.MINIMIZE)

    model.addConstrs(
        (
            gp.quicksum(assign_vars[customer_id, facility_id] for facility_id in facility_ids)
            == 1
            for customer_id in customer_ids
        ),
        name="assign_once",
    )

    model.addConstrs(
        (
            gp.quicksum(
                customer_map[customer_id].demand * assign_vars[customer_id, facility_id]
                for customer_id in customer_ids
            )
            <= facility_map[facility_id].capacity * open_vars[facility_id]
            for facility_id in facility_ids
        ),
        name="capacity",
    )

    model.addConstrs(
        (
            assign_vars[customer_id, facility_id] <= open_vars[facility_id]
            for customer_id in customer_ids
            for facility_id in facility_ids
        ),
        name="open_link",
    )

    return ModelArtifacts(
        env=env,
        model=model,
        open_vars=open_vars,
        assign_vars=assign_vars,
        data=data,
        facility_map=facility_map,
        customer_map=customer_map,
    )


def get_status_name(status_code: int) -> str:
    if GRB is None:
        return f"未知状态({status_code})"

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


def solve_model(
    artifacts: ModelArtifacts,
    compute_iis_if_infeasible: bool = False,
) -> SolveResult:
    model = artifacts.model
    model.optimize()

    status = model.Status

    # 对 INF_OR_UNBD 做一次常见的稳健性处理
    if status == GRB.INF_OR_UNBD:
        model.Params.DualReductions = 0
        model.optimize()
        status = model.Status

    status_name = get_status_name(status)
    runtime_seconds = safe_get_model_attr(model, "Runtime") or 0.0
    best_bound = safe_get_model_attr(model, "ObjBound")
    mip_gap = safe_get_model_attr(model, "MIPGap")

    if status == GRB.INFEASIBLE:
        if compute_iis_if_infeasible:
            try:
                model.computeIIS()
                message = "模型无可行解，且已完成 IIS 计算，可进一步导出约束诊断。"
            except gp.GurobiError:
                message = "模型无可行解，IIS 计算失败。"
        else:
            message = "模型无可行解。若需诊断，可启用 --compute-iis。"
        return SolveResult(
            status_code=status,
            status_name=status_name,
            message=message,
            objective_value=None,
            best_bound=best_bound,
            mip_gap=mip_gap,
            runtime_seconds=runtime_seconds,
            fixed_cost_value=None,
            service_cost_value=None,
            open_facilities=[],
            assignments={},
            facility_loads={},
        )

    if status == GRB.UNBOUNDED:
        return SolveResult(
            status_code=status,
            status_name=status_name,
            message="模型无界。请检查目标方向、变量上下界和约束是否合理。",
            objective_value=None,
            best_bound=best_bound,
            mip_gap=mip_gap,
            runtime_seconds=runtime_seconds,
            fixed_cost_value=None,
            service_cost_value=None,
            open_facilities=[],
            assignments={},
            facility_loads={},
        )

    if model.SolCount <= 0:
        return SolveResult(
            status_code=status,
            status_name=status_name,
            message="求解结束，但没有可读取的可行解。",
            objective_value=None,
            best_bound=best_bound,
            mip_gap=mip_gap,
            runtime_seconds=runtime_seconds,
            fixed_cost_value=None,
            service_cost_value=None,
            open_facilities=[],
            assignments={},
            facility_loads={},
        )

    facility_ids = [facility.facility_id for facility in artifacts.data.facilities]
    customer_ids = [customer.customer_id for customer in artifacts.data.customers]

    open_facilities = sorted(
        facility_id
        for facility_id in facility_ids
        if artifacts.open_vars[facility_id].X > 0.5
    )

    assignments: dict[str, str] = {}
    facility_loads = {facility_id: 0 for facility_id in facility_ids}

    for customer_id in customer_ids:
        selected_facility = None
        for facility_id in facility_ids:
            if artifacts.assign_vars[customer_id, facility_id].X > 0.5:
                selected_facility = facility_id
                break
        if selected_facility is None:
            selected_facility = max(
                facility_ids,
                key=lambda facility_id: artifacts.assign_vars[customer_id, facility_id].X,
            )
        assignments[customer_id] = selected_facility
        facility_loads[selected_facility] += artifacts.customer_map[customer_id].demand

    fixed_cost_value = sum(
        artifacts.facility_map[facility_id].fixed_cost
        for facility_id in open_facilities
    )
    service_cost_value = sum(
        artifacts.customer_map[customer_id].demand
        * artifacts.data.unit_service_cost[(customer_id, assignments[customer_id])]
        for customer_id in customer_ids
    )

    if status == GRB.OPTIMAL:
        message = "求解成功，并已证明当前解为全局最优解。"
    elif status == GRB.TIME_LIMIT:
        message = "达到时间上限，但已找到可行解。"
    elif status == GRB.SUBOPTIMAL:
        message = "得到可行解，但尚未证明最优。"
    else:
        message = "求解完成，并返回了一个可读的可行解。"

    return SolveResult(
        status_code=status,
        status_name=status_name,
        message=message,
        objective_value=float(model.ObjVal),
        best_bound=best_bound,
        mip_gap=mip_gap,
        runtime_seconds=runtime_seconds,
        fixed_cost_value=float(fixed_cost_value),
        service_cost_value=float(service_cost_value),
        open_facilities=open_facilities,
        assignments=assignments,
        facility_loads=facility_loads,
    )


def print_input_data(data: FacilityLocationData) -> None:
    total_demand = sum(customer.demand for customer in data.customers)
    total_capacity = sum(facility.capacity for facility in data.facilities)

    print("=" * 72)
    print("输入数据示例")
    print("=" * 72)
    print(f"随机种子: {data.seed}")
    print(f"设施数量: {len(data.facilities)}")
    print(f"客户数量: {len(data.customers)}")
    print(f"总需求: {total_demand}")
    print(f"总容量: {total_capacity}")
    print()

    print("设施列表:")
    for facility in data.facilities:
        print(
            "  "
            f"{facility.facility_id}: 坐标=({facility.x:.2f}, {facility.y:.2f}), "
            f"容量={facility.capacity}, 固定成本={facility.fixed_cost:.2f}"
        )
    print()

    print("客户列表:")
    for customer in data.customers:
        print(
            "  "
            f"{customer.customer_id}: 坐标=({customer.x:.2f}, {customer.y:.2f}), "
            f"需求={customer.demand}"
        )
    print()

    print("前 12 条单位服务成本样例:")
    counter = 0
    for customer in data.customers:
        for facility in data.facilities:
            print(
                "  "
                f"cost[{customer.customer_id}, {facility.facility_id}] = "
                f"{data.unit_service_cost[(customer.customer_id, facility.facility_id)]:.2f}"
            )
            counter += 1
            if counter >= 12:
                print()
                return
    print()


def print_solution(result: SolveResult, data: FacilityLocationData) -> None:
    print("=" * 72)
    print("求解结果")
    print("=" * 72)
    print(f"求解状态: {result.status_name}")
    print(f"状态说明: {result.message}")
    print(f"运行时间: {result.runtime_seconds:.4f} 秒")

    if result.objective_value is None:
        if result.best_bound is not None:
            print(f"当前下界 / 上界参考: {result.best_bound:.4f}")
        return

    print(f"目标值: {result.objective_value:.4f}")
    if result.best_bound is not None:
        print(f"当前最优界: {result.best_bound:.4f}")
    if result.mip_gap is not None:
        print(f"MIPGap: {result.mip_gap:.6f}")
    if result.fixed_cost_value is not None:
        print(f"固定成本部分: {result.fixed_cost_value:.4f}")
    if result.service_cost_value is not None:
        print(f"运输成本部分: {result.service_cost_value:.4f}")

    print()
    print(f"启用设施: {', '.join(result.open_facilities) if result.open_facilities else '无'}")
    print("设施负载:")
    for facility in data.facilities:
        load = result.facility_loads.get(facility.facility_id, 0)
        print(
            "  "
            f"{facility.facility_id}: 负载={load}, 容量={facility.capacity}, "
            f"是否启用={'是' if facility.facility_id in result.open_facilities else '否'}"
        )

    print()
    print("客户分配结果:")
    for customer in data.customers:
        facility_id = result.assignments.get(customer.customer_id, "N/A")
        unit_cost = data.unit_service_cost.get((customer.customer_id, facility_id), 0.0)
        total_cost = unit_cost * customer.demand
        print(
            "  "
            f"{customer.customer_id} -> {facility_id}, 需求={customer.demand}, "
            f"单位成本={unit_cost:.2f}, 分配成本={total_cost:.2f}"
        )


def dispose_artifacts(artifacts: ModelArtifacts | None) -> None:
    if artifacts is None:
        return
    try:
        artifacts.model.dispose()
    except Exception:
        pass
    try:
        artifacts.env.dispose()
    except Exception:
        pass


def main() -> int:
    args = parse_args()
    artifacts: ModelArtifacts | None = None

    try:
        data = generate_test_data(
            num_facilities=args.facilities,
            num_customers=args.customers,
            seed=args.seed,
            capacity_factor=args.capacity_factor,
        )
        print_input_data(data)

        artifacts = build_model(
            data=data,
            time_limit=args.time_limit,
            mip_gap=args.mip_gap,
            log_to_console=args.log_to_console,
        )
        result = solve_model(
            artifacts=artifacts,
            compute_iis_if_infeasible=args.compute_iis,
        )
        print_solution(result, data)

        if result.objective_value is None:
            return 1
        return 0
    except ValueError as exc:
        print(f"数据生成失败: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - 保护主入口
        print(f"程序出现未预期错误: {exc}", file=sys.stderr)
        return 3
    finally:
        dispose_artifacts(artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
