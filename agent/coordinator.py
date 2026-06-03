"""Agent主协调器 - 完整工作流程"""
from typing import Dict, Set, List, Tuple, Optional
from agent.perception import PerceptionModule, EnvironmentState, RobotState
from agent.task_assignment import TaskAssignmentModule
from agent.path_planning import PathPlanningModule, AStarPlanner, PrioritizedPlanner, PathResult
from agent.conflict_resolution import ConflictResolutionModule
from agent.visualization import VisualizationModule
from agent.metrics import MetricsModule
from agent.pde_planner import PDEDensityField, PDEGuidedAStar, DiffusionPathPlanner

class PlannerFactory:
    """规划器工厂 - 根据配置创建不同的路径规划器"""
    
    @staticmethod
    def create_planner(config, pde_field=None):
        """根据配置创建规划器实例"""
        algorithm = config.algorithm
        
        if algorithm == "astar":
            return AStarPlanner(diagonal=config.diagonal_movement)
        elif algorithm == "prioritized":
            return PrioritizedPlanner(config)
        elif algorithm == "pde_astar":
            if pde_field is None:
                raise ValueError("PDE-A* requires a PDE density field")
            return PDEGuidedAStar(pde_field, lambda_density=config.density_weight)
        elif algorithm == "diffusion":
            if pde_field is None:
                raise ValueError("Diffusion planner requires a PDE density field")
            return DiffusionPathPlanner(
                pde_field, 
                n_diffusion_steps=config.n_diffusion_steps,
                n_samples=config.n_samples,
                temperature=config.temperature,
                density_weight=config.density_weight,
                perturbation_prob=getattr(config, 'perturbation_probability', 0.2)
            )
        elif algorithm == "pde_diffusion":
            if pde_field is None:
                raise ValueError("PDE+Diffusion requires a PDE density field")
            return DiffusionPathPlanner(
                pde_field, 
                n_diffusion_steps=config.n_diffusion_steps,
                n_samples=config.n_samples,
                temperature=config.temperature,
                density_weight=config.density_weight,
                perturbation_prob=getattr(config, 'perturbation_probability', 0.2)
            )
        else:
            return AStarPlanner(diagonal=config.diagonal_movement)

class CoordinatorAgent:
    """仓储协同调度Agent总协调器 - 支持多种调度策略"""
    
    def __init__(self, config):
        self.config = config
        self.perception = PerceptionModule(config.warehouse)
        self.task_assignment = TaskAssignmentModule(config.task_assignment)
        self.conflict_resolution = ConflictResolutionModule(config.conflict_resolution)
        self.visualization = VisualizationModule(config.visualization)
        self.metrics = MetricsModule(config.metrics)
        
        # PDE密度场（用于物理启发方法）
        self.pde_field = None
        
        # 当前使用的规划器
        self.planner = None
        self.agent_paths = {}
        self.prev_positions = {}
        self._pickup_wait = {}
        
        print("=" * 60)
        print(f"  Warehouse Scheduling Agent v2.0")
        print(f"  Robots: {config.warehouse.n_agents}")
        print(f"  Algorithm: {config.path_planning.algorithm}")
        print(f"  Strategy: {config.task_assignment.strategy}")
        print(f"  Scale: {config.warehouse.layout_size}")
        print("=" * 60)
    
    def initialize(self):
        """初始化Agent"""
        self.perception.initialize()
        self.task_assignment.initialize(self.config.warehouse.n_agents)
        env_state = self.perception.reset(seed=self.config.seed)
        self._update_layout(env_state)
        
        # 初始化PDE密度场（如果使用物理启发方法）
        if self.config.path_planning.algorithm in ("pde_astar", "diffusion", "pde_diffusion"):
            self.pde_field = PDEDensityField(
                env_state.grid_width, 
                env_state.grid_height,
                diffusion_coef=self.config.path_planning.diffusion_coef,
                convection_coef=self.config.path_planning.convection_coef
            )
        
        # 创建规划器
        self.planner = PlannerFactory.create_planner(
            self.config.path_planning, 
            self.pde_field
        )
    
    def _update_layout(self, env_state):
        """更新环境布局信息"""
        shelves = [(s.position[0], s.position[1]) for s in env_state.shelves]
        deliveries = []
        if self.perception.delivery_list:
            deliveries = list(self.perception.delivery_list)
        self.task_assignment.set_environment_layout(shelves, deliveries)
    
    def run_episode(self, episode_id):
        """运行单个Episode"""
        print(f"\n--- Episode {episode_id} ---")
        env_state = self.perception.reset(seed=self.config.seed + episode_id)
        self._update_layout(env_state)
        self.task_assignment.reset()
        self.conflict_resolution.reset()
        self.metrics.start_episode(episode_id)
        self.agent_paths.clear()
        self.prev_positions.clear()
        self._pickup_wait.clear()
        self.env_state = env_state
        
        # 重置PDE场
        if self.pde_field:
            self.pde_field.reset()
        
        # 生成初始订单
        for _ in range(self.config.warehouse.n_agents):
            self.task_assignment.generate_order(0)
        
        # 初始化可视化
        if episode_id == 0 and self.config.visualization.enabled:
            shelves = [(s.position[0], s.position[1]) for s in env_state.shelves]
            deliveries = self.task_assignment.delivery_positions
            self.visualization.setup(
                env_state.grid_width, 
                env_state.grid_height,
                shelves, 
                deliveries,
                self.pde_field if self.config.visualization.show_density_field else None
            )
        
        step = 0
        completed = 0
        total_collisions = 0
        
        while not self.perception.episode_done:
            # 1. 感知 - 获取机器人状态
            rpos, rdir, rload, rstate = {}, {}, {}, {}
            for r in self.env_state.robots:
                rpos[r.agent_id] = r.position
                rdir[r.agent_id] = r.direction
                rload[r.agent_id] = r.has_shelf
                a = self.task_assignment.agent_assignments.get(r.agent_id)
                rstate[r.agent_id] = "busy" if (a and not a.is_idle) else "idle"
            
            # 2. 任务分配
            self._manage_tasks(rpos, rstate, step)
            
            # 更新任务进度
            for r in self.env_state.robots:
                result = self.task_assignment.update_task_progress(
                    r.agent_id, r.position, r.has_shelf, step)
                if result == "delivery_completed":
                    completed += 1
                elif result == "at_pickup":
                    self._pickup_wait.setdefault(r.agent_id, step)
            
            # 检测卡住的机器人
            self._handle_stuck_robots(rpos, step)
            
            # 3. 更新PDE密度场（如果使用）
            if self.pde_field:
                robot_pos_list = [rpos[i] for i in range(self.config.warehouse.n_agents)]
                robot_dir_list = [rdir[i] for i in range(self.config.warehouse.n_agents)]
                self.pde_field.update(
                    robot_pos_list, 
                    robot_dir_list,
                    list(self.env_state.shelf_positions) if hasattr(self.env_state, 'shelf_positions') else [],
                    self.task_assignment.delivery_positions,
                    dt=0.15
                )
            
            # 4. 路径规划
            self._plan_paths(rpos)
            
            # 5. 冲突消解
            conflicts = self.conflict_resolution.detect_conflicts(self.agent_paths, rpos)
            resolution = self.conflict_resolution.resolve(conflicts, 
                {r.agent_id: self.task_assignment.get_robot_priority(r.agent_id) 
                 for r in self.env_state.robots})
            total_collisions += len(conflicts)
            
            # 处理需要重新规划的机器人
            for aid in resolution.replan_agents:
                if aid in self.agent_paths and len(self.agent_paths.get(aid, [])) > 1:
                    self.agent_paths[aid] = self.agent_paths[aid][:1]
            
            # 6. 动作执行
            deadlocked = self.conflict_resolution.detect_deadlock(rpos, self.prev_positions)
            actions = self._select_actions(self.env_state.robots, deadlocked)
            self.env_state = self.perception.step(actions)
            self.prev_positions = rpos.copy()
            
            # 7. 记录指标
            self._record_metrics(step, completed, total_collisions, deadlocked)
            
            # 8. 可视化
            if self.config.visualization.enabled:
                self._render_visualization(step, rpos, rdir, rload)
            
            step += 1
            if step % 200 == 0:
                print(f"  [Step {step}] Done:{completed} Collision:{total_collisions} "
                      f"TP:{completed/max(step,1)*3600:.1f}/h")
        
        summary = self.metrics.end_episode(step)
        self.metrics.print_summary()
        return summary
    
    def _manage_tasks(self, robot_positions, robot_states, step):
        """任务管理：生成新订单并分配"""
        idle_count = sum(1 for st in robot_states.values() if st == "idle")
        pending = len(self.task_assignment.pending_tasks)
        
        # 空闲过半且待处理订单不足时生成新订单
        if idle_count >= 2 and pending <= 2:
            for _ in range(self.config.warehouse.n_agents - pending):
                self.task_assignment.generate_order(step)
        
        # 全部空闲时清空已分配标记
        if idle_count == self.config.warehouse.n_agents:
            self.task_assignment._assigned_shelves.clear()
        
        self.task_assignment.assign_tasks(robot_positions, robot_states, step)
    
    def _handle_stuck_robots(self, robot_positions, step):
        """处理卡住的机器人"""
        for r in self.env_state.robots:
            phase = self.task_assignment.agent_assignments.get(r.agent_id)
            if phase and phase.phase == "picking_up":
                wait_start = self._pickup_wait.get(r.agent_id, step)
                if step - wait_start > 5:
                    # 强制释放当前任务
                    task = phase.current_task
                    if task:
                        self.task_assignment._assigned_shelves.discard(task.shelf_position)
                        self.task_assignment.active_tasks.pop(task.task_id, None)
                    phase.current_task = None
                    phase.phase = "idle"
                    self._pickup_wait.pop(r.agent_id, None)
                    self.agent_paths[r.agent_id] = []
    
    def _plan_paths(self, robot_positions):
        """路径规划：根据当前算法生成路径"""
        plan_tasks = []
        for r in self.env_state.robots:
            target = self.task_assignment.get_task_target(r.agent_id)
            if target and r.position != target:
                plan_tasks.append((r.agent_id, r.position, target))
            else:
                self.agent_paths[r.agent_id] = []
        
        if not plan_tasks:
            return
        
        # 构建障碍物集合
        obstacles = set()
        target_shelf_positions = set()
        
        for r in self.env_state.robots:
            t = self.task_assignment.get_task_target(r.agent_id)
            if t:
                target_shelf_positions.add(t)
        
        # 添加非目标货架作为障碍物
        for s in getattr(self.env_state, 'shelves', []):
            if s.position not in target_shelf_positions:
                obstacles.add(s.position)
        
        # 添加其他机器人作为障碍物
        for r in self.env_state.robots:
            if r.position not in target_shelf_positions:
                obstacles.add(r.position)
        
        # 根据算法类型执行规划
        algorithm = self.config.path_planning.algorithm
        
        if algorithm in ("astar", "pde_astar", "diffusion", "pde_diffusion"):
            # 单机器人规划
            for aid, start, goal in plan_tasks:
                obs = obstacles.copy()
                # 移除自身位置
                obs.discard(start)
                
                if algorithm in ("pde_astar", "diffusion", "pde_diffusion"):
                    path = self.planner.find_path(start, goal, obs) if hasattr(self.planner, 'find_path') \
                           else self.planner.generate_trajectory(start, goal, obs)
                else:
                    path = self.planner.find_path(start, goal, obs)
                
                self.agent_paths[aid] = path if path else []
        
        elif algorithm == "prioritized":
            # 多机器人优先级规划
            priorities = {r.agent_id: self.task_assignment.get_robot_priority(r.agent_id)
                         for r in self.env_state.robots}
            results = self.planner.plan(plan_tasks, obstacles, priorities)
            for aid, res in results.items():
                self.agent_paths[aid] = res.path if res.success else []
    
    def _select_actions(self, robots, deadlocked):
        """将路径转换为动作"""
        actions = {}
        dir_map = {(0, -1): 0, (1, 0): 1, (0, 1): 2, (-1, 0): 3}
        
        for r in robots:
            aid = r.agent_id
            
            if aid in deadlocked:
                actions[aid] = 0
                continue
            
            path = self.agent_paths.get(aid, [])
            
            if not path:
                target = self.task_assignment.get_task_target(aid)
                phase = self.task_assignment.agent_assignments.get(aid)
                phase_str = phase.phase if phase else ""
                
                if phase_str in ("picking_up", "delivering"):
                    actions[aid] = 3
                elif target and r.position == target:
                    actions[aid] = 3
                else:
                    actions[aid] = 0
                continue
            
            nx, ny = path[0]
            rd = dir_map.get((nx - r.position[0], ny - r.position[1]))
            
            if rd is None:
                actions[aid] = 0
                continue
            
            if r.direction == rd:
                actions[aid] = 2  # Forward
            else:
                diff = (rd - r.direction) % 4
                if diff == 1:
                    actions[aid] = 1  # Turn Right
                elif diff == 3:
                    actions[aid] = 0  # Turn Left
                else:
                    actions[aid] = 1  # Turn Right (180°)
        
        return actions
    
    def _record_metrics(self, step, completed, collisions, deadlocked):
        """记录指标"""
        n_active = sum(1 for r in self.env_state.robots if r.is_active)
        n_loaded = sum(1 for r in self.env_state.robots if r.has_shelf)
        n_idle = sum(1 for r in self.env_state.robots
                    if self.task_assignment.agent_assignments.get(r.agent_id, None)
                    and self.task_assignment.agent_assignments[r.agent_id].is_idle)
        ts = self.task_assignment.get_summary()
        
        dist_delta = 0
        for r in self.env_state.robots:
            prev = self.prev_positions.get(r.agent_id)
            if prev and prev != r.position:
                dist_delta += 1
        
        self.metrics.record_step(
            step, n_active, n_idle, n_loaded,
            ts['pending_count'], completed,
            len(self.conflict_resolution.detect_conflicts(self.agent_paths, 
                {r.agent_id: r.position for r in self.env_state.robots})),
            len(deadlocked), dist_delta
        )
    
    def _render_visualization(self, step, robot_positions, robot_directions, robot_loaded):
        """渲染可视化帧"""
        md = {
            'step': step,
            'active': sum(1 for r in self.env_state.robots if r.is_active),
            'idle': sum(1 for r in self.env_state.robots
                       if self.task_assignment.agent_assignments.get(r.agent_id, None)
                       and self.task_assignment.agent_assignments[r.agent_id].is_idle),
            'loaded': sum(1 for r in self.env_state.robots if r.has_shelf),
            'pending': len(self.task_assignment.pending_tasks),
            'completed': self.metrics.cumulative_completed,
            'throughput': self.metrics.cumulative_completed / max(step, 1) * 3600,
            'collisions': self.metrics.cumulative_collisions,
            'deadlocks': self.conflict_resolution.deadlock_count
        }
        
        density_field = self.pde_field.density if self.pde_field else None
        
        self.visualization.render_frame(
            step,
            robot_positions,
            robot_directions,
            robot_loaded,
            self.agent_paths,
            VisualizationModule.format_metrics_text(md),
            density_field
        )
    
    def run_evaluation(self, n_episodes=None):
        """运行评估"""
        if n_episodes is None:
            n_episodes = self.config.n_episodes
        print(f"\nEval: {n_episodes} episodes")
        self.initialize()
        for ep in range(n_episodes):
            self.run_episode(ep)
        self.metrics.print_final_summary()
        self.cleanup()
    
    def cleanup(self):
        """清理资源"""
        self.perception.close()
        self.visualization.close()
        print("\nAgent closed")

class MultiMethodEvaluator:
    """多方法评估器 - 用于对比不同调度策略"""
    
    def __init__(self):
        self.results = {}
    
    def evaluate_method(self, method_name, config):
        """评估单个方法"""
        print(f"\n{'='*60}")
        print(f"  Evaluating: {method_name}")
        print(f"{'='*60}")
        
        agent = CoordinatorAgent(config)
        try:
            agent.run_evaluation(config.n_episodes)
            summary = agent.metrics.get_latest_summary()
            self.results[method_name] = summary
        except Exception as e:
            print(f"  Error evaluating {method_name}: {e}")
            self.results[method_name] = None
        
        return summary
    
    def compare_methods(self, methods_configs):
        """对比多个方法"""
        print("\n" + "="*60)
        print("  MULTI-METHOD COMPARISON")
        print("="*60)
        
        for method_name, config in methods_configs.items():
            self.evaluate_method(method_name, config)
        
        # 打印对比结果
        self.print_comparison()
    
    def print_comparison(self):
        """打印对比结果"""
        print("\n" + "="*60)
        print("  COMPARISON RESULTS")
        print("="*60)
        
        headers = ["Method", "Throughput/h", "Collisions", "Orders", "Idle%"]
        print(f"  {headers[0]:<20} {headers[1]:>12} {headers[2]:>10} {headers[3]:>8} {headers[4]:>8}")
        print("  " + "-"*60)
        
        for method, summary in self.results.items():
            if summary:
                print(f"  {method:<20} {summary.throughput_per_hour:>12.1f} "
                      f"{summary.total_collisions:>10} {summary.total_orders_completed:>8} "
                      f"{summary.avg_robot_idle_rate:>8.1%}")
            else:
                print(f"  {method:<20} {'N/A':>12} {'N/A':>10} {'N/A':>8} {'N/A':>8}")
        
        print("="*60)
