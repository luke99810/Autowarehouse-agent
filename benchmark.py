#!/usr/bin/env python3
"""
Warehouse Scheduling Agent - Full Methods Benchmark
====================================================
Compares traditional and PDE/diffusion-based approaches:

  Traditional:
    A*-Only          - Independent A* per robot, no coordination
    A*+Prioritized   - Prioritized planning (current baseline)
    
  Physics-Informed (Phase 2):
    PDE-A*           - A* with PDE density field as heuristic penalty
    Diffusion        - Simplified score-based diffusion trajectory sampling
    PDE+Diffusion    - Diffusion sampling conditioned on PDE density field
"""

import sys, os, time, json, copy
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Tuple, Set
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import AgentConfig, WarehouseConfig, PathPlanningConfig
from agent.simulated_env import SimulatedWarehouse
from agent.task_assignment import TaskAssignmentModule
from agent.conflict_resolution import ConflictResolutionModule
from agent.metrics import MetricsModule
from config import TaskAssignmentConfig, ConflictResolutionConfig, MetricsConfig
from agent.pde_planner import PDEDensityField, PDEGuidedAStar, DiffusionPathPlanner
from agent.path_planning import AStarPlanner, PrioritizedPlanner

# ============================================================
# Result types
# ============================================================
@dataclass
class MethodResult:
    method: str
    category: str  # "traditional" or "physics-informed"
    throughput_mean: float
    throughput_std: float
    orders_mean: float
    orders_std: float
    collision_rate_mean: float
    path_efficiency_mean: float
    congestion_mean: float
    n_runs: int
    
@dataclass  
class RunResult:
    orders: int
    throughput: float
    collisions: int
    steps: int
    time_s: float
    path_lengths: List[float]


# ============================================================
# Multi-Method Agent Runner
# ============================================================
class MethodRunner:
    """Runs one episode with a specific planning method."""
    
    def __init__(self, config: AgentConfig, method: str):
        self.config = config
        self.method = method
        self.wc = config.warehouse
        self.tc = config.task_assignment
        
        # Init env
        scale = getattr(self.wc, 'layout_size', None)
        self.env = SimulatedWarehouse(
            scale=scale if scale and scale != "small" else None,
            n_agents=self.wc.n_agents,
            n_shelves=self.wc.request_queue_size,
            max_steps=self.wc.max_steps,
        )
        
        # Task assignment
        self.ta = TaskAssignmentModule(self.tc)
        self.ta.initialize(self.wc.n_agents)
        self.ta.set_environment_layout(
            list(self.env.shelf_positions),
            list(self.env.delivery_zones),
        )
        
        # PDE field (shared for PDE methods)
        self.pde = PDEDensityField(
            self.env.grid_width, self.env.grid_height,
            diffusion_coef=0.06, convection_coef=0.12
        )
        
        # Planning method
        self.planner = self._init_planner(method)
        self.cr = ConflictResolutionModule(ConflictResolutionConfig())
        
        # State
        self.agent_paths = {}
        self._pickup_wait = {}
        self.total_path_length = 0
        self.path_count = 0
    
    def _init_planner(self, method: str):
        if method == "A*-Only":
            return AStarPlanner(diagonal=False)
        elif method == "A*+Prioritized":
            return PrioritizedPlanner(PathPlanningConfig(enable_prioritized_planning=True))
        elif method == "PDE-A*":
            return PDEGuidedAStar(self.pde, lambda_density=3.0)
        elif method == "Diffusion":
            return DiffusionPathPlanner(self.pde, n_diffusion_steps=8, n_samples=3, temperature=0.2)
        elif method == "PDE+Diffusion":
            return DiffusionPathPlanner(self.pde, n_diffusion_steps=10, n_samples=3, temperature=0.12)
        else:
            return AStarPlanner(diagonal=False)
    
    def run(self, seed: int = 42) -> RunResult:
        """Run one episode and return metrics."""
        np.random.seed(seed)
        obs, info = self.env.reset(seed=seed)
        self.ta.reset()
        self.pde.reset()
        self.agent_paths.clear()
        self._pickup_wait.clear()
        self.total_path_length = 0
        self.path_count = 0
        
        # Generate initial tasks
        for _ in range(self.wc.n_agents):
            self.ta.generate_order(0)
        
        completed = 0
        collisions = 0
        prev_positions = {}
        
        t0 = time.time()
        step = 0
        
        while step < self.wc.max_steps:
            # Robot states
            rpos = {a['id']: (a['x'], a['y']) for a in self.env.agents}
            rload = {a['id']: a['carrying_shelf'] is not None for a in self.env.agents}
            rdirs = {a['id']: a['dir'] for a in self.env.agents}
            rstate = {}
            for a in self.env.agents:
                assign = self.ta.agent_assignments.get(a['id'])
                rstate[a['id']] = "busy" if (assign and not assign.is_idle) else "idle"
            
            # Task management
            idle_count = sum(1 for s in rstate.values() if s == "idle")
            if idle_count >= 2 and len(self.ta.pending_tasks) <= 2:
                for _ in range(self.wc.n_agents - len(self.ta.pending_tasks)):
                    self.ta.generate_order(step)
            if idle_count == self.wc.n_agents:
                self.ta._assigned_shelves.clear()
            self.ta.assign_tasks(rpos, rstate, step)
            
            # Update PDE density field
            robot_pos_list = [rpos[i] for i in range(self.wc.n_agents)]
            robot_dir_list = [rdirs[i] for i in range(self.wc.n_agents)]
            self.pde.update(
                robot_pos_list, robot_dir_list,
                list(self.env.shelf_positions),
                list(self.env.delivery_zones),
                dt=0.15
            )
            
            # Update task progress
            for a in self.env.agents:
                result = self.ta.update_task_progress(a['id'], (a['x'], a['y']),
                                                       a['carrying_shelf'] is not None, step)
                if result == "at_pickup":
                    self._pickup_wait.setdefault(a['id'], step)
                elif result == "delivery_completed":
                    completed += 1
            
            # Stuck robot handling
            for a in self.env.agents:
                phase = self.ta.agent_assignments.get(a['id'])
                if phase and phase.phase == "picking_up":
                    wait_start = self._pickup_wait.get(a['id'], step)
                    if step - wait_start > 5:
                        task = phase.current_task
                        if task:
                            self.ta._assigned_shelves.discard(task.shelf_position)
                            self.ta.active_tasks.pop(task.task_id, None)
                        phase.current_task = None
                        phase.phase = "idle"
                        self._pickup_wait.pop(a['id'], None)
                        self.agent_paths[a['id']] = []
            
            # Path planning (METHOD-SPECIFIC)
            plan_tasks = []
            for a in self.env.agents:
                target = self.ta.get_task_target(a['id'])
                if target and (a['x'], a['y']) != target:
                    plan_tasks.append((a['id'], (a['x'], a['y']), target))
                else:
                    self.agent_paths[a['id']] = []
            
            obstacles = set()
            target_shelves = set()
            # Build per-agent obstacle sets to exclude self position
            agent_obstacles = {}
            for a in self.env.agents:
                aid = a['id']
                obs = set()
                t = self.ta.get_task_target(aid)
                if t: target_shelves.add(t)
                # Add shelves (except target)
                for sp in self.env.shelf_positions:
                    if sp != t:
                        obs.add(sp)
                # Add other robots (not self), skip robots in delivery phase
                for a2 in self.env.agents:
                    if a2['id'] != aid:
                        p2 = self.ta.agent_assignments.get(a2['id'])
                        # Don't block robots heading to delivery (they'll move away)
                        if p2 and p2.phase == "moving_to_delivery":
                            continue
                        pos2 = (a2['x'], a2['y'])
                        if pos2 != t:
                            obs.add(pos2)
                agent_obstacles[aid] = obs
            
            # Execute planning
            if self.method in ("A*-Only", "PDE-A*"):
                # Single-agent planner for each robot
                for aid, start, goal in plan_tasks:
                    obs = agent_obstacles.get(aid, set())
                    if isinstance(self.planner, PDEGuidedAStar):
                        path = self.planner.find_path(start, goal, obs)
                        if not path:
                            # Fallback to standard A*
                            path = AStarPlanner().find_path(start, goal, obs)
                    else:
                        path = self.planner.find_path(start, goal, obs)
                    self.agent_paths[aid] = path if path else []
                    if path:
                        self.total_path_length += len(path)
                        self.path_count += 1
            elif self.method in ("A*+Prioritized",):
                priorities = {a['id']: self.ta.get_robot_priority(a['id']) 
                            for a in self.env.agents}
                # Shelves not targeted by anyone are obstacles
                all_obs = set()
                for sp in self.env.shelf_positions:
                    if sp not in target_shelves:
                        all_obs.add(sp)
                results = self.planner.plan(plan_tasks, all_obs, priorities)
                for aid, res in results.items():
                    self.agent_paths[aid] = res.path if res.success else []
                    if res.path:
                        self.total_path_length += len(res.path)
                        self.path_count += 1
            elif self.method in ("Diffusion", "PDE+Diffusion"):
                astar = AStarPlanner()
                for aid, start, goal in plan_tasks:
                    obs = agent_obstacles.get(aid, set())
                    path = self.planner.generate_trajectory(start, goal, obs)
                    if not path:
                        path = astar.find_path(start, goal, obs)
                    self.agent_paths[aid] = path if path else []
                    if path:
                        self.total_path_length += len(path)
                        self.path_count += 1
            
            # Conflict detection
            conflicts = self.cr.detect_conflicts(self.agent_paths, rpos)
            collisions += len([c for c in conflicts if c.conflict_time == 0])
            
            # Select actions
            actions = self._select_actions()
            
            # Execute
            obs, rew, term, trunc, info = self.env.step(actions)
            prev_positions = rpos.copy()
            step += 1
        
        elapsed = time.time() - t0
        
        path_lengths = [len(p) for p in self.agent_paths.values() if p]
        
        return RunResult(
            orders=completed,
            throughput=completed / max(step, 1) * 3600,
            collisions=collisions,
            steps=step,
            time_s=elapsed,
            path_lengths=path_lengths,
        )
    
    def _select_actions(self) -> Dict[str, int]:
        """Convert paths to D-RWARE actions."""
        actions = {}
        dir_map = {(0, -1): 0, (1, 0): 1, (0, 1): 2, (-1, 0): 3}
        
        for a in self.env.agents:
            aid = a['id']
            path = self.agent_paths.get(aid, [])
            target = self.ta.get_task_target(aid)
            phase = self.ta.agent_assignments.get(aid)
            phase_str = phase.phase if phase else ""
            
            if phase_str in ("picking_up", "delivering"):
                actions[f"agent_{aid}"] = 3  # Load/Unload
            elif target and (a['x'], a['y']) == target:
                actions[f"agent_{aid}"] = 3  # Load/Unload
            elif not path:
                actions[f"agent_{aid}"] = 0
            else:
                nx, ny = path[0]
                rd = dir_map.get((nx - a['x'], ny - a['y']))
                if rd is None:
                    actions[f"agent_{aid}"] = 0
                elif a['dir'] == rd:
                    actions[f"agent_{aid}"] = 2  # Forward
                else:
                    diff = (rd - a['dir']) % 4
                    actions[f"agent_{aid}"] = 1 if diff == 1 else 0
        
        return actions


# ============================================================
# Benchmark Runner
# ============================================================
ALL_METHODS = [
    ("A*-Only", "traditional"),
    ("A*+Prioritized", "traditional"),
    ("PDE-A*", "physics-informed"),
    ("Diffusion", "physics-informed"),
    ("PDE+Diffusion", "physics-informed"),
]


def run_comparison(scale="small", n_agents=4, max_steps=600,
                   n_runs=3, seed=42) -> List[MethodResult]:
    """Run all methods for comparison."""
    results = []
    
    for method, category in ALL_METHODS:
        config = AgentConfig()
        config.warehouse.layout_size = scale
        config.warehouse.n_agents = n_agents
        config.warehouse.request_queue_size = n_agents
        config.warehouse.max_steps = max_steps
        
        orders_list, tp_list, col_list, path_eff_list = [], [], [], []
        
        print(f"\n  [{category}] {method}:")
        for run in range(n_runs):
            runner = MethodRunner(config, method)
            result = runner.run(seed + run)
            
            orders_list.append(result.orders)
            tp_list.append(result.throughput)
            col_list.append(result.collisions)
            
            # Path efficiency: manhattan / actual
            if result.path_lengths:
                avg_len = np.mean(result.path_lengths)
                path_eff_list.append(avg_len)
            
            print(f"    run {run}: orders={result.orders:>3}  tp={result.throughput:>6.1f}/h  "
                  f"col={result.collisions:>3}  time={result.time_s:.1f}s")
        
        results.append(MethodResult(
            method=method, category=category,
            throughput_mean=np.mean(tp_list),
            throughput_std=np.std(tp_list),
            orders_mean=np.mean(orders_list),
            orders_std=np.std(orders_list),
            collision_rate_mean=np.mean(col_list) / max_steps * 1000,
            path_efficiency_mean=np.mean(path_eff_list) if path_eff_list else 0,
            congestion_mean=0.0,
            n_runs=n_runs,
        ))
    
    return results


# ============================================================
# Report
# ============================================================
def print_comparison_table(results: List[MethodResult], title: str):
    """Pretty-print comparison table."""
    print(f"\n  {title}")
    print(f"  {'='*70}")
    header = f"  {'Method':<20} {'Category':<16} {'TP/h':>8} {'+-':>6} {'Orders':>7} {'Col/1k':>7}"
    print(header)
    print(f"  {'-'*70}")
    
    for r in results:
        print(f"  {r.method:<20} {r.category:<16} {r.throughput_mean:>8.1f} "
              f"{r.throughput_std:>6.1f} {r.orders_mean:>7.1f} {r.collision_rate_mean:>7.1f}")
    
    # Best
    best = max(results, key=lambda x: x.throughput_mean)
    print(f"\n  >> Best: {best.method} ({best.throughput_mean:.1f}/h)")
    
    # Improvement over baseline
    baseline = next((r for r in results if r.method == "A*+Prioritized"), None)
    if baseline and baseline.throughput_mean > 0:
        for r in results:
            if r.method != "A*+Prioritized":
                improvement = (r.throughput_mean - baseline.throughput_mean) / baseline.throughput_mean * 100
                print(f"  {r.method} vs baseline: {improvement:+.1f}%")


def generate_comparison_chart(all_results: Dict, output_path: str):
    """Generate comparison charts."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    scenarios = list(all_results.keys())
    n_scenarios = len(scenarios)
    
    fig, axes = plt.subplots(1, n_scenarios, figsize=(6 * n_scenarios, 5))
    if n_scenarios == 1:
        axes = [axes]
    
    colors = {'traditional': '#4682B4', 'physics-informed': '#FF6347'}
    
    for ax, (scenario, results) in zip(axes, all_results.items()):
        methods = [r.method for r in results]
        tps = [r.throughput_mean for r in results]
        errs = [r.throughput_std for r in results]
        cats = [r.category for r in results]
        bar_colors = [colors[c] for c in cats]
        
        bars = ax.bar(range(len(methods)), tps, color=bar_colors, yerr=errs, capsize=4)
        ax.set_xticks(range(len(methods)))
        ax.set_xticklabels(methods, rotation=20, ha='right', fontsize=8)
        ax.set_title(f'{scenario}\n({results[0].n_runs} runs)', fontsize=10, fontweight='bold')
        ax.set_ylabel('Throughput (orders/hour)')
        
        for bar, val in zip(bars, tps):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                   f'{val:.0f}', ha='center', fontsize=8, fontweight='bold')
        
        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=colors['traditional'], label='Traditional'),
            Patch(facecolor=colors['physics-informed'], label='Physics-Informed (PDE/Diffusion)'),
        ]
        ax.legend(handles=legend_elements, fontsize=7, loc='upper left')
    
    plt.suptitle('Warehouse Scheduling Agent - Methods Comparison',
                fontsize=13, fontweight='bold')
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n  Chart saved: {output_path}")


# ============================================================
# Main
# ============================================================
def main():
    import argparse
    p = argparse.ArgumentParser(description="Full Methods Benchmark")
    p.add_argument("--quick", action="store_true", help="Quick: 1 run, 400 steps")
    p.add_argument("--runs", type=int, default=2, help="Runs per method")
    p.add_argument("--steps", type=int, default=500, help="Steps per run")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    
    n_runs = 1 if args.quick else args.runs
    max_steps = 400 if args.quick else args.steps
    
    print("=" * 70)
    print("  WAREHOUSE SCHEDULING - FULL METHODS COMPARISON")
    print(f"  {n_runs} runs x {max_steps} steps each")
    print("=" * 70)
    
    all_results = {}
    t0 = time.time()
    
    # Scenario 1: small scale, 4 agents
    print("\n" + "=" * 70)
    print("  SCENARIO 1: Small warehouse, 4 agents")
    print("=" * 70)
    r1 = run_comparison("small", 4, max_steps, n_runs, args.seed)
    print_comparison_table(r1, "SCENARIO 1 RESULTS")
    all_results["Small-4Agents"] = r1
    
    # Generate chart
    chart_path = os.path.join(os.getcwd(), "method_comparison.png")
    generate_comparison_chart(all_results, chart_path)
    
    # Save JSON
    json_path = os.path.join(os.getcwd(), "method_comparison.json")
    serializable = {}
    for scenario, results in all_results.items():
        serializable[scenario] = [asdict(r) for r in results]
    with open(json_path, "w") as fp:
        json.dump(serializable, fp, indent=2)
    print(f"\n  JSON: {json_path}")
    
    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
