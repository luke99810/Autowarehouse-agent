
"""任务分配模块 - 启发式最近距离匹配"""
import numpy as np
from typing import Dict, List, Tuple, Optional

class Task:
    __slots__ = ('task_id','shelf_position','delivery_position',
                 'assigned_agent','status','created_at','completed_at')
    def __init__(self, task_id, shelf_position, delivery_position, created_at=0):
        self.task_id = task_id
        self.shelf_position = shelf_position
        self.delivery_position = delivery_position
        self.assigned_agent = None
        self.status = "pending"
        self.created_at = created_at
        self.completed_at = None

class RobotAssignment:
    __slots__ = ('agent_id','current_task','phase')
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.current_task = None
        self.phase = "idle"
    
    @property
    def is_idle(self):
        return self.phase == "idle" and self.current_task is None
    
    @property
    def is_loaded(self):
        return self.phase == "moving_to_delivery"

class TaskAssignmentModule:
    def __init__(self, config):
        self.config = config
        self.task_counter = 0
        self.pending_tasks = []
        self.active_tasks = {}
        self.completed_tasks = []
        self.agent_assignments = {}
        self.shelf_positions = []
        self.delivery_positions = []
        self.order_gen_counter = 0
        self._assigned_shelves = set()  # 已被分配的货架位置
    
    def initialize(self, n_agents):
        self.agent_assignments = {i: RobotAssignment(i) for i in range(n_agents)}
        self.pending_tasks.clear()
        self.active_tasks.clear()
        self.completed_tasks.clear()
        self.task_counter = 0
        print(f"[TaskAssign] init: {n_agents}机器人")
    
    def set_environment_layout(self, shelf_positions, delivery_positions):
        self.shelf_positions = list(shelf_positions)
        self.delivery_positions = list(delivery_positions)
    
    def reset(self):
        self.task_counter = 0
        self.pending_tasks.clear()
        self.active_tasks.clear()
        self.completed_tasks.clear()
        for a in self.agent_assignments.values():
            a.current_task = None
            a.phase = "idle"
        self.order_gen_counter = 0
        self._assigned_shelves.clear()
    
    def generate_order(self, timestamp):
        if len(self.pending_tasks) >= self.config.max_pending_orders:
            return None
        if not self.shelf_positions or not self.delivery_positions:
            return None
        si = np.random.randint(0, len(self.shelf_positions))
        di = np.random.randint(0, len(self.delivery_positions))
        task = Task(self.task_counter,
                    self.shelf_positions[si],
                    self.delivery_positions[di],
                    timestamp)
        self.task_counter += 1
        self.pending_tasks.append(task)
        return task
    
    def assign_tasks(self, robot_positions, robot_states, timestamp):
        self.order_gen_counter += 1
        if self.order_gen_counter >= self.config.order_generation_interval:
            self.order_gen_counter = 0
            self.generate_order(timestamp)
        
        new_assignments = {}
        idle_agents = [aid for aid, st in robot_states.items()
                      if st == "idle" and self.agent_assignments.get(aid, RobotAssignment(aid)).is_idle]
        
        if not idle_agents or not self.pending_tasks:
            return new_assignments
        
        to_remove = []
        for aid in idle_agents:
            if not self.pending_tasks:
                break
            apos = robot_positions.get(aid)
            if apos is None:
                continue
            
            best_task, best_dist = None, float('inf')
            for task in self.pending_tasks:
                if task in to_remove:
                    continue
                # 跳过已被分配货架的任务
                if task.shelf_position in self._assigned_shelves:
                    continue
                d = abs(apos[0]-task.shelf_position[0]) + abs(apos[1]-task.shelf_position[1])
                if d < best_dist:
                    best_dist, best_task = d, task
            
            if best_task:
                best_task.assigned_agent = aid
                best_task.status = "assigned"
                self.agent_assignments[aid].current_task = best_task
                self.agent_assignments[aid].phase = "moving_to_pickup"
                new_assignments[aid] = best_task
                self._assigned_shelves.add(best_task.shelf_position)  # 标记货架已被分配
                to_remove.append(best_task)
        
        for task in to_remove:
            self.pending_tasks.remove(task)
            self.active_tasks[task.task_id] = task
        
        return new_assignments
    
    def update_task_progress(self, agent_id, position, has_shelf, timestamp):
        a = self.agent_assignments.get(agent_id)
        if not a or not a.current_task:
            return None
        task = a.current_task
        
        if a.phase == "moving_to_pickup" and position == task.shelf_position:
            a.phase = "picking_up"
            return "at_pickup"
        elif a.phase == "picking_up" and has_shelf:
            a.phase = "moving_to_delivery"
            task.status = "in_delivery"
            return "pickup_completed"
        elif a.phase == "moving_to_delivery" and position == task.delivery_position:
            a.phase = "delivering"
            return "at_delivery"
        elif a.phase == "delivering" and not has_shelf:
            task.status = "completed"
            task.completed_at = timestamp
            self.completed_tasks.append(task)
            self.active_tasks.pop(task.task_id, None)
            self._assigned_shelves.discard(task.shelf_position)  # 释放货架
            a.current_task = None
            a.phase = "idle"
            return "delivery_completed"
        return None
    
    def get_task_target(self, agent_id):
        a = self.agent_assignments.get(agent_id)
        if not a or not a.current_task:
            return None
        if a.phase == "moving_to_pickup":
            return a.current_task.shelf_position
        elif a.phase == "picking_up":
            return a.current_task.shelf_position  # stay at shelf to load
        elif a.phase == "moving_to_delivery":
            return a.current_task.delivery_position
        elif a.phase == "delivering":
            return a.current_task.delivery_position  # stay at delivery to unload
        return None
    
    def get_robot_priority(self, agent_id):
        a = self.agent_assignments.get(agent_id)
        if not a:
            return 4
        return {"moving_to_delivery": 1, "picking_up": 2,
                "delivering": 2, "moving_to_pickup": 3, "idle": 4}.get(a.phase, 4)
    
    def get_summary(self):
        return {"pending_count": len(self.pending_tasks),
                "active_count": len(self.active_tasks),
                "completed_count": len(self.completed_tasks),
                "total_generated": self.task_counter}
