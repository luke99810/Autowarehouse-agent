
"""
PDE-Based Planners - Physics-informed trajectory generation
================================================================
Implements the Phase 2 research direction from the design document:

1. PDEDensityField: Convection-Diffusion PDE for robot density evolution
   ∂ρ/∂t = D·∇²ρ - v·∇ρ + S
   where: D = diffusivity, v = velocity field, S = source (tasks)

2. PDEGuidedAStar: A* with PDE density as heuristic penalty
   f(n) = g(n) + h(n) + λ·ρ(n,t)
   
3. PDEDiffusionPlanner: Density-conditioned trajectory sampling
   (simplified score-based diffusion)
"""

import numpy as np
import heapq
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from agent.path_planning import PathResult, DIRECTIONS, AStarPlanner

# ============================================================
# PDE Density Field Model
# ============================================================
class PDEDensityField:
    """
    2D Convection-Diffusion PDE on warehouse grid.
    
    ∂ρ/∂t = D·∇²ρ - v·∇ρ + S
    
    Discretized with forward Euler + central differences.
    """
    
    def __init__(self, grid_w: int, grid_h: int,
                 diffusion_coef: float = 0.08,
                 convection_coef: float = 0.15,
                 source_strength: float = 0.5,
                 decay_rate: float = 0.02):
        self.grid_w = grid_w
        self.grid_h = grid_h
        self.D = diffusion_coef      # Diffusion coefficient
        self.C = convection_coef     # Convection coefficient
        self.S0 = source_strength    # Source strength at task locations
        self.decay = decay_rate      # Natural decay
        
        # State fields
        self.density = np.zeros((grid_h, grid_w), dtype=np.float32)
        self.velocity_x = np.zeros((grid_h, grid_w), dtype=np.float32)
        self.velocity_y = np.zeros((grid_h, grid_w), dtype=np.float32)
        
        # History for analysis
        self.density_history = []
        self.max_density = 1.0
    
    def update(self, robot_positions: List[Tuple[int, int]],
               robot_directions: List[int],
               shelf_positions: List[Tuple[int, int]],
               delivery_positions: List[Tuple[int, int]],
               dt: float = 0.1) -> np.ndarray:
        """
        One step of PDE evolution.
        
        Args:
            robot_positions: current (x,y) of all robots
            robot_directions: direction index (0-3) for each robot
            shelf_positions: shelf locations (task sources)
            delivery_positions: delivery locations (sinks)
            dt: time step for PDE integration
        """
        h, w = self.density.shape
        
        # 1. Build velocity field from robot movements
        self.velocity_x.fill(0)
        self.velocity_y.fill(0)
        dir_map = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
        
        for (rx, ry), d in zip(robot_positions, robot_directions):
            if 0 <= rx < w and 0 <= ry < h:
                vx, vy = dir_map.get(d, (0, 0))
                # Gaussian spread of velocity influence
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        ny, nx = ry + dy, rx + dx
                        if 0 <= nx < w and 0 <= ny < h:
                            weight = np.exp(-(dx*dx + dy*dy) / 2.0)
                            self.velocity_x[ny, nx] += vx * weight * 0.3
                            self.velocity_y[ny, nx] += vy * weight * 0.3
        
        # 2. Source term: tasks generate density
        source = np.zeros_like(self.density)
        for sx, sy in shelf_positions:
            if 0 <= sx < w and 0 <= sy < h:
                source[sy, sx] = self.S0
                # Spread source influence
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        ny, nx = sy + dy, sx + dx
                        if 0 <= nx < w and 0 <= ny < h:
                            source[ny, nx] += self.S0 * 0.3
        
        # 3. Sink: delivery zones absorb density
        sink = np.ones_like(self.density)
        for dx_pos, dy_pos in delivery_positions:
            if 0 <= dx_pos < w and 0 <= dy_pos < h:
                sink[dy_pos, dx_pos] = 0.3  # Strong sink
        
        # 4. Finite difference: ∂ρ/∂t = D∇²ρ - v·∇ρ + S - γρ
        rho = self.density
        
        # Laplacian (∇²ρ) with central differences
        laplacian = np.zeros_like(rho)
        laplacian[1:-1, 1:-1] = (
            rho[2:, 1:-1] + rho[:-2, 1:-1] +
            rho[1:-1, 2:] + rho[1:-1, :-2] -
            4 * rho[1:-1, 1:-1]
        )
        
        # Advection (-v·∇ρ) with upwind scheme
        advection = np.zeros_like(rho)
        for y in range(1, h-1):
            for x in range(1, w-1):
                vx = self.velocity_x[y, x]
                vy = self.velocity_y[y, x]
                # Upwind for x
                if vx > 0:
                    dphidx = (rho[y, x] - rho[y, x-1])
                else:
                    dphidx = (rho[y, x+1] - rho[y, x])
                # Upwind for y
                if vy > 0:
                    dphidy = (rho[y, x] - rho[y-1, x])
                else:
                    dphidy = (rho[y+1, x] - rho[y, x])
                advection[y, x] = -(vx * dphidx + vy * dphidy) * self.C
        
        # Combine terms
        drho_dt = (
            self.D * laplacian +
            advection +
            source -
            self.decay * rho
        )
        
        # Euler step
        rho_new = rho + dt * drho_dt
        
        # Apply sink
        rho_new *= sink
        
        # Clamp
        rho_new = np.clip(rho_new, 0, 1.0)
        
        # Boundary conditions: zero at edges
        rho_new[0, :] = 0
        rho_new[-1, :] = 0
        rho_new[:, 0] = 0
        rho_new[:, -1] = 0
        
        self.density = rho_new
        self.max_density = max(self.max_density, rho_new.max())
        
        # Store history (every 10 steps)
        if len(self.density_history) == 0 or len(self.density_history) % 10 == 0:
            self.density_history.append(rho_new.copy())
        
        return rho_new
    
    def get_density(self, x: int, y: int) -> float:
        """Get density at (x,y), normalized to [0,1]."""
        if 0 <= x < self.grid_w and 0 <= y < self.grid_h:
            return self.density[y, x]
        return 1.0
    
    def get_density_penalty(self, x: int, y: int, time_horizon: int = 5) -> float:
        """Get congestion penalty including predicted future density."""
        base = self.get_density(x, y)
        # Simple prediction: density diffuses
        future_penalty = 0
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                nx, ny = x + dx, y + dy
                future_penalty += self.get_density(nx, ny) * 0.1
        return base + future_penalty
    
    def reset(self):
        """Reset the density field."""
        self.density.fill(0)
        self.velocity_x.fill(0)
        self.velocity_y.fill(0)
        self.density_history.clear()
        self.max_density = 1.0


# ============================================================
# PDE-Guided A* Planner
# ============================================================
class PDEGuidedAStar:
    """
    A* search with PDE density field as heuristic penalty.
    
    f(n) = g(n) + h(n) + λ * density_penalty(n)
    
    This naturally routes robots away from congested areas,
    achieving decentralized congestion control through physics.
    """
    
    def __init__(self, pde_field: PDEDensityField, lambda_density: float = 2.0):
        self.pde = pde_field
        self.lambda_d = lambda_density
        self.directions = DIRECTIONS
    
    def heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
    
    def find_path(self, start: Tuple[int, int], goal: Tuple[int, int],
                  obstacles: Set[Tuple[int, int]],
                  max_cost: float = 5000) -> List[Tuple[int, int]]:
        """PDE-guided A* search."""
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
                nb = (current[0] + dx, current[1] + dy)
                if nb in closed or nb in obstacles:
                    continue
                
                # Base cost = 1
                tg = g + 1.0
                if tg > max_cost:
                    continue
                
                if tg < g_score.get(nb, float('inf')):
                    came_from[nb] = current
                    g_score[nb] = tg
                    # Add PDE density to heuristic (guides away from congestion)
                    density_penalty = self.pde.get_density_penalty(nb[0], nb[1])
                    h = self.heuristic(nb, goal) + self.lambda_d * density_penalty
                    heapq.heappush(open_set, (tg + h, tg, nb))
        return []


# ============================================================
# Simplified Diffusion-Based Trajectory Generator
# ============================================================
class PerturbedAStarPlanner:
    """
    Perturbed A* with PDE density guidance.
    
    Generates diverse trajectories by:
    1. Running A* for a base path
    2. Adding density-biased random perturbations at waypoints
    3. Selecting the best valid variant
    
    This approximates diffusion model behavior (stochastic trajectory 
    generation conditioned on PDE density field) without the full 
    denoising cost. Suitable for real-time multi-robot coordination.
    
    Reference: DGD framework - discrete MAPF solver as guide, 
    diffusion for smoothing in continuous space.
    """
    
    def __init__(self, pde_field, n_variants=2, perturbation_scale=0.8, 
                 density_weight=1.0, perturbation_prob=0.2):
        self.pde = pde_field
        self.n_variants = n_variants
        self.perturbation_scale = perturbation_scale
        self.density_weight = density_weight
        self.perturbation_prob = perturbation_prob
        self.astar = AStarPlanner(diagonal=False)
        self.directions = DIRECTIONS
    
    def generate_trajectory(self, start, goal, obstacles,
                           other_trajectories=None):
        # 1. Base A* path
        base = self.astar.find_path(start, goal, obstacles)
        if not base:
            return []
        
        # If no PDE guidance available, return base path
        if self.pde is None:
            return base
        
        # 2. Generate variants with density-biased perturbations
        best_path = base
        best_score = self._score(base)
        
        for _ in range(self.n_variants):
            variant = self._perturb(base, obstacles)
            if variant:
                score = self._score(variant)
                if score < best_score:
                    best_score = score
                    best_path = variant
        
        return best_path
    
    def _perturb(self, base, obstacles):
        """Add density-avoiding perturbations at waypoints."""
        if len(base) < 3:
            return base
        
        result = []
        for i, (x, y) in enumerate(base):
            if i == 0 or i == len(base) - 1:
                result.append((x, y))
                continue
            
            # Only perturb with certain probability
            if np.random.random() > self.perturbation_prob:
                result.append((x, y))
                continue
            
            # Try neighboring cells, prefer low-density
            candidates = [(x, y)]
            for dx, dy in self.directions:
                nx, ny = x + dx, y + dy
                if (nx, ny) not in obstacles:
                    candidates.append((nx, ny))
            
            # Score candidates by density (lower is better)
            best = min(candidates, 
                      key=lambda c: self.pde.get_density(c[0], c[1]) * self.density_weight
                                   + 0.8 * abs(c[0]-x) + 0.8 * abs(c[1]-y))
            result.append(best)
        
        return result
    
    def _score(self, path):
        """Score path (lower = better): density + length + smoothness."""
        score = len(path) * 0.2  # Length is most important
        for x, y in path:
            score += self.pde.get_density(x, y) * self.density_weight
        # Smoothness
        for i in range(1, len(path) - 1):
            dx1 = path[i][0] - path[i-1][0]
            dy1 = path[i][1] - path[i-1][1]
            dx2 = path[i+1][0] - path[i][0]
            dy2 = path[i+1][1] - path[i][1]
            if dx1 != dx2 or dy1 != dy2:
                score += 0.1  # Reduced smoothness penalty
        return score


# Alias for backward compatibility
class DiffusionPathPlanner(PerturbedAStarPlanner):
    """
    Simplified diffusion planner using Perturbed A*.
    In production, replace with a trained neural score network.
    """
    def __init__(self, pde_field, n_diffusion_steps=5, n_samples=2, temperature=0.15,
                 density_weight=1.0, perturbation_prob=0.2):
        super().__init__(
            pde_field, 
            n_variants=n_samples, 
            perturbation_scale=temperature * 5,
            density_weight=density_weight,
            perturbation_prob=perturbation_prob
        )
