"""
仓储协同调度Agent - 配置文件
基于「仓储协同调度Agent设计文档Version 1.0 – Pilot」
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class WarehouseConfig:
    """仓库环境配置"""
    layout_size: str = "small"  # tiny, small, medium, large
    n_agents: int = 4
    request_queue_size: int = 4
    observation_radius: int = 1
    max_steps: int = 2000
    collision_protocol: str = "max_movement_priority"  # max_movement_priority, loaded_first, round_robin
    allow_diagonal: bool = False

@dataclass
class TaskAssignmentConfig:
    strategy: str = "nearest"  # nearest, random, load_balanced, auction
    order_generation_interval: int = 5
    max_pending_orders: int = 10
    enable_preemption: bool = False
    preemption_threshold: float = 0.8  # 优先级高于此值时可抢占

@dataclass
class PathPlanningConfig:
    algorithm: str = "astar"  # astar, prioritized, pde_astar, diffusion, pde_diffusion
    enable_prioritized_planning: bool = True
    max_path_length: int = 100
    diagonal_movement: bool = False
    time_horizon: int = 50
    
    # PDE参数 - 优化后的参数设置
    diffusion_coef: float = 0.12      # 增加扩散系数，使密度传播更快
    convection_coef: float = 0.20     # 增加对流系数
    density_weight: float = 1.5       # 降低密度权重，避免过度绕路
    source_strength: float = 0.3      # 降低源强度，避免局部密度过高
    
    # Diffusion参数 - 优化扰动策略
    n_diffusion_steps: int = 5         # 减少扩散步骤
    n_samples: int = 2                # 减少采样数，提高效率
    temperature: float = 0.15         # 降低温度，减少扰动幅度
    perturbation_probability: float = 0.3  # 降低扰动概率
    smoothness_weight: float = 0.1    # 增加平滑度权重

@dataclass
class ConflictResolutionConfig:
    loaded_priority: int = 3
    empty_priority: int = 2
    waiting_priority: int = 1
    max_replan_attempts: int = 3
    deadlock_timeout: int = 20
    resolution_strategy: str = "priority"  # priority, backtracking, negotiation

@dataclass
class VisualizationConfig:
    enabled: bool = True
    render_mode: str = "web"  # matplotlib, web, both
    fps: int = 10
    window_size: tuple = (1200, 800)
    show_metrics_panel: bool = True
    show_density_field: bool = True
    save_gif: bool = False
    gif_path: str = "simulation.gif"
    output_dir: str = "frames"

@dataclass
class MetricsConfig:
    log_format: str = "jsonl"
    log_dir: str = "logs"
    episode_log_prefix: str = "episode"
    summary_log: str = "summary.json"
    record_interval: int = 10
    enable_tensorboard: bool = False
    tensorboard_dir: str = "tb_logs"

@dataclass
class BenchmarkConfig:
    enabled: bool = False
    methods_to_compare: List[str] = field(default_factory=lambda: [
        "A*-Only", 
        "A*+Prioritized", 
        "PDE-A*", 
        "Diffusion", 
        "PDE+Diffusion"
    ])
    scenarios: List[Dict[str, int]] = field(default_factory=lambda: [
        {"scale": "small", "agents": 4},
        {"scale": "small", "agents": 6},
        {"scale": "medium", "agents": 8},
    ])
    runs_per_method: int = 3
    steps_per_run: int = 1000

@dataclass
class AgentConfig:
    warehouse: WarehouseConfig = field(default_factory=WarehouseConfig)
    task_assignment: TaskAssignmentConfig = field(default_factory=TaskAssignmentConfig)
    path_planning: PathPlanningConfig = field(default_factory=PathPlanningConfig)
    conflict_resolution: ConflictResolutionConfig = field(default_factory=ConflictResolutionConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    n_episodes: int = 10
    seed: int = 42
    experiment_name: str = "default_experiment"

def get_default_config() -> AgentConfig:
    return AgentConfig()

def get_test_config() -> AgentConfig:
    config = AgentConfig()
    config.warehouse.max_steps = 200
    config.n_episodes = 2
    config.visualization.fps = 30
    return config

def get_large_scale_config() -> AgentConfig:
    config = AgentConfig()
    config.warehouse.layout_size = "medium"
    config.warehouse.n_agents = 8
    config.warehouse.request_queue_size = 8
    config.warehouse.max_steps = 5000
    return config

def get_high_density_config() -> AgentConfig:
    """高密度场景配置"""
    config = AgentConfig()
    config.warehouse.layout_size = "large"
    config.warehouse.n_agents = 12
    config.warehouse.request_queue_size = 12
    config.warehouse.max_steps = 5000
    config.path_planning.algorithm = "pde_diffusion"
    config.path_planning.enable_prioritized_planning = True
    return config

def get_real_time_config() -> AgentConfig:
    """实时场景配置"""
    config = AgentConfig()
    config.warehouse.max_steps = 1000
    config.n_episodes = 5
    config.visualization.fps = 20
    config.path_planning.time_horizon = 30
    return config
