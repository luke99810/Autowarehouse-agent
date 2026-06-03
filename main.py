#!/usr/bin/env python3
"""Warehouse Scheduling Agent - 主入口"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import get_default_config, get_test_config, get_large_scale_config, \
                   get_high_density_config, get_real_time_config
from agent.coordinator import CoordinatorAgent, MultiMethodEvaluator

def main():
    p = argparse.ArgumentParser(description="仓储协同调度Agent")
    
    # 配置选择
    g = p.add_mutually_exclusive_group()
    g.add_argument("--test", action="store_true", help="测试配置")
    g.add_argument("--large", action="store_true", help="大规模配置")
    g.add_argument("--high-density", action="store_true", help="高密度配置")
    g.add_argument("--real-time", action="store_true", help="实时配置")
    
    # 参数覆盖
    p.add_argument("-e", "--episodes", type=int, help="Episode数量")
    p.add_argument("-s", "--steps", type=int, help="每Episode步数")
    p.add_argument("-a", "--agents", type=int, help="机器人数量")
    p.add_argument("--seed", type=int, help="随机种子")
    
    # 可视化选项
    p.add_argument("--no-viz", action="store_true", help="禁用可视化")
    p.add_argument("--viz-mode", choices=["matplotlib", "web", "both"], 
                   default="web", help="可视化模式")
    p.add_argument("--fps", type=int, default=10, help="帧率")
    p.add_argument("--save-gif", action="store_true", help="保存模拟为GIF动画")
    
    # 算法配置
    p.add_argument("--algo", choices=["astar", "prioritized", "pde_astar", "diffusion", "pde_diffusion"],
                   default="prioritized", help="路径规划算法")
    p.add_argument("--no-prioritized", action="store_true", help="禁用优先级规划")
    
    # 任务分配策略
    p.add_argument("--task-strategy", choices=["nearest", "random", "load_balanced", "auction"],
                   default="nearest", help="任务分配策略")
    
    # 实验配置
    p.add_argument("--exp-name", type=str, help="实验名称")
    p.add_argument("--benchmark", action="store_true", help="运行基准测试")
    p.add_argument("--compare", action="store_true", help="多方法对比")
    
    args = p.parse_args()
    
    # 根据参数选择配置
    if args.test:
        cfg = get_test_config()
    elif args.large:
        cfg = get_large_scale_config()
    elif args.high_density:
        cfg = get_high_density_config()
    elif args.real_time:
        cfg = get_real_time_config()
    else:
        cfg = get_default_config()
    
    # 覆盖参数
    if args.episodes:
        cfg.n_episodes = args.episodes
    if args.steps:
        cfg.warehouse.max_steps = args.steps
    if args.agents:
        cfg.warehouse.n_agents = args.agents
        cfg.warehouse.request_queue_size = args.agents
    if args.seed:
        cfg.seed = args.seed
    if args.no_viz:
        cfg.visualization.enabled = False
    cfg.visualization.render_mode = args.viz_mode
    cfg.visualization.fps = args.fps
    if args.save_gif:
        cfg.visualization.save_gif = True
    # matplotlib 模式下自动启用 GIF 保存
    if args.viz_mode in ("matplotlib", "both"):
        cfg.visualization.save_gif = True
    cfg.path_planning.algorithm = args.algo
    cfg.task_assignment.strategy = args.task_strategy
    if args.no_prioritized:
        cfg.path_planning.enable_prioritized_planning = False
    if args.exp_name:
        cfg.experiment_name = args.exp_name
    
    # 打印配置信息
    print(f"{'='*60}")
    print(f"  Warehouse Scheduling Agent v2.0")
    print(f"{'='*60}")
    print(f"  配置: {cfg.experiment_name}")
    print(f"  场景: {cfg.warehouse.layout_size}")
    print(f"  机器人: {cfg.warehouse.n_agents}")
    print(f"  步数: {cfg.warehouse.max_steps}")
    print(f"  Episodes: {cfg.n_episodes}")
    print(f"  算法: {cfg.path_planning.algorithm}")
    print(f"  任务策略: {cfg.task_assignment.strategy}")
    print(f"  可视化: {'ON' if cfg.visualization.enabled else 'OFF'} "
          f"({cfg.visualization.render_mode})")
    print(f"{'='*60}")
    
    # 运行模式
    if args.compare:
        run_comparison(cfg)
    elif args.benchmark:
        run_benchmark(cfg)
    else:
        run_single_method(cfg)

def run_single_method(config):
    """运行单个方法"""
    agent = CoordinatorAgent(config)
    try:
        agent.run_evaluation(config.n_episodes)
    except KeyboardInterrupt:
        print("\n用户中断")
        agent.cleanup()

def run_comparison(base_config):
    """多方法对比"""
    evaluator = MultiMethodEvaluator()
    
    methods = {
        "A*-Only": get_method_config(base_config, "astar"),
        "A*+Prioritized": get_method_config(base_config, "prioritized"),
        "PDE-A*": get_method_config(base_config, "pde_astar"),
        "Diffusion": get_method_config(base_config, "diffusion"),
        "PDE+Diffusion": get_method_config(base_config, "pde_diffusion"),
    }
    
    evaluator.compare_methods(methods)

def get_method_config(base_config, algorithm):
    """创建特定算法的配置"""
    import copy
    cfg = copy.deepcopy(base_config)
    cfg.path_planning.algorithm = algorithm
    cfg.experiment_name = f"{base_config.experiment_name}-{algorithm}"
    return cfg

def run_benchmark(config):
    """运行基准测试"""
    from agent.metrics import MetricsModule
    import json
    import time
    
    results = []
    scenarios = [
        {"name": "小规模", "scale": "small", "agents": 4},
        {"name": "中等规模", "scale": "medium", "agents": 6},
        {"name": "大规模", "scale": "medium", "agents": 8},
    ]
    
    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"  基准测试: {scenario['name']}")
        print(f"{'='*60}")
        
        cfg = get_scenario_config(config, scenario)
        agent = CoordinatorAgent(cfg)
        
        try:
            agent.run_evaluation(cfg.n_episodes)
            summary = agent.metrics.get_latest_summary()
            
            results.append({
                "scenario": scenario["name"],
                "scale": scenario["scale"],
                "agents": scenario["agents"],
                "throughput": summary.throughput_per_hour,
                "collisions": summary.total_collisions,
                "orders": summary.total_orders_completed,
                "idle_rate": summary.avg_robot_idle_rate,
                "time": summary.duration_seconds,
            })
        except Exception as e:
            print(f"  错误: {e}")
    
    # 保存结果
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = f"benchmark_{timestamp}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"  基准测试完成")
    print(f"  结果已保存到: {output_path}")
    print(f"{'='*60}")
    
    # 打印汇总表
    print("\n  基准测试汇总")
    print("  " + "-"*60)
    print(f"  {'场景':<10} {'规模':<8} {'机器人':<6} {'吞吐量':>10} {'碰撞':>8} {'订单':>8}")
    print("  " + "-"*60)
    for r in results:
        print(f"  {r['场景']:<10} {r['scale']:<8} {r['agents']:<6} "
              f"{r['throughput']:>10.1f} {r['collisions']:>8} {r['orders']:>8}")
    print("  " + "-"*60)

def get_scenario_config(base_config, scenario):
    """创建场景配置"""
    import copy
    cfg = copy.deepcopy(base_config)
    cfg.warehouse.layout_size = scenario["scale"]
    cfg.warehouse.n_agents = scenario["agents"]
    cfg.warehouse.request_queue_size = scenario["agents"]
    cfg.experiment_name = f"benchmark-{scenario['name']}"
    return cfg

if __name__ == "__main__":
    main()
