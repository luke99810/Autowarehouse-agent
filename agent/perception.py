
"""环境感知模块 - D-RWARE环境封装"""
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass

ACTION_TURN_LEFT = 0
ACTION_TURN_RIGHT = 1
ACTION_FORWARD = 2
ACTION_LOAD_UNLOAD = 3

DIRECTION_DELTA = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}

@dataclass
class RobotState:
    agent_id: int
    position: Tuple[int, int]
    direction: int
    has_shelf: bool
    is_active: bool = True

@dataclass  
class ShelfState:
    shelf_id: int
    position: Tuple[int, int]
    is_requested: bool = False
    is_being_carried: bool = False

@dataclass
class Order:
    order_id: int
    shelf_position: Tuple[int, int]
    delivery_position: Tuple[int, int]
    status: str = "pending"

@dataclass
class EnvironmentState:
    grid_width: int
    grid_height: int
    robots: List[RobotState]
    shelves: List[ShelfState]
    pending_orders: List[Order]
    active_orders: List[Order]
    completed_orders: List[Order]
    grid_layout: np.ndarray
    timestamp: int = 0

class PerceptionModule:
    """环境感知模块 - 支持D-RWARE和模拟环境"""
    
    def __init__(self, config):
        self.config = config
        self.env = None
        self.agent_ids = []
        self.n_agents = config.n_agents
        self.max_steps = config.max_steps
        self.current_step = 0
        self.episode_done = False
        self.grid = None
        self.shelf_list = []
        self.delivery_list = []
        
    def initialize(self):
        self._init_simulated_env()
        
    def _init_simulated_env(self):
        from agent.simulated_env import SimulatedWarehouse
        scale = getattr(self.config, 'layout_size', None)
        self.env = SimulatedWarehouse(
            grid_width=20, grid_height=11,
            n_agents=self.config.n_agents,
            n_shelves=self.config.request_queue_size,
            max_steps=self.config.max_steps,
            scale=scale if scale and scale != "small" else None,
        )
        self.agent_ids = list(range(self.config.n_agents))
        self.n_agents = self.config.n_agents
        
        # 获取布局信息
        self.shelf_list = self.env.shelf_positions
        self.delivery_list = self.env.delivery_zones
        print(f"[Perception] Simulated env ready: {self.n_agents}机器人")
        
    def reset(self, seed=None):
        if self.env is None:
            self.initialize()
        obs, info = self.env.reset(seed=seed)
        self.current_step = 0
        self.episode_done = False
        return self._extract_state()
    
    def step(self, actions):
        if self.episode_done:
            return self._extract_state()
        
        env_actions = {}
        for aid, action in actions.items():
            name = f"agent_{aid}" if isinstance(aid, int) else aid
            env_actions[name] = action
        
        obs, reward, terminated, truncated, info = self.env.step(env_actions)
        self.current_step += 1
        
        if self.current_step >= self.max_steps:
            self.episode_done = True
        if any(terminated.values()):
            self.episode_done = True
            
        return self._extract_state()
    
    def _extract_state(self):
        robots = []
        for i, agent in enumerate(self.env.agents):
            robots.append(RobotState(
                agent_id=i,
                position=(agent['x'], agent['y']),
                direction=agent['dir'],
                has_shelf=agent['carrying_shelf'] is not None,
                is_active=True,
            ))
        
        shelves = []
        for sid, pos in enumerate(self.env.shelf_positions):
            requested = sid in self.env.request_queue
            shelves.append(ShelfState(
                shelf_id=sid,
                position=pos,
                is_requested=requested,
            ))
        
        grid = np.copy(self.env.grid) if hasattr(self.env, 'grid') else np.zeros((11, 20), dtype=np.int32)
        
        return EnvironmentState(
            grid_width=self.env.grid_width,
            grid_height=self.env.grid_height,
            robots=robots,
            shelves=shelves,
            pending_orders=[],
            active_orders=[],
            completed_orders=[],
            grid_layout=grid,
            timestamp=self.current_step,
        )
    
    def close(self):
        if self.env:
            try:
                self.env.close()
            except:
                pass
