
"""数据记录与评估模块 - 科学的实验结果管理"""
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import numpy as np


class ResultsManager:
    """结果管理器 - 统一管理实验结果和日志"""
    
    def __init__(self, base_dir: str = "results"):
        self.base_dir = base_dir
        self.current_experiment = None
        self.experiment_dir = None
        os.makedirs(base_dir, exist_ok=True)
    
    def create_experiment(self, name: str = None):
        """创建新实验目录"""
        if name is None:
            name = f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.current_experiment = name
        self.experiment_dir = os.path.join(self.base_dir, name)
        os.makedirs(self.experiment_dir, exist_ok=True)
        
        # 创建子目录
        os.makedirs(os.path.join(self.experiment_dir, 'logs'), exist_ok=True)
        os.makedirs(os.path.join(self.experiment_dir, 'plots'), exist_ok=True)
        os.makedirs(os.path.join(self.experiment_dir, 'configs'), exist_ok=True)
        
        # 记录实验元信息
        meta = {
            'name': name,
            'created_at': datetime.now().isoformat(),
            'description': ''
        }
        self._save_json('experiment_meta.json', meta)
        
        print(f"[Results] 创建实验: {self.experiment_dir}")
        return self.experiment_dir
    
    def _save_json(self, filename: str, data: dict):
        """保存JSON文件"""
        path = os.path.join(self.experiment_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def save_config(self, config):
        """保存配置"""
        if self.experiment_dir:
            config_dict = asdict(config)
            self._save_json('configs/experiment_config.json', config_dict)
    
    def save_metrics(self, metrics: dict, episode: int):
        """保存Episode指标"""
        if self.experiment_dir:
            filename = f'logs/episode_{episode:03d}.json'
            self._save_json(filename, metrics)
    
    def save_summary(self, summary: dict):
        """保存实验汇总"""
        if self.experiment_dir:
            self._save_json('summary.json', summary)
    
    @staticmethod
    def load_experiment(experiment_path: str):
        """加载已有实验"""
        manager = ResultsManager()
        manager.experiment_dir = experiment_path
        manager.current_experiment = os.path.basename(experiment_path)
        
        if os.path.exists(os.path.join(experiment_path, 'experiment_meta.json')):
            with open(os.path.join(experiment_path, 'experiment_meta.json'), 'r', encoding='utf-8') as f:
                meta = json.load(f)
            manager.current_experiment = meta['name']
        
        return manager

@dataclass
class StepMetrics:
    step: int
    timestamp: float
    active_robots: int
    idle_robots: int
    loaded_robots: int
    pending_orders: int
    completed_orders_cumulative: int
    collisions_this_step: int
    deadlocks_this_step: int
    total_distance_traveled: float

@dataclass
class EpisodeMetrics:
    episode_id: int
    total_steps: int
    total_orders_completed: int
    throughput_per_hour: float
    avg_task_completion_time: float
    total_collisions: int
    total_deadlocks: int
    avg_robot_distance: float
    avg_robot_idle_rate: float
    start_time: float
    end_time: float
    duration_seconds: float

class MetricsModule:
    def __init__(self, config):
        self.config = config
        self.log_dir = os.path.join(os.getcwd(), config.log_dir)
        os.makedirs(self.log_dir, exist_ok=True)
        self.current_episode = 0
        self.step_metrics = []
        self.task_completion_times = []
        self.robot_distances = defaultdict(float)
        self.robot_idle_steps = defaultdict(int)
        self.episode_start_time = 0.0
        self.episode_summaries = []
        self.cumulative_completed = 0
        self.cumulative_collisions = 0
        self.cumulative_deadlocks = 0
        self.total_distance = 0.0
        self.current_log_file = None
        self.summary_file = os.path.join(self.log_dir, config.summary_log)
    
    def start_episode(self, episode_id):
        self.current_episode = episode_id
        self.step_metrics.clear()
        self.task_completion_times.clear()
        self.robot_distances.clear()
        self.robot_idle_steps.clear()
        self.episode_start_time = time.time()
        self.cumulative_completed = 0
        self.cumulative_collisions = 0
        self.cumulative_deadlocks = 0
        self.total_distance = 0.0
        log_name = f"{self.config.episode_log_prefix}_{episode_id:03d}.jsonl"
        self.current_log_file = os.path.join(self.log_dir, log_name)
    
    def record_step(self, step, n_active, n_idle, n_loaded, n_pending_orders,
                    n_completed, collisions=0, deadlocks=0, distance_delta=0.0):
        self.cumulative_completed = n_completed
        self.cumulative_collisions += collisions
        self.cumulative_deadlocks += deadlocks
        self.total_distance += distance_delta
        m = StepMetrics(step, time.time(), n_active, n_idle, n_loaded,
                        n_pending_orders, n_completed, collisions, deadlocks,
                        self.total_distance)
        self.step_metrics.append(m)
        if step % self.config.record_interval == 0:
            self._write_step(m)
    
    def _write_step(self, m):
        try:
            with open(self.current_log_file, 'a', encoding='utf-8') as fp:
                json.dump(asdict(m), fp, ensure_ascii=False)
                fp.write('\n')
        except:
            pass
    
    def end_episode(self, total_steps):
        end_time = time.time()
        dur_h = total_steps / 3600.0
        throughput = self.cumulative_completed / max(dur_h, 0.001)
        avg_ct = np.mean(self.task_completion_times) if self.task_completion_times else 0.0
        avg_dist = np.mean(list(self.robot_distances.values())) if self.robot_distances else 0.0
        total_idle = sum(self.robot_idle_steps.values())
        total_robot_steps = total_steps * max(len(self.robot_idle_steps), 1)
        avg_idle = total_idle / max(total_robot_steps, 1)
        
        s = EpisodeMetrics(self.current_episode, total_steps, self.cumulative_completed,
                          throughput, avg_ct, self.cumulative_collisions,
                          self.cumulative_deadlocks, avg_dist, avg_idle,
                          self.episode_start_time, end_time, end_time - self.episode_start_time)
        self.episode_summaries.append(s)
        self._save_summary()
        return s
    
    def _save_summary(self):
        try:
            with open(self.summary_file, 'w', encoding='utf-8') as fp:
                json.dump([asdict(s) for s in self.episode_summaries], fp,
                         ensure_ascii=False, indent=2)
        except:
            pass
    
    def get_latest_summary(self):
        return self.episode_summaries[-1] if self.episode_summaries else None
    
    def print_summary(self):
        s = self.get_latest_summary()
        if not s:
            return
        print(f"\n{'='*50}")
        print(f"  Episode {s.episode_id} Report")
        print(f"{'='*50}")
        print(f"  Steps:{s.total_steps}  Orders:{s.total_orders_completed}  TP:{s.throughput_per_hour:.1f}/h")
        print(f"  Col:{s.total_collisions}  DL:{s.total_deadlocks}")
        print(f"  Idle%:{s.avg_robot_idle_rate:.1%}  Time:{s.duration_seconds:.1f}s")
        print(f"{'='*50}")
    
    def print_final_summary(self):
        if not self.episode_summaries:
            return
        ts = [s.throughput_per_hour for s in self.episode_summaries]
        cs = [s.total_collisions for s in self.episode_summaries]
        os_ = [s.total_orders_completed for s in self.episode_summaries]
        print(f"\n{'='*50}")
        print(f"  All{len(self.episode_summaries)} Episodes Summary")
        print(f"{'='*50}")
        print(f"  Throughput: {np.mean(ts):.1f} ± {np.std(ts):.1f}/h")
        print(f"  Col: {np.mean(cs):.1f} ± {np.std(cs):.1f}")
        print(f"  Orders: {np.mean(os_):.1f} ± {np.std(os_):.1f}")
        print(f"{'='*50}")
