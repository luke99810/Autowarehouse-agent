# Warehouse Agent — 多机器人仓储协同调度

基于 **PDE 密度场 + A\*/扩散** 的多机器人仓储协同调度 Agent，支持传统 A\* 与物理启发式 PDE 方法的多维度对比评估。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)

## 核心特性

- **5 种路径规划算法**：A\*-Only / A\*+Prioritized / PDE-A\* / Diffusion / PDE+Diffusion
- **PDE 密度场建模**：基于对流-扩散方程的实时密度场，引导全局路径决策
- **实时 2D 可视化**：Matplotlib 实时渲染仓库网格 + 机器人 + 路径 + 密度场热力图
- **Web 可视化**：Flask + Socket.IO 浏览器端实时展示（可选）
- **GIF 动画导出**：模拟过程自动录制为 GIF 动画
- **科研级图表**：300 DPI 论文发表级对比图（8 张），Wong 色盲友好配色
- **完整基准测试**：多规模、多机器人数、多方法的系统对比

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 快速测试（200 步 × 2 轮，无可视化）
python main.py --test --no-viz

# 默认评估（2000 步 × 10 轮，含可视化）
python main.py

# 大规模测试
python main.py --large --no-viz

# 运行基准测试（5 种方法全对比）
python benchmark.py

# 生成科研图表
python generate_charts.py
```

## 路径规划方法

| 方法 | 类型 | 说明 | 吞吐量 (orders/h) |
|------|------|------|:---:|
| **A\*-Only** | 传统 | 标准 A\* 最短路径，无协同 | 225 |
| **A\*+Prioritized** | 传统+协同 | 时空 A\* + 预留表协同 | 279 |
| **Diffusion** | 物理启发式 | 密度偏置随机扰动生成轨迹 | 324 |
| **PDE-A\*** | 物理启发式 | A\* 中加入密度场惩罚项 | 297 |
| **PDE+Diffusion** | 混合 | PDE 引导 + 扩散多样性 | 252 |

> 吞吐量基于 2000 步 × 10 轮的平均值，4 机器人，中等规模场景。

## 架构

```
Agent 主循环:
  感知 → 任务分配 → PDE 场更新 → 路径规划 → 冲突消解 → 动作执行 → 可视化/记录
```

### 模块说明

```
warehouse_agent/
├── main.py                  # CLI 主入口
├── config.py                # 全局配置（dataclass，支持 5 种预设）
├── benchmark.py             # 多方法基准测试
├── generate_charts.py       # 科研级图表生成（8 张，300 DPI）
├── analysis.py              # JSONL 日志分析
├── comprehensive_analysis.py # 综合文本分析
├── enhanced_analysis.py     # 增强分析（含 PNG 图表）
├── trend_analysis.py        # 趋势与效率分析
├── requirements.txt         # Python 依赖
├── agent/
│   ├── coordinator.py       # 主协调器（核心工作流）
│   ├── perception.py        # 环境感知模块
│   ├── simulated_env.py     # 简化模拟仓库环境
│   ├── task_assignment.py   # 启发式任务分配
│   ├── path_planning.py     # A* / 优先级协同规划
│   ├── pde_planner.py       # PDE 密度场 + 扩散路径规划
│   ├── conflict_resolution.py # 时空冲突检测 + 仲裁
│   ├── visualization.py     # Matplotlib / Web 可视化 + GIF 导出
│   └── metrics.py           # 指标记录（JSONL）+ 汇总
└── web/
    └── index.html           # Web 可视化前端
```

## 可视化

### Matplotlib 模式（默认）
实时 2D 渲染：仓库网格、货架、配送区、机器人（含载货状态）、规划路径、密度场热力图

### Web 模式
```python
config.visualization.render_mode = "web"
```
启动 Flask 服务器，浏览器访问 `http://localhost:5000`

### GIF 导出
```python
config.visualization.save_gif = True
config.visualization.gif_path = "output.gif"
```
模拟结束后自动合成 GIF 动画

## 基准测试

```bash
# 运行 5 种方法 × 多规模 × 多机器人数的完整对比
python benchmark.py
```

结果输出：
- `benchmark_results.json` — 结构化对比数据
- `method_comparison.json` — 方法统计汇总

## 指标

- 吞吐量 (orders/hour)
- 订单完成数
- 碰撞次数 / 碰撞率
- 死锁次数
- 机器人空闲率
- 平均任务完成时间

## 许可证

MIT License © 2026 宿心 (Wang Fengzhou)
