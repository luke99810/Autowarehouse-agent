"""可视化模块 - 支持Matplotlib和Web模式"""
import sys as _sys
import os
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# 尝试导入matplotlib，如果失败则设置标志
try:
    import matplotlib
    if 'Agg' not in _sys.argv:
        matplotlib.use('TkAgg')
    else:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    patches = None

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

COLORS = {
    'robot_idle': '#4682B4', 'robot_loaded': '#32CD32',
    'shelf_empty': '#8B4513', 'delivery_zone': '#87CEEB',
    'path': '#FF69B4', 'floor': '#F5F5DC', 'text': '#333333',
    'grid': '#E0E0E0', 'density_low': '#E8F5E9', 'density_high': '#EF9A9A',
}

class VisualizationModule:
    def __init__(self, config):
        self.config = config
        self.fig = None
        self.ax_grid = None
        self.ax_panel = None
        self.is_running = False
        self._shelf_positions = []
        self._delivery_positions = []
        self._grid_w = 20
        self._grid_h = 11
        self._density_field = None
        
        # Web模式相关
        self.web_server = None
        self.frame_data = []
        self.current_frame = 0

        # GIF帧保存相关
        self._frame_counter = 0
        self._frame_dir = None
        self._saved_frame_paths = []
        
    def setup(self, grid_width, grid_height, shelf_positions, delivery_positions, density_field=None):
        if not self.config.enabled:
            return
        
        self._grid_w = grid_width
        self._grid_h = grid_height
        self._shelf_positions = shelf_positions
        self._delivery_positions = delivery_positions
        self._density_field = density_field

        # 初始化GIF帧保存目录
        if self.config.save_gif:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self._frame_dir = os.path.join(self.config.output_dir, f"run_{timestamp}")
            os.makedirs(self._frame_dir, exist_ok=True)
            self._frame_counter = 0
            self._saved_frame_paths = []
            print(f"[可视化] GIF帧将保存到: {self._frame_dir}")
        
        if self.config.render_mode == "web":
            self._setup_web_server()
        elif self.config.render_mode in ("matplotlib", "both"):
            if MATPLOTLIB_AVAILABLE:
                self._setup_matplotlib()
            else:
                print("[可视化] matplotlib不可用，切换到Web模式")
                self.config.render_mode = "web"
                self._setup_web_server()
        
        print(f"[可视化] 初始化完成 ({self.config.render_mode})")
    
    def _setup_matplotlib(self):
        """设置Matplotlib可视化"""
        plt.ion()
        self.fig, (self.ax_grid, self.ax_panel) = plt.subplots(1, 2, figsize=(12, 6))
        self.fig.canvas.manager.set_window_title("Warehouse Scheduling Agent")
        
        # 主网格区域
        self.ax_grid.set_xlim(-0.5, self._grid_w - 0.5)
        self.ax_grid.set_ylim(-0.5, self._grid_h - 0.5)
        self.ax_grid.set_aspect('equal')
        self.ax_grid.grid(True, alpha=0.3, color=COLORS['grid'])
        self.ax_grid.invert_yaxis()
        self.ax_grid.set_title("Warehouse Grid", fontsize=12)
        
        # 绘制静态元素
        for sx, sy in self._shelf_positions:
            self.ax_grid.add_patch(patches.Rectangle(
                (sx-0.4, sy-0.4), 0.8, 0.8,
                facecolor=COLORS['shelf_empty'], alpha=0.7, ec='black', lw=1))
        for dx, dy in self._delivery_positions:
            self.ax_grid.add_patch(patches.Rectangle(
                (dx-0.4, dy-0.4), 0.8, 0.8,
                facecolor=COLORS['delivery_zone'], alpha=0.7, ec='black', lw=1))
        
        # 指标面板
        self.ax_panel.set_axis_off()
        self.ax_panel.set_title("Metrics", fontsize=12)
        
        plt.tight_layout()
        self.is_running = True
    
    def _setup_web_server(self):
        """设置Web服务器"""
        try:
            from flask import Flask, render_template, Response, jsonify
            from flask_socketio import SocketIO, emit
            import threading
            
            self.web_app = Flask(__name__, template_folder=self._get_web_template_path())
            self.web_socketio = SocketIO(self.web_app, cors_allowed_origins="*")
            
            @self.web_app.route('/')
            def index():
                return render_template('index.html', 
                                     grid_width=self._grid_w,
                                     grid_height=self._grid_h,
                                     shelves=json.dumps(self._shelf_positions),
                                     deliveries=json.dumps(self._delivery_positions))
            
            @self.web_app.route('/frames')
            def get_frames():
                return jsonify(self.frame_data)
            
            @self.web_socketio.on('connect')
            def handle_connect():
                print("[Web] Client connected")
            
            @self.web_socketio.on('request_frame')
            def handle_request_frame(frame_id):
                if frame_id < len(self.frame_data):
                    emit('frame_data', self.frame_data[frame_id])
            
            # 启动服务器线程
            def run_server():
                self.web_socketio.run(self.web_app, host='0.0.0.0', port=5000, debug=False)
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            print("[Web] Server started at http://localhost:5000")
            
        except ImportError:
            print("[Web] Flask not installed")
            if MATPLOTLIB_AVAILABLE:
                print("[可视化] 回退到matplotlib模式")
                self.config.render_mode = "matplotlib"
                self._setup_matplotlib()
            else:
                print("[可视化] matplotlib和Flask都不可用，禁用可视化")
                self.config.enabled = False
                self.is_running = False
    
    def _get_web_template_path(self):
        """获取Web模板路径"""
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'web')
        if not os.path.exists(template_dir):
            os.makedirs(template_dir)
        return template_dir
    
    def render_frame(self, step, robot_positions, robot_directions, robot_loaded,
                     robot_paths=None, metrics_text=None, density_field=None):
        if not self.is_running or not self.config.enabled:
            return
        
        if self.config.render_mode == "web":
            self._render_web_frame(step, robot_positions, robot_directions, 
                                  robot_loaded, robot_paths, metrics_text, density_field)
        elif self.config.render_mode == "matplotlib":
            self._render_matplotlib_frame(step, robot_positions, robot_directions,
                                         robot_loaded, robot_paths, metrics_text, density_field)
        elif self.config.render_mode == "both":
            self._render_matplotlib_frame(step, robot_positions, robot_directions,
                                         robot_loaded, robot_paths, metrics_text, density_field)
            self._render_web_frame(step, robot_positions, robot_directions,
                                  robot_loaded, robot_paths, metrics_text, density_field)
    
    def _render_matplotlib_frame(self, step, robot_positions, robot_directions,
                                 robot_loaded, robot_paths, metrics_text, density_field):
        """渲染Matplotlib帧"""
        self.ax_grid.clear()
        self.ax_grid.set_xlim(-0.5, self._grid_w - 0.5)
        self.ax_grid.set_ylim(-0.5, self._grid_h - 0.5)
        self.ax_grid.set_aspect('equal')
        self.ax_grid.grid(True, alpha=0.3, color=COLORS['grid'])
        self.ax_grid.set_title(f"Step: {step}", fontsize=12)
        
        # 绘制密度场
        if density_field is not None and self.config.show_density_field:
            self._draw_density_field(density_field)
        
        # 绘制静态元素
        for sx, sy in self._shelf_positions:
            self.ax_grid.add_patch(patches.Rectangle(
                (sx-0.4, sy-0.4), 0.8, 0.8,
                facecolor=COLORS['shelf_empty'], alpha=0.7, ec='black', lw=1))
        for dx, dy in self._delivery_positions:
            self.ax_grid.add_patch(patches.Rectangle(
                (dx-0.4, dy-0.4), 0.8, 0.8,
                facecolor=COLORS['delivery_zone'], alpha=0.7, ec='black', lw=1))
        
        # 绘制路径
        if robot_paths:
            for aid, path in robot_paths.items():
                if path:
                    xs, ys = [p[0] for p in path], [p[1] for p in path]
                    self.ax_grid.plot(xs, ys, color=COLORS['path'], lw=1.5, alpha=0.6, ls='--')
        
        # 绘制机器人
        arrows = {0: (0, -0.35), 1: (0.35, 0), 2: (0, 0.35), 3: (-0.35, 0)}
        for aid, (x, y) in robot_positions.items():
            c = COLORS['robot_loaded'] if robot_loaded.get(aid) else COLORS['robot_idle']
            self.ax_grid.add_patch(patches.Circle((x, y), 0.35, fc=c, ec='black', lw=1.5, zorder=10))
            dx, dy = arrows.get(robot_directions.get(aid, 0), (0, 0))
            self.ax_grid.arrow(x, y, dx*0.6, dy*0.6, head_width=0.12, head_length=0.12,
                              fc='white', ec='white', zorder=11, lw=2)
            self.ax_grid.text(x, y-0.55, str(aid), ha='center', fontsize=7,
                             color=COLORS['text'], fontweight='bold', zorder=12)
        
        # 更新指标面板
        self.ax_panel.clear()
        self.ax_panel.set_axis_off()
        if metrics_text:
            self.ax_panel.text(0.05, 0.95, metrics_text, fontsize=10,
                              verticalalignment='top', fontfamily='monospace')
        
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(1.0 / max(self.config.fps, 1))

        # 如果启用了GIF保存，保存当前帧
        self._save_frame()
    
    def _draw_density_field(self, density_field):
        """绘制密度场热力图"""
        h, w = density_field.shape
        extent = [-0.5, w - 0.5, -0.5, h - 0.5]
        self.ax_grid.imshow(density_field, extent=extent, cmap='YlOrRd', 
                           alpha=0.3, origin='lower', vmin=0, vmax=1)

    def _save_frame(self):
        """保存当前matplotlib帧为PNG图片（用于后续合成为GIF）"""
        if not self._frame_dir or self.fig is None:
            return
        fname = os.path.join(self._frame_dir, f"frame_{self._frame_counter:04d}.png")
        self.fig.savefig(fname, dpi=100, bbox_inches='tight')
        self._saved_frame_paths.append(fname)
        self._frame_counter += 1

    def _create_gif(self):
        """将所有保存的帧合成为GIF动画"""
        if not self._frame_dir or not self._saved_frame_paths:
            print("[GIF] 没有帧可合成")
            return

        if not PIL_AVAILABLE:
            print("[GIF] Pillow不可用，无法合成GIF。帧已保存为PNG。")
            return

        try:
            frames = []
            for fname in self._saved_frame_paths:
                frames.append(PILImage.open(fname))

            if frames:
                gif_path = self.config.gif_path
                duration = int(1000 / max(self.config.fps, 1))
                frames[0].save(
                    gif_path,
                    save_all=True,
                    append_images=frames[1:],
                    duration=duration,
                    loop=0  # 无限循环
                )
                print(f"[GIF] 已保存: {gif_path} ({len(frames)} 帧, {duration}ms/帧)")
        except Exception as e:
            print(f"[GIF] 合成失败: {e}")
            print(f"[GIF] 帧文件已保存到: {self._frame_dir}")
    
    def _render_web_frame(self, step, robot_positions, robot_directions,
                          robot_loaded, robot_paths, metrics_text, density_field):
        """渲染Web帧数据"""
        frame_data = {
            'step': step,
            'robots': [
                {
                    'id': aid,
                    'x': pos[0],
                    'y': pos[1],
                    'direction': robot_directions.get(aid, 0),
                    'loaded': robot_loaded.get(aid, False)
                }
                for aid, pos in robot_positions.items()
            ],
            'paths': {
                str(aid): [{'x': p[0], 'y': p[1]} for p in path]
                for aid, path in (robot_paths or {}).items() if path
            },
            'metrics': self._parse_metrics(metrics_text),
            'density_field': density_field.tolist() if density_field is not None else None
        }
        
        self.frame_data.append(frame_data)
        
        # 发送到Web客户端
        if hasattr(self, 'web_socketio'):
            self.web_socketio.emit('new_frame', frame_data)
    
    def _parse_metrics(self, metrics_text):
        """解析指标文本为字典"""
        if not metrics_text:
            return {}
        result = {}
        for line in metrics_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip()
        return result
    
    def close(self):
        """关闭可视化"""
        self.is_running = False

        # 如果启用了GIF保存，合成GIF
        if self.config.save_gif and self._frame_dir:
            self._create_gif()

        if self.fig:
            plt.close(self.fig)

        if hasattr(self, 'web_socketio'):
            self.web_socketio.stop()
    
    @staticmethod
    def format_metrics_text(metrics):
        """格式化指标文本"""
        return '\n'.join([
            f"Step: {metrics.get('step', 0)}",
            f"活跃/空闲/载货: {metrics.get('active', 0)}/{metrics.get('idle', 0)}/{metrics.get('loaded', 0)}",
            f"订单(待/完成): {metrics.get('pending', 0)}/{metrics.get('completed', 0)}",
            f"吞吐量: {metrics.get('throughput', 0):.1f}/h",
            f"碰撞: {metrics.get('collisions', 0)}  死锁: {metrics.get('deadlocks', 0)}",
        ])

def create_web_template():
    """创建Web可视化模板"""
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'web')
    os.makedirs(template_dir, exist_ok=True)
    
    html_content = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>仓储协同调度Agent</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { display: flex; gap: 20px; padding: 20px; max-width: 1400px; margin: 0 auto; }
        .main-panel { flex: 1; background: white; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); overflow: hidden; }
        .side-panel { width: 320px; background: white; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); padding: 20px; }
        
        .header { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 20px; font-weight: 600; }
        .step-info { background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 20px; font-size: 14px; }
        
        .grid-container { position: relative; overflow: auto; }
        #grid { display: block; }
        
        .metrics-section { margin-bottom: 20px; }
        .metrics-title { font-size: 14px; font-weight: 600; color: #666; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 2px solid #eee; }
        .metric-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
        .metric-label { color: #888; font-size: 13px; }
        .metric-value { font-weight: 600; color: #333; font-size: 14px; }
        
        .stat-card { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 15px; border-radius: 12px; text-align: center; margin-bottom: 15px; }
        .stat-card.orange { background: linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%); }
        .stat-card.purple { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .stat-card.blue { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
        .stat-value { font-size: 28px; font-weight: 700; }
        .stat-label { font-size: 12px; opacity: 0.9; margin-top: 4px; }
        
        .legend { display: flex; gap: 15px; flex-wrap: wrap; margin-top: 10px; }
        .legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #666; }
        .legend-color { width: 16px; height: 16px; border-radius: 4px; }
        
        .controls { display: flex; gap: 10px; margin-top: 20px; }
        .control-btn { flex: 1; padding: 10px; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 500; }
        .control-btn.play { background: #4CAF50; color: white; }
        .control-btn.pause { background: #ff9800; color: white; }
        .control-btn.reset { background: #f44336; color: white; }
        
        .chart-container { margin-top: 20px; }
        .mini-chart { height: 100px; background: #f8f9fa; border-radius: 8px; position: relative; overflow: hidden; }
        .chart-line { position: absolute; bottom: 0; left: 0; width: 100%; height: 100%; }
        .chart-bar { display: inline-block; background: #4facfe; margin-right: 2px; border-radius: 2px; }
        
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .pulse { animation: pulse 2s infinite; }
    </style>
</head>
<body>
    <div class="container">
        <div class="main-panel">
            <div class="header">
                <h1>🏭 仓储协同调度Agent</h1>
                <div class="step-info">Step: <span id="step-counter">0</span></div>
            </div>
            <div class="grid-container">
                <canvas id="grid"></canvas>
            </div>
            <div class="legend">
                <div class="legend-item"><div class="legend-color" style="background: #4682B4;"></div> 空闲机器人</div>
                <div class="legend-item"><div class="legend-color" style="background: #32CD32;"></div> 载货机器人</div>
                <div class="legend-item"><div class="legend-color" style="background: #8B4513;"></div> 货架</div>
                <div class="legend-item"><div class="legend-color" style="background: #87CEEB;"></div> 配送区</div>
                <div class="legend-item"><div class="legend-color" style="background: #FF69B4;"></div> 路径</div>
            </div>
        </div>
        
        <div class="side-panel">
            <div class="stat-card">
                <div class="stat-value" id="stat-throughput">0.0</div>
                <div class="stat-label">吞吐量 (订单/小时)</div>
            </div>
            <div class="stat-card orange">
                <div class="stat-value" id="stat-completed">0</div>
                <div class="stat-label">已完成订单</div>
            </div>
            <div class="stat-card purple">
                <div class="stat-value" id="stat-collisions">0</div>
                <div class="stat-label">碰撞次数</div>
            </div>
            <div class="stat-card blue">
                <div class="stat-value" id="stat-deadlocks">0</div>
                <div class="stat-label">死锁次数</div>
            </div>
            
            <div class="metrics-section">
                <div class="metrics-title">📊 实时指标</div>
                <div class="metric-item"><span class="metric-label">活跃机器人</span><span class="metric-value" id="metric-active">0</span></div>
                <div class="metric-item"><span class="metric-label">空闲机器人</span><span class="metric-value" id="metric-idle">0</span></div>
                <div class="metric-item"><span class="metric-label">载货机器人</span><span class="metric-value" id="metric-loaded">0</span></div>
                <div class="metric-item"><span class="metric-label">待处理订单</span><span class="metric-value" id="metric-pending">0</span></div>
            </div>
            
            <div class="chart-container">
                <div class="metrics-title">📈 吞吐量趋势</div>
                <div class="mini-chart">
                    <div id="throughput-chart" class="chart-line"></div>
                </div>
            </div>
            
            <div class="controls">
                <button class="control-btn play" onclick="togglePlay()">▶ 播放</button>
                <button class="control-btn pause" onclick="pause()">⏸ 暂停</button>
                <button class="control-btn reset" onclick="reset()">🔄 重置</button>
            </div>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('grid');
        const ctx = canvas.getContext('2d');
        
        let gridWidth = {{ grid_width }};
        let gridHeight = {{ grid_height }};
        let shelves = JSON.parse('{{ shelves | safe }}');
        let deliveries = JSON.parse('{{ deliveries | safe }}');
        
        let robots = [];
        let paths = {};
        let densityField = null;
        let currentStep = 0;
        let isPlaying = true;
        let throughputHistory = [];
        
        const CELL_SIZE = 35;
        const PADDING = 20;
        
        function resizeCanvas() {
            canvas.width = gridWidth * CELL_SIZE + PADDING * 2;
            canvas.height = gridHeight * CELL_SIZE + PADDING * 2;
        }
        
        function drawGrid() {
            ctx.fillStyle = '#F5F5DC';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // 绘制网格线
            ctx.strokeStyle = '#E0E0E0';
            ctx.lineWidth = 1;
            for (let x = 0; x <= gridWidth; x++) {
                ctx.beginPath();
                ctx.moveTo(PADDING + x * CELL_SIZE, PADDING);
                ctx.lineTo(PADDING + x * CELL_SIZE, PADDING + gridHeight * CELL_SIZE);
                ctx.stroke();
            }
            for (let y = 0; y <= gridHeight; y++) {
                ctx.beginPath();
                ctx.moveTo(PADDING, PADDING + y * CELL_SIZE);
                ctx.lineTo(PADDING + gridWidth * CELL_SIZE, PADDING + y * CELL_SIZE);
                ctx.stroke();
            }
        }
        
        function drawDensityField() {
            if (!densityField) return;
            
            for (let y = 0; y < gridHeight; y++) {
                for (let x = 0; x < gridWidth; x++) {
                    const density = densityField[y] ? densityField[y][x] || 0 : 0;
                    if (density > 0.1) {
                        const alpha = Math.min(density * 0.6, 0.5);
                        ctx.fillStyle = `rgba(239, 154, 154, ${alpha})`;
                        ctx.fillRect(PADDING + x * CELL_SIZE, PADDING + y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
                    }
                }
            }
        }
        
        function drawShelves() {
            ctx.fillStyle = '#8B4513';
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 2;
            
            shelves.forEach(shelf => {
                const x = PADDING + shelf[0] * CELL_SIZE + CELL_SIZE * 0.1;
                const y = PADDING + shelf[1] * CELL_SIZE + CELL_SIZE * 0.1;
                const size = CELL_SIZE * 0.8;
                
                ctx.fillRect(x, y, size, size);
                ctx.strokeRect(x, y, size, size);
            });
        }
        
        function drawDeliveries() {
            ctx.fillStyle = '#87CEEB';
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 2;
            
            deliveries.forEach(del => {
                const x = PADDING + del[0] * CELL_SIZE + CELL_SIZE * 0.1;
                const y = PADDING + del[1] * CELL_SIZE + CELL_SIZE * 0.1;
                const size = CELL_SIZE * 0.8;
                
                ctx.fillRect(x, y, size, size);
                ctx.strokeRect(x, y, size, size);
            });
        }
        
        function drawPaths() {
            Object.values(paths).forEach(path => {
                if (path.length < 2) return;
                
                ctx.strokeStyle = '#FF69B4';
                ctx.lineWidth = 3;
                ctx.setLineDash([5, 5]);
                ctx.beginPath();
                
                ctx.moveTo(
                    PADDING + path[0].x * CELL_SIZE + CELL_SIZE / 2,
                    PADDING + path[0].y * CELL_SIZE + CELL_SIZE / 2
                );
                
                for (let i = 1; i < path.length; i++) {
                    ctx.lineTo(
                        PADDING + path[i].x * CELL_SIZE + CELL_SIZE / 2,
                        PADDING + path[i].y * CELL_SIZE + CELL_SIZE / 2
                    );
                }
                
                ctx.stroke();
                ctx.setLineDash([]);
            });
        }
        
        function drawRobots() {
            robots.forEach(robot => {
                const x = PADDING + robot.x * CELL_SIZE + CELL_SIZE / 2;
                const y = PADDING + robot.y * CELL_SIZE + CELL_SIZE / 2;
                const radius = CELL_SIZE * 0.35;
                
                // 机器人身体
                ctx.beginPath();
                ctx.arc(x, y, radius, 0, Math.PI * 2);
                ctx.fillStyle = robot.loaded ? '#32CD32' : '#4682B4';
                ctx.fill();
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 2;
                ctx.stroke();
                
                // 方向箭头
                const dirs = [[0, -1], [1, 0], [0, 1], [-1, 0]];
                const [dx, dy] = dirs[robot.direction];
                
                ctx.beginPath();
                ctx.moveTo(x, y);
                ctx.lineTo(
                    x + dx * radius * 0.8,
                    y + dy * radius * 0.8
                );
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 3;
                ctx.stroke();
                
                // 箭头头部
                ctx.beginPath();
                ctx.moveTo(x + dx * radius * 0.8, y + dy * radius * 0.8);
                const perp = [-dy, dx];
                ctx.lineTo(
                    x + dx * radius * 0.5 - perp[0] * radius * 0.3,
                    y + dy * radius * 0.5 - perp[1] * radius * 0.3
                );
                ctx.lineTo(
                    x + dx * radius * 0.5 + perp[0] * radius * 0.3,
                    y + dy * radius * 0.5 + perp[1] * radius * 0.3
                );
                ctx.closePath();
                ctx.fillStyle = '#fff';
                ctx.fill();
                
                // 机器人ID
                ctx.fillStyle = '#333';
                ctx.font = 'bold 12px Arial';
                ctx.textAlign = 'center';
                ctx.fillText(robot.id.toString(), x, y + radius + 12);
            });
        }
        
        function draw() {
            drawGrid();
            drawDensityField();
            drawShelves();
            drawDeliveries();
            drawPaths();
            drawRobots();
        }
        
        function updateMetrics(data) {
            if (!data.metrics) return;
            
            document.getElementById('step-counter').textContent = data.step;
            document.getElementById('stat-throughput').textContent = data.metrics['吞吐量'] || '0.0';
            document.getElementById('stat-completed').textContent = data.metrics['订单(待/完成)'] ? 
                data.metrics['订单(待/完成)'].split('/')[1] : '0';
            document.getElementById('stat-collisions').textContent = data.metrics['碰撞'] || '0';
            document.getElementById('stat-deadlocks').textContent = data.metrics['死锁'] || '0';
            
            const activeIdleLoaded = data.metrics['活跃/空闲/载货'];
            if (activeIdleLoaded) {
                const parts = activeIdleLoaded.split('/');
                document.getElementById('metric-active').textContent = parts[0] || '0';
                document.getElementById('metric-idle').textContent = parts[1] || '0';
                document.getElementById('metric-loaded').textContent = parts[2] || '0';
            }
            
            const pendingCompleted = data.metrics['订单(待/完成)'];
            if (pendingCompleted) {
                document.getElementById('metric-pending').textContent = pendingCompleted.split('/')[0] || '0';
            }
            
            // 更新吞吐量图表
            const tp = parseFloat(data.metrics['吞吐量'] || '0');
            throughputHistory.push(tp);
            if (throughputHistory.length > 20) throughputHistory.shift();
            
            updateChart();
        }
        
        function updateChart() {
            const chart = document.getElementById('throughput-chart');
            const max = Math.max(...throughputHistory, 1);
            let html = '';
            
            throughputHistory.forEach(value => {
                const height = (value / max) * 100;
                html += `<div class="chart-bar" style="height: ${height}%; width: ${100/20}%;"></div>`;
            });
            
            chart.innerHTML = html;
        }
        
        function handleNewFrame(data) {
            robots = data.robots || [];
            paths = data.paths || {};
            densityField = data.density_field;
            currentStep = data.step;
            
            updateMetrics(data);
            draw();
        }
        
        // WebSocket连接
        const socket = io();
        socket.on('new_frame', handleNewFrame);
        
        function togglePlay() {
            isPlaying = !isPlaying;
        }
        
        function pause() {
            isPlaying = false;
        }
        
        function reset() {
            currentStep = 0;
            throughputHistory = [];
            updateChart();
        }
        
        resizeCanvas();
        draw();
    </script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
</body>
</html>
    '''
    
    with open(os.path.join(template_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)

# 创建Web模板
create_web_template()
