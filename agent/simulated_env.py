
"""简化模拟仓库环境"""
import numpy as np
from typing import Dict, List, Tuple, Optional

class SimulatedWarehouse:
    ACTION_TURN_LEFT = 0
    ACTION_TURN_RIGHT = 1
    ACTION_FORWARD = 2
    ACTION_LOAD_UNLOAD = 3
    
    # Scale presets: (grid_width, grid_height, n_shelves, delivery_zones_count)
    SCALE_PRESETS = {
        "tiny":   (8, 6, 2, 1),
        "small":  (20, 11, 4, 2),
        "medium": (30, 15, 8, 3),
        "large":  (40, 20, 12, 4),
    }
    
    def __init__(self, grid_width=20, grid_height=11, n_agents=4,
                 n_shelves=4, max_steps=2000, seed=None, scale=None):
        # Apply scale preset if specified
        if scale and scale in self.SCALE_PRESETS:
            gw, gh, ns, _ = self.SCALE_PRESETS[scale]
            grid_width, grid_height, n_shelves = gw, gh, ns
        
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.n_agents = n_agents
        self.n_shelves = n_shelves
        self.max_steps = max_steps
        self._scale = scale
        self.possible_agents = [f"agent_{i}" for i in range(n_agents)]
        self.agents = []
        self.shelf_positions = []
        self.delivery_zones = []
        self.grid = None
        self.request_queue = []
        self.completed_requests = 0
        self.request_queue_size = n_shelves
        self.current_step = 0
        self.rng = np.random.RandomState(seed)
        self._init_layout()
    
    def _init_layout(self):
        self.grid = np.zeros((self.grid_height, self.grid_width), dtype=np.int32)
        self.shelf_positions = []
        self.agents = []
        
        # Shelves in middle column, spaced evenly
        sc = self.grid_width // 2
        margin = 2
        available = self.grid_height - 2 * margin
        for i in range(self.n_shelves):
            row = margin + int((i + 0.5) * available / max(self.n_shelves, 1))
            pos = (sc, row)
            self.shelf_positions.append(pos)
            self.grid[row, sc] = 2
        
        # Delivery zones on right side, spaced evenly
        self.delivery_zones = []
        n_delivery = max(1, self.grid_height // 5)
        for i in range(n_delivery):
            dy = 1 + int((i + 0.5) * (self.grid_height - 2) / n_delivery)
            pos = (self.grid_width - 1, dy)
            self.delivery_zones.append(pos)
            self.grid[dy, self.grid_width - 1] = 4
        
        # Robots start on left side, spread vertically
        margin = 1
        available = self.grid_height - 2 * margin
        for i in range(self.n_agents):
            rx = 1 + (i % 2)
            ry = margin + int((i + 0.5) * available / max(self.n_agents, 1))
            agent = {'id': i, 'x': rx, 'y': ry,
                     'dir': self.rng.randint(0, 4),
                     'carrying_shelf': None, 'active': True}
            self.agents.append(agent)
            self.grid[ry, rx] = 3
    
    def reset(self, seed=None):
        if seed is not None:
            self.rng = np.random.RandomState(seed)
        self.current_step = 0
        self.completed_requests = 0
        self.request_queue = list(range(self.n_shelves))
        self.rng.shuffle(self.request_queue)
        self.request_queue = self.request_queue[:self.request_queue_size]
        self._init_layout()
        obs = {f"agent_{i}": {} for i in range(self.n_agents)}
        return obs, {}
    
    def step(self, actions):
        rewards = {name: 0.0 for name in self.possible_agents}
        terminated = {name: False for name in self.possible_agents}
        truncated = {name: False for name in self.possible_agents}
        
        for agent_name, action in actions.items():
            aid = int(agent_name.split('_')[1])
            agent = self.agents[aid]
            if not agent['active']:
                continue
            
            if action == 0:  # Turn Left
                agent['dir'] = (agent['dir'] - 1) % 4
            elif action == 1:  # Turn Right
                agent['dir'] = (agent['dir'] + 1) % 4
            elif action == 2:  # Forward
                dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][agent['dir']]
                nx, ny = agent['x'] + dx, agent['y'] + dy
                if self._is_valid(nx, ny) and not self._has_robot(nx, ny, aid):
                    self.grid[agent['y'], agent['x']] = 0
                    agent['x'] = nx
                    agent['y'] = ny
                    self.grid[ny, nx] = 3
            elif action == 3:  # Load/Unload
                pos = (agent['x'], agent['y'])
                if agent['carrying_shelf'] is not None:
                    if pos in self.delivery_zones:
                        agent['carrying_shelf'] = None
                        self.completed_requests += 1
                        rewards[agent_name] = 1.0
                else:
                    for sid, spos in enumerate(self.shelf_positions):
                        if spos == pos:
                            agent['carrying_shelf'] = sid
                            if sid in self.request_queue:
                                self.request_queue.remove(sid)
                            break
        
        # 若请求队列为空，自动补充
        if not self.request_queue:
            self.request_queue = list(range(self.n_shelves))
            self.rng.shuffle(self.request_queue)
            self.request_queue = self.request_queue[:self.request_queue_size]
        
        self.current_step += 1
        all_done = self.current_step >= self.max_steps
        for name in self.possible_agents:
            truncated[name] = all_done
        
        obs = {f"agent_{i}": {} for i in range(self.n_agents)}
        info = {'completed': self.completed_requests}
        return obs, rewards, terminated, truncated, info
    
    def _is_valid(self, x, y):
        return 0 <= x < self.grid_width and 0 <= y < self.grid_height
    
    def _has_robot(self, x, y, exclude_id):
        for a in self.agents:
            if a['id'] != exclude_id and a['x'] == x and a['y'] == y and a['active']:
                return True
        return False
    
    def close(self):
        pass
