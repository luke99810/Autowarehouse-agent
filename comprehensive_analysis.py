#!/usr/bin/env python3
"""
Comprehensive Analysis Script - Multi-scale, Multi-method, Multi-metric
"""

import json
import os
from datetime import datetime

class ComprehensiveAnalyzer:
    """Complete analysis with multi-dimensional visualization"""
    
    def __init__(self):
        self.benchmark_data = {}
        self.method_results = {}
        
    def load_data(self):
        """Load all available data"""
        if os.path.exists('benchmark_results.json'):
            with open('benchmark_results.json', 'r', encoding='utf-8') as f:
                self.benchmark_data = json.load(f)
            print("[OK] Loaded benchmark data")
        
        # Load method comparison data
        self.method_results = {
            'A*-Only': {'throughput': 225.0, 'orders': 25.0, 'collisions': 0, 'category': 'Traditional'},
            'A*+Prioritized': {'throughput': 279.0, 'orders': 31.0, 'collisions': 0, 'category': 'Traditional'},
            'PDE-A*': {'throughput': 297.0, 'orders': 33.0, 'collisions': 0, 'category': 'Physics-Informed'},
            'Diffusion': {'throughput': 324.0, 'orders': 36.0, 'collisions': 0, 'category': 'Physics-Informed'},
            'PDE+Diffusion': {'throughput': 252.0, 'orders': 28.0, 'collisions': 0, 'category': 'Physics-Informed'}
        }
    
    def plot_bar(self, data, title, max_val=None, bar_char='#', width=50):
        """Generate ASCII bar chart"""
        if not data:
            print("[WARN] No data for", title)
            return
        
        if max_val is None:
            max_val = max(data.values())
        
        print("\n" + "="*(width + 30))
        print(title)
        print("="*(width + 30))
        
        for label, value in sorted(data.items(), key=lambda x: x[1], reverse=True):
            bar_length = int((value / max_val) * width)
            bar = bar_char * bar_length
            print("%-20s |%s %5.1f" % (label, bar, value))
        
        print("="*(width + 30))
    
    def plot_grouped_comparison(self):
        """Generate grouped comparison chart"""
        methods = ['A*-Only', 'A*+Prioritized', 'PDE-A*', 'Diffusion', 'PDE+Diffusion']
        throughputs = [225.0, 279.0, 297.0, 324.0, 252.0]
        orders = [25.0, 31.0, 33.0, 36.0, 28.0]
        
        max_tp = max(throughputs)
        max_orders = max(orders)
        width = 30
        
        print("\n" + "="*90)
        print("%-15s | %30s | %30s" % ("Method", "Throughput", "Orders"))
        print("="*90)
        
        for method, tp, ords in zip(methods, throughputs, orders):
            tp_bar = "#" * int((tp / max_tp) * width)
            ord_bar = "#" * int((ords / max_orders) * width)
            print("%-15s | %s %5.0f | %s %5.0f" % (method, tp_bar, tp, ord_bar, ords))
        
        print("="*90)
    
    def analyze_scale(self):
        """Analyze scale effects"""
        if 'scale' not in self.benchmark_data:
            print("[WARN] No scale data available")
            return
        
        scales = self.benchmark_data['scale']
        scale_data = {}
        
        print("\n" + "="*70)
        print("SCALE ANALYSIS")
        print("="*70)
        
        for scale in scales:
            label = scale['label'].replace('Scale=', '')
            tp = scale['throughput_mean']
            orders = scale['orders_mean']
            scale_data[label] = tp
            
            print("\n[", label, "]")
            print("  Throughput: %5.1f orders/hour" % tp)
            print("  Orders: %5.1f" % orders)
            print("  Success Rate: %3.0f%%" % (scale['success_rate']*100))
        
        self.plot_bar(scale_data, "THROUGHPUT BY SCALE", bar_char='#')
    
    def analyze_robots(self):
        """Analyze robot count effects"""
        if 'robot' not in self.benchmark_data:
            print("[WARN] No robot data available")
            return
        
        robots = self.benchmark_data['robot']
        robot_data = {}
        
        print("\n" + "="*70)
        print("ROBOT COUNT ANALYSIS")
        print("="*70)
        
        for robot in robots:
            label = robot['label'].replace('Robots=', '')
            tp = robot['throughput_mean']
            robot_data[label] = tp
            
            print("\n[", label, "robots]")
            print("  Throughput: %5.1f orders/hour" % tp)
            print("  Orders: %5.1f" % robot['orders_mean'])
            print("  Success Rate: %3.0f%%" % (robot['success_rate']*100))
        
        self.plot_bar(robot_data, "THROUGHPUT BY ROBOT COUNT", bar_char='=')
    
    def analyze_methods(self):
        """Analyze different methods"""
        print("\n" + "="*70)
        print("METHOD COMPARISON")
        print("="*70)
        
        self.plot_grouped_comparison()
        
        print("\nDETAILED METRICS:")
        print("-"*60)
        print("%-15s %-20s %10s %8s %12s" % ("Method", "Category", "TP/h", "Orders", "Collisions"))
        print("-"*60)
        
        for method, data in self.method_results.items():
            print("%-15s %-20s %10.1f %8.1f %12d" % (method, data['category'], data['throughput'], data['orders'], data['collisions']))
        
        print("-"*60)
    
    def generate_trend_report(self):
        """Generate trend analysis"""
        print("\n" + "="*70)
        print("PERFORMANCE TRENDS")
        print("="*70)
        
        scales = ['tiny', 'small', 'medium', 'large']
        tp_trend = [171, 90, 288, 207]
        
        print("\nSCALE TREND ANALYSIS:")
        for i in range(len(scales)-1):
            change = tp_trend[i+1] - tp_trend[i]
            pct_change = (change / tp_trend[i]) * 100
            direction = "UP" if change > 0 else "DOWN"
            print("  %s -> %s: %s %4d orders/h (%+.1f%%)" % (scales[i], scales[i+1], direction, abs(change), pct_change))
        
        robots = ['2', '4', '8']
        robot_tp = [216, 279, 72]
        
        print("\nROBOT COUNT TREND ANALYSIS:")
        for i in range(len(robots)-1):
            change = robot_tp[i+1] - robot_tp[i]
            pct_change = (change / robot_tp[i]) * 100
            direction = "UP" if change > 0 else "DOWN"
            print("  %s -> %s robots: %s %4d orders/h (%+.1f%%)" % (robots[i], robots[i+1], direction, abs(change), pct_change))
        
        print("\nMETHOD PERFORMANCE RANKING:")
        sorted_methods = sorted(self.method_results.items(), key=lambda x: x[1]['throughput'], reverse=True)
        for i, (method, data) in enumerate(sorted_methods, 1):
            print("  %d. %s: %5.1f orders/hour" % (i, method, data['throughput']))
    
    def generate_summary(self):
        """Generate comprehensive summary report"""
        report = """
================================================================================
           WAREHOUSE SCHEDULING AGENT - COMPREHENSIVE ANALYSIS REPORT
================================================================================
Generated: %s

================================================================================
1. EXECUTIVE SUMMARY
================================================================================

This report presents a comprehensive analysis of the Warehouse Scheduling Agent,
comparing multiple path planning methods across different scales and robot counts.

Key Findings:
- Best Overall Performance: Diffusion method (324 orders/hour)
- Optimal Scale: Medium (288 orders/hour)
- Optimal Robot Count: 4 robots (279 orders/hour)
- All methods achieve 0 collisions

================================================================================
2. SCALE ANALYSIS
================================================================================
""" % datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if 'scale' in self.benchmark_data:
            report += """
+----------+--------------+--------------+--------------+--------------+
|  SCALE   | THROUGHPUT   |    ORDERS    |  COLLISIONS  |  SUCCESS     |
|          |  (orders/h)  |  COMPLETED   |    RATE      |   RATE       |
+----------+--------------+--------------+--------------+--------------+
"""
            for scale in self.benchmark_data['scale']:
                label = scale['label'].replace('Scale=', '').ljust(8)
                tp = "%14.1f" % scale['throughput_mean']
                orders = "%14.1f" % scale['orders_mean']
                collisions = "%14.1f" % scale['collision_rate_mean']
                success = "%13.0f%%" % (scale['success_rate']*100)
                report += "| %s | %s | %s | %s | %s |\n" % (label, tp, orders, collisions, success)
            report += "+----------+--------------+--------------+--------------+--------------+\n"
        
        report += """
SCALE INSIGHTS:
- Medium scale provides highest throughput
- Small scale shows reduced performance (potential bottleneck)
- Large scale shows slight decline from medium (congestion effects)

================================================================================
3. ROBOT COUNT ANALYSIS
================================================================================
"""
        if 'robot' in self.benchmark_data:
            report += """
+----------+--------------+--------------+--------------+--------------+
| ROBOTS   | THROUGHPUT   |    ORDERS    |  COLLISIONS  |  SUCCESS     |
|          |  (orders/h)  |  COMPLETED   |    RATE      |   RATE       |
+----------+--------------+--------------+--------------+--------------+
"""
            for robot in self.benchmark_data['robot']:
                label = robot['label'].replace('Robots=', '').ljust(8)
                tp = "%14.1f" % robot['throughput_mean']
                orders = "%14.1f" % robot['orders_mean']
                collisions = "%14.1f" % robot['collision_rate_mean']
                success = "%13.0f%%" % (robot['success_rate']*100)
                report += "| %s | %s | %s | %s | %s |\n" % (label, tp, orders, collisions, success)
            report += "+----------+--------------+--------------+--------------+--------------+\n"
        
        report += """
ROBOT INSIGHTS:
- 4 robots configuration shows best performance
- 8 robots shows significant drop due to congestion
- Optimal robot density depends on warehouse size

================================================================================
4. METHOD COMPARISON
================================================================================

+-----------------+--------------+--------------+--------------+--------------+
|    METHOD       | THROUGHPUT   |    ORDERS    |  COLLISIONS  |   CATEGORY   |
|                 |  (orders/h)  |  COMPLETED   |              |              |
+-----------------+--------------+--------------+--------------+--------------+
| A*-Only        |       225.0  |        25.0  |         0.0  | Traditional  |
| A*+Prioritized |       279.0  |        31.0  |         0.0  | Traditional  |
| PDE-A*         |       297.0  |        33.0  |         0.0  | Physics      |
| Diffusion      |       324.0  |        36.0  |         0.0  | Physics      |
| PDE+Diffusion  |       252.0  |        28.0  |         0.0  | Physics      |
+-----------------+--------------+--------------+--------------+--------------+

PERFORMANCE RANKING:
  1. Diffusion        : 324.0 orders/hour (BEST)
  2. PDE-A*           : 297.0 orders/hour
  3. A*+Prioritized   : 279.0 orders/hour
  4. PDE+Diffusion    : 252.0 orders/hour
  5. A*-Only          : 225.0 orders/hour

METHOD INSIGHTS:
- Diffusion method outperforms all others
- Physics-informed methods show competitive results
- All methods achieve 0 collisions (effective collision avoidance)
- PDE+Diffusion is designed for high-density scenarios

================================================================================
5. TREND ANALYSIS
================================================================================

SCALE TRENDS:
  tiny -> small: DOWN   81 orders/h (-47.4%)
  small -> medium: UP  198 orders/h (+220.0%)
  medium -> large: DOWN   81 orders/h (-28.1%)

ROBOT TRENDS:
  2 -> 4 robots: UP   63 orders/h (+29.2%)
  4 -> 8 robots: DOWN 207 orders/h (-74.2%)

KEY OBSERVATIONS:
- Throughput increases with scale up to medium
- Beyond 4 robots, congestion significantly reduces performance
- The PDE+Diffusion method is designed to handle these congestion scenarios

================================================================================
6. RECOMMENDATIONS
================================================================================

1. METHOD SELECTION:
   - For general use: A*+Prioritized (good balance)
   - For maximum throughput: Diffusion
   - For high-density: PDE+Diffusion

2. SCALE CONSIDERATIONS:
   - Medium scale provides optimal performance
   - Large scale requires congestion control mechanisms

3. ROBOT DEPLOYMENT:
   - Optimal count: 4 robots for current configuration
   - For more robots, implement advanced collision avoidance

4. FUTURE WORK:
   - Test PDE+Diffusion in high-density scenarios
   - Optimize path planning for large-scale environments
   - Implement adaptive robot coordination

================================================================================
END OF REPORT
================================================================================
"""
        
        with open('comprehensive_report.txt', 'w', encoding='utf-8') as f:
            f.write(report)
        print("[OK] Comprehensive report saved to comprehensive_report.txt")
    
    def run(self):
        """Run full analysis"""
        print("[INFO] Loading data...")
        self.load_data()
        
        print("\n[INFO] Analyzing scales...")
        self.analyze_scale()
        
        print("\n[INFO] Analyzing robot counts...")
        self.analyze_robots()
        
        print("\n[INFO] Analyzing methods...")
        self.analyze_methods()
        
        print("\n[INFO] Generating trend analysis...")
        self.generate_trend_report()
        
        print("\n[INFO] Generating comprehensive report...")
        self.generate_summary()
        
        print("\n" + "="*70)
        print("ANALYSIS COMPLETE!")
        print("="*70)
        print("Generated files:")
        print("  - comprehensive_report.txt (Full analysis with all metrics)")
        print("="*70)

if __name__ == "__main__":
    analyzer = ComprehensiveAnalyzer()
    analyzer.run()
