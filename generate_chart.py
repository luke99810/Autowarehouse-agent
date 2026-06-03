"""
Simple comparison visualization - generates ASCII and PNG charts
"""

# Data from benchmark results
methods = ['A*-Only', 'A*+Prioritized', 'PDE-A*', 'Diffusion', 'PDE+Diffusion']
throughputs = [225.0, 279.0, 297.0, 324.0, 252.0]

# Generate ASCII bar chart
print("\n" + "="*60)
print("Throughput Comparison (orders/hour)")
print("="*60)

max_tp = max(throughputs)
scale = 50 / max_tp  # Scale bars to 50 characters max

for method, tp in zip(methods, throughputs):
    bar_length = int(tp * scale)
    bar = "█" * bar_length
    print(f"{method:15} |{bar} {tp:.0f}")

print("="*60)

# Try to generate PNG chart
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['#4facfe', '#00f2fe', '#ff6b6b', '#feca57', '#5f27cd']
    bars = ax.bar(methods, throughputs, color=colors)
    
    ax.set_title('Warehouse Agent - Multi-Method Throughput Comparison', fontsize=14, fontweight='bold')
    ax.set_ylabel('Throughput (orders/hour)', fontsize=12)
    ax.set_xlabel('Method', fontsize=12)
    ax.grid(axis='y', alpha=0.3)
    ax.tick_params(axis='x', rotation=15)
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 5,
                f'{height:.0f}', ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    plt.savefig('method_comparison.png', dpi=150, bbox_inches='tight')
    print("\n[OK] Chart saved to method_comparison.png")
    
except Exception as e:
    print(f"\n[INFO] matplotlib not available: {e}")
    print("Using ASCII chart above.")

print("\nComparison complete!")
