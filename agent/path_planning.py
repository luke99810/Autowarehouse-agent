
"""路径规划模块 - A* + 优先级协同规划"""
import heapq
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

DIRECTIONS = [(0, -1), (1, 0), (0, 1), (-1, 0)]

@dataclass
class PathResult:
    agent_id: int
    path: List[Tuple[int, int]]
    success: bool
    cost: float = 0.0

class TrajectoryGenerator(ABC):
    @abstractmethod
    def generate_trajectory(self, start, goal, obstacles, other_trajs=None):
        pass

class AStarGenerator(TrajectoryGenerator):
    def __init__(self, diagonal=False):
        self.diagonal = diagonal
    
    def generate_trajectory(self, start, goal, obstacles, other_trajs=None):
        return AStarPlanner(self.diagonal).find_path(start, goal, obstacles)

class DiffusionGenerator(TrajectoryGenerator):
    def generate_trajectory(self, start, goal, obstacles, other_trajs=None):
        raise NotImplementedError("第二阶段实现")

class AStarPlanner:
    def __init__(self, diagonal=False):
        self.diagonal = diagonal
        self.directions = DIRECTIONS + ([(1,-1),(1,1),(-1,1),(-1,-1)] if diagonal else [])
    
    @staticmethod
    def heuristic(a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1])
    
    def find_path(self, start, goal, obstacles, max_cost=5000):
        if start == goal:
            return []
        if start in obstacles or goal in obstacles:
            return []
        
        open_set = [(0, 0, start)]
        came_from = {}
        g_score = {start: 0}
        closed = set()
        
        while open_set:
            f, g, current = heapq.heappop(open_set)
            if current in closed:
                continue
            closed.add(current)
            
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return path
            
            for dx, dy in self.directions:
                nb = (current[0]+dx, current[1]+dy)
                if nb in closed or nb in obstacles:
                    continue
                cost = 1.414 if (dx!=0 and dy!=0) else 1.0
                tg = g + cost
                if tg > max_cost:
                    continue
                if tg < g_score.get(nb, float('inf')):
                    came_from[nb] = current
                    g_score[nb] = tg
                    h = self.heuristic(nb, goal)
                    heapq.heappush(open_set, (tg + h, tg, nb))
        return []

class ReservationTable:
    def __init__(self):
        self.reservations = {}
    
    def reserve(self, time, position, agent_id):
        self.reservations.setdefault(time, {})[position] = agent_id
    
    def reserve_path(self, path, agent_id, start_time=0):
        for t, pos in enumerate(path):
            self.reserve(start_time + t, pos, agent_id)
    
    def is_reserved(self, time, position):
        return position in self.reservations.get(time, {})
    
    def clear(self):
        self.reservations.clear()

class PrioritizedPlanner:
    def __init__(self, config):
        self.config = config
        self.astar = AStarPlanner(diagonal=config.diagonal_movement)
        self.rt = ReservationTable()
        self.time_horizon = config.time_horizon
    
    def plan(self, agent_tasks, obstacles, priorities=None):
        self.rt.clear()
        sorted_tasks = sorted(agent_tasks,
                             key=lambda x: priorities.get(x[0], 0) if priorities else x[0])
        results = {}
        
        for aid, start, goal in sorted_tasks:
            path = self._spatiotemporal_astar(start, goal, obstacles, aid)
            if path:
                self.rt.reserve_path(path, aid)
            results[aid] = PathResult(aid, path, bool(path), len(path) if path else float('inf'))
        return results
    
    def _spatiotemporal_astar(self, start, goal, obstacles, agent_id):
        if start == goal:
            return []
        
        open_set = [(0, 0, (start[0], start[1], 0))]
        came_from = {}
        cost_so_far = {(start[0], start[1], 0): 0}
        closed = set()
        
        while open_set:
            f, g, state = heapq.heappop(open_set)
            if state in closed:
                continue
            closed.add(state)
            cx, cy, ct = state
            
            if (cx, cy) == goal:
                path = []
                cur = state
                while cur in came_from:
                    x, y, t = cur
                    path.append((x, y))
                    cur = came_from[cur]
                path.reverse()
                if path and path[0] == start:
                    path.pop(0)
                return path
            
            if ct >= self.time_horizon:
                continue
            
            # Wait
            ws = (cx, cy, ct+1)
            if not self.rt.is_reserved(ct+1, (cx, cy)):
                ng = g + 0.5
                if ng < cost_so_far.get(ws, float('inf')):
                    came_from[ws] = state
                    cost_so_far[ws] = ng
                    h = AStarPlanner.heuristic((cx,cy), goal)
                    heapq.heappush(open_set, (ng+h, ng, ws))
            
            for dx, dy in DIRECTIONS:
                nx, ny, nt = cx+dx, cy+dy, ct+1
                if (nx, ny) in obstacles:
                    continue
                if nt > self.time_horizon:
                    continue
                if self.rt.is_reserved(nt, (nx, ny)):
                    continue
                
                ns = (nx, ny, nt)
                ng = g + 1.0
                if ng < cost_so_far.get(ns, float('inf')):
                    came_from[ns] = state
                    cost_so_far[ns] = ng
                    h = AStarPlanner.heuristic((nx,ny), goal)
                    heapq.heappush(open_set, (ng+h, ng, ns))
        return []

class PathPlanningModule:
    def __init__(self, config):
        self.config = config
        self.astar = AStarPlanner(diagonal=config.diagonal_movement)
        self.multi = PrioritizedPlanner(config) if config.enable_prioritized_planning else None
        self.trajectory_generator = AStarGenerator(diagonal=config.diagonal_movement)
    
    def plan_single(self, start, goal, obstacles):
        return self.trajectory_generator.generate_trajectory(start, goal, obstacles)
    
    def plan_multi(self, agent_tasks, obstacles, priorities=None):
        if self.multi:
            return self.multi.plan(agent_tasks, obstacles, priorities)
        results = {}
        for aid, start, goal in agent_tasks:
            p = self.plan_single(start, goal, obstacles)
            results[aid] = PathResult(aid, p, bool(p), len(p) if p else float('inf'))
        return results
