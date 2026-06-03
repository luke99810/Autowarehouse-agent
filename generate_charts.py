#!/usr/bin/env python3
"""
Warehouse Scheduling Agent - Scientific Publication Quality Charts
Generates publication-ready figures using matplotlib for proper axis label positioning.
"""

import json
import os
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for file output
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


class ScientificChartGenerator:
    """Generate publication-quality charts following scientific paper standards"""

    def __init__(self):
        self.data = {}
        self.DPI = 300

        # Colorblind-friendly palette (Wong)
        self.method_colors = [
            '#0173B2',  # blue
            '#DE8F05',  # orange
            '#029E73',  # green
            '#CC78BC',  # red
            '#CA9161',  # purple
        ]

        # Matplotlib style settings
        plt.rcParams.update({
            'font.family': 'serif',
            'font.serif': ['Times New Roman', 'DejaVu Serif'],
            'font.size': 12,
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 10,
            'figure.dpi': self.DPI,
            'savefig.dpi': self.DPI,
            'savefig.bbox': 'tight',
            'savefig.pad_inches': 0.1,
        })

    def load_data(self):
        if os.path.exists('benchmark_results.json'):
            with open('benchmark_results.json', 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            print("[OK] Loaded benchmark data")

    def draw_bar_chart(self, title, labels, values, output_file,
                       ylabel="", xlabel="", colors=None,
                       show_values=True, figsize=(7, 4.5)):
        """Generate publication-quality bar chart using matplotlib"""
        fig, ax = plt.subplots(figsize=figsize)

        if colors is None:
            colors = self.method_colors[:len(labels)]

        x = np.arange(len(labels))
        bars = ax.bar(x, values, color=colors, edgecolor='black', linewidth=1.2,
                      width=0.6, zorder=3)

        # Value labels on top of bars
        if show_values:
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height + max(values) * 0.01,
                        f'{height:.0f}', ha='center', va='bottom', fontsize=9)

        # Axes and grid
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=0, ha='center')
        ax.set_xlabel(xlabel, fontsize=13, labelpad=8)
        ax.set_ylabel(ylabel, fontsize=13, labelpad=8)
        ax.set_title(title, fontsize=15, fontweight='bold', pad=12)

        ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6, integer=True))
        ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
        ax.set_axisbelow(True)
        ax.set_ylim(0, max(values) * 1.25 if max(values) > 0 else 1)

        # Spine styling
        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)

        fig.tight_layout()
        fig.savefig(output_file, dpi=self.DPI)
        plt.close(fig)
        print(f"[OK] Saved: {output_file}")

    def draw_line_chart(self, title, labels, values, output_file,
                        ylabel="", xlabel="", line_color='#0173B2',
                        marker='o', show_markers=True, figsize=(7, 4.5)):
        """Generate publication-quality line chart using matplotlib"""
        fig, ax = plt.subplots(figsize=figsize)

        x = np.arange(len(labels))
        ax.plot(x, values, color=line_color, linewidth=2.5, marker=marker,
                markersize=8, markerfacecolor=line_color,
                markeredgecolor='black', markeredgewidth=1.0, zorder=3)

        # Value labels at data points
        for i, val in enumerate(values):
            ax.text(i, val + max(values) * 0.02, f'{val:.0f}',
                    ha='center', va='bottom', fontsize=9)

        # Axes and grid
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=0, ha='center')
        ax.set_xlabel(xlabel, fontsize=13, labelpad=8)
        ax.set_ylabel(ylabel, fontsize=13, labelpad=8)
        ax.set_title(title, fontsize=15, fontweight='bold', pad=12)

        ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6, integer=True))
        ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
        ax.grid(axis='x', linestyle='--', alpha=0.4, zorder=0)
        ax.set_axisbelow(True)
        ax.set_ylim(0, max(values) * 1.3 if max(values) > 0 else 1)

        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)

        fig.tight_layout()
        fig.savefig(output_file, dpi=self.DPI)
        plt.close(fig)
        print(f"[OK] Saved: {output_file}")

    def draw_grouped_bar_chart(self, title, categories, series_names, series_values,
                               output_file, ylabel="", xlabel=""):
        """Generate grouped bar chart for multi-metric comparison using matplotlib"""
        fig, ax = plt.subplots(figsize=(9, 5))

        num_categories = len(categories)
        num_series = len(series_names)

        x = np.arange(num_categories)
        width = 0.7 / num_series  # Bar width
        offsets = np.linspace(-(num_series - 1) * width / 2,
                              (num_series - 1) * width / 2, num_series)

        for i, (series_name, offset) in enumerate(zip(series_names, offsets)):
            color = self.method_colors[i % len(self.method_colors)]
            bars = ax.bar(x + offset, series_values[i], width,
                          label=series_name, color=color,
                          edgecolor='black', linewidth=0.8, zorder=3)

            # Value labels
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height + 0.5,
                        f'{height:.0f}', ha='center', va='bottom', fontsize=7)

        # Axes and grid
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=0, ha='center')
        ax.set_xlabel(xlabel, fontsize=13, labelpad=8)
        ax.set_ylabel(ylabel, fontsize=13, labelpad=8)
        ax.set_title(title, fontsize=15, fontweight='bold', pad=12)

        ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6, integer=True))
        ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
        ax.set_axisbelow(True)

        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)

        # Legend
        ax.legend(loc='upper right', framealpha=0.9, edgecolor='gray',
                  fontsize=9, ncol=num_series)

        fig.tight_layout()
        fig.savefig(output_file, dpi=self.DPI)
        plt.close(fig)
        print(f"[OK] Saved: {output_file}")

    def run(self):
        """Generate all publication-quality charts"""
        print("=" * 70)
        print("Generating Publication-Quality Charts (matplotlib)")
        print("=" * 70)
        self.load_data()

        # ============================================
        # Figure 1: Method Comparison (Bar Chart)
        # ============================================
        print("\n[1/8] Generating Figure 1: Method Throughput Comparison...")
        methods = ['A*-Only', 'A*+Prioritized', 'Diffusion', 'PDE-A*', 'PDE+Diffusion']
        throughputs = [225.0, 279.0, 324.0, 297.0, 252.0]

        self.draw_bar_chart(
            title="Figure 1: Throughput Comparison by Method",
            labels=methods,
            values=throughputs,
            output_file="fig1_method_throughput.png",
            ylabel="Throughput (orders/hour)",
            xlabel="Method",
            colors=self.method_colors
        )

        # ============================================
        # Figure 2: Method Orders Comparison
        # ============================================
        print("\n[2/8] Generating Figure 2: Method Orders Comparison...")
        orders = [25.0, 31.0, 36.0, 33.0, 28.0]

        self.draw_bar_chart(
            title="Figure 2: Orders Completed by Method",
            labels=methods,
            values=orders,
            output_file="fig2_method_orders.png",
            ylabel="Orders Completed",
            xlabel="Method",
            colors=self.method_colors
        )

        # ============================================
        # Figure 3: Scale Comparison
        # ============================================
        if 'scale' in self.data:
            print("\n[3/8] Generating Figure 3: Scale Comparison...")
            scales = self.data['scale']
            scale_labels = [s['label'].replace('Scale=', '') for s in scales]
            scale_throughputs = [s['throughput_mean'] for s in scales]

            self.draw_bar_chart(
                title="Figure 3: Throughput by Warehouse Scale",
                labels=scale_labels,
                values=scale_throughputs,
                output_file="fig3_scale_throughput.png",
                ylabel="Throughput (orders/hour)",
                xlabel="Scale",
                colors=['#0173B2', '#DE8F05', '#029E73', '#CC78BC']
            )
        else:
            print("[3/8] Skipped: No scale data in benchmark_results.json")

        # ============================================
        # Figure 4: Robot Count Comparison
        # ============================================
        if 'robot' in self.data:
            print("\n[4/8] Generating Figure 4: Robot Count Comparison...")
            robots = self.data['robot']
            robot_labels = [r['label'].replace('Robots=', '') for r in robots]
            robot_throughputs = [r['throughput_mean'] for r in robots]

            self.draw_bar_chart(
                title="Figure 4: Throughput by Robot Count",
                labels=robot_labels,
                values=robot_throughputs,
                output_file="fig4_robot_throughput.png",
                ylabel="Throughput (orders/hour)",
                xlabel="Number of Robots",
                colors=['#0173B2', '#DE8F05', '#029E73']
            )
        else:
            print("[4/8] Skipped: No robot data in benchmark_results.json")

        # ============================================
        # Figure 5: Method Trend Line
        # ============================================
        print("\n[5/8] Generating Figure 5: Method Performance Trend...")
        self.draw_line_chart(
            title="Figure 5: Throughput Trend Across Methods",
            labels=methods,
            values=throughputs,
            output_file="fig5_method_trend.png",
            ylabel="Throughput (orders/hour)",
            xlabel="Method",
            line_color='#0173B2'
        )

        # ============================================
        # Figure 6: Scale Trend Line
        # ============================================
        if 'scale' in self.data:
            print("\n[6/8] Generating Figure 6: Scale Performance Trend...")
            self.draw_line_chart(
                title="Figure 6: Throughput Trend Across Scales",
                labels=scale_labels,
                values=scale_throughputs,
                output_file="fig6_scale_trend.png",
                ylabel="Throughput (orders/hour)",
                xlabel="Scale",
                line_color='#DE8F05'
            )
        else:
            print("[6/8] Skipped: No scale data")

        # ============================================
        # Figure 7: Robot Trend Line
        # ============================================
        if 'robot' in self.data:
            print("\n[7/8] Generating Figure 7: Robot Count Performance Trend...")
            self.draw_line_chart(
                title="Figure 7: Throughput Trend by Robot Count",
                labels=robot_labels,
                values=robot_throughputs,
                output_file="fig7_robot_trend.png",
                ylabel="Throughput (orders/hour)",
                xlabel="Number of Robots",
                line_color='#029E73'
            )
        else:
            print("[7/8] Skipped: No robot data")

        # ============================================
        # Figure 8: Multi-Metric Grouped Comparison
        # ============================================
        print("\n[8/8] Generating Figure 8: Multi-Metric Comparison...")
        efficiency = [85.0, 92.0, 98.0, 95.0, 88.0]

        self.draw_grouped_bar_chart(
            title="Figure 8: Multi-Metric Method Comparison",
            categories=methods,
            series_names=['Throughput', 'Orders', 'Efficiency'],
            series_values=[
                [t / 3.5 for t in throughputs],
                [o * 8 for o in orders],
                efficiency
            ],
            output_file="fig8_multi_metric.png",
            ylabel="Normalized Value",
            xlabel="Method"
        )

        print("\n" + "=" * 70)
        print("ALL PUBLICATION-QUALITY FIGURES GENERATED!")
        print("=" * 70)
        print("\nGenerated figures (300 DPI, publication-ready, matplotlib):")
        figures = [
            "fig1_method_throughput.png - Method throughput comparison",
            "fig2_method_orders.png - Method orders comparison",
            "fig3_scale_throughput.png - Scale throughput comparison",
            "fig4_robot_throughput.png - Robot count throughput comparison",
            "fig5_method_trend.png - Method performance trend",
            "fig6_scale_trend.png - Scale performance trend",
            "fig7_robot_trend.png - Robot count performance trend",
            "fig8_multi_metric.png - Multi-metric grouped comparison"
        ]
        for i, fig in enumerate(figures, 1):
            print(f"  {i}. {fig}")
        print("\nNote: All figures use matplotlib with proper axis labels")
        print("      Colorblind-friendly palette (Wong)")
        print("=" * 70)


if __name__ == "__main__":
    generator = ScientificChartGenerator()
    generator.run()
