
"""冲突消解模块 - 碰撞检测 + 优先级仲裁"""
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class Conflict:
    agent_a: int
    agent_b: int
    conflict_position: Tuple[int, int]
    conflict_time: int
    conflict_type: str

@dataclass
class ResolutionResult:
    conflicts_detected: list
    resolved: bool
    blocked_agents: set = field(default_factory=set)
    replan_agents: set = field(default_factory=set)
    message: str = ""

class ConflictResolutionModule:
    def __init__(self, config):
        self.config = config
        self.collision_count = 0
        self.deadlock_count = 0
        self.stall_counter = defaultdict(int)
    
    def reset(self):
        self.collision_count = 0
        self.deadlock_count = 0
        self.stall_counter.clear()
    
    def detect_conflicts(self, agent_paths, agent_positions):
        conflicts = []
        occupancy = defaultdict(lambda: defaultdict(list))
        
        for aid, pos in agent_positions.items():
            occupancy[0][pos].append(aid)
        
        max_time = 0
        for aid, path in agent_paths.items():
            if not path:
                continue
            for t, pos in enumerate(path):
                occupancy[t+1][pos].append(aid)
                max_time = max(max_time, t+1)
        
        for t in range(max_time+1):
            for pos, agents in occupancy[t].items():
                if len(agents) > 1:
                    for i in range(len(agents)):
                        for j in range(i+1, len(agents)):
                            # 仅统计t=0的实际碰撞(当前位置重叠才是真碰撞)
                            if t == 0:
                                conflicts.append(Conflict(agents[i], agents[j], pos, 0, "vertex"))
        
        return conflicts
    
    def resolve(self, conflicts, agent_priorities):
        if not conflicts:
            return ResolutionResult([], True)
        
        blocked = set()
        replan = set()
        
        for c in conflicts:
            pa = agent_priorities.get(c.agent_a, 5)
            pb = agent_priorities.get(c.agent_b, 5)
            if pa < pb:
                blocked.add(c.agent_b)
            elif pb < pa:
                blocked.add(c.agent_a)
            else:
                blocked.add(c.agent_b if c.agent_a < c.agent_b else c.agent_a)
            
            if c.conflict_type == "swapping":
                replan.add(c.agent_a)
                replan.add(c.agent_b)
        
        replan.update(blocked)
        self.collision_count += len(conflicts)
        
        return ResolutionResult(conflicts, bool(blocked), blocked, replan,
                               f"检测{len(conflicts)}冲突,阻塞{len(blocked)}机器人")
    
    def detect_deadlock(self, agent_positions, prev_positions):
        deadlocked = set()
        for aid, pos in agent_positions.items():
            prev = prev_positions.get(aid)
            if prev is not None and pos == prev:
                self.stall_counter[aid] += 1
            else:
                self.stall_counter[aid] = 0
            if self.stall_counter[aid] >= self.config.deadlock_timeout:
                deadlocked.add(aid)
                self.stall_counter[aid] = 0
                self.deadlock_count += 1
        return deadlocked
    
    def get_stats(self):
        return {"collision_count": self.collision_count,
                "deadlock_count": self.deadlock_count}
