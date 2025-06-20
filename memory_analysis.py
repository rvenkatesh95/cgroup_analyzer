# cgroup_analyzer/memory_analysis.py
"""
Memory performance analysis module
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import List


def analyze_memory_performance(analyzer: 'CgroupAnalyzer') -> None:
    """Memory performance analysis (if extended metrics available)"""
    if not analyzer.has_extended_metrics:
        print("Extended metrics not available - skipping memory analysis")
        return
    
    print("\n=== Memory Performance Analysis ===")
    
    fig, axes = plt.subplots(2, 2, figsize=(20, 15))
    fig.suptitle('Memory Performance Analysis', fontsize=16, fontweight='bold')
    
    # 1. Memory Usage Over Time
    ax1 = axes[0, 0]
    for cgroup in analyzer.cgroups:
        memory_current = analyzer._safe_column(cgroup, 'memory_current')
        # Convert to MB
        memory_mb = memory_current / (1024 * 1024)
        ax1.plot(analyzer.df['elapsed_sec'], memory_mb, label=cgroup, linewidth=2)
    
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('Memory Usage (MB)')
    ax1.set_title('Memory Usage Over Time')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Memory Composition
    ax2 = axes[0, 1]
    for i, cgroup in enumerate(analyzer.cgroups):
        anon_mem = analyzer._safe_column(cgroup, 'memory_anon').iloc[-1] / (1024 * 1024)
        file_mem = analyzer._safe_column(cgroup, 'memory_file').iloc[-1] / (1024 * 1024)
        kernel_mem = analyzer._safe_column(cgroup, 'memory_kernel').iloc[-1] / (1024 * 1024)
        
        bottom = 0
        if anon_mem > 0:
            ax2.bar(i, anon_mem, label='Anonymous' if i == 0 else "", alpha=0.8)
            bottom += anon_mem
        if file_mem > 0:
            ax2.bar(i, file_mem, bottom=bottom, label='File Cache' if i == 0 else "", alpha=0.8)
            bottom += file_mem
        if kernel_mem > 0:
            ax2.bar(i, kernel_mem, bottom=bottom, label='Kernel' if i == 0 else "", alpha=0.8)
    
    ax2.set_xticks(range(len(analyzer.cgroups)))
    ax2.set_xticklabels(analyzer.cgroups, rotation=45)
    ax2.set_ylabel('Memory Usage (MB)')
    ax2.set_title('Memory Composition by Type')
    ax2.legend()
    
    # 3. Memory Pressure
    ax3 = axes[1, 0]
    for cgroup in analyzer.cgroups:
        pressure_some = analyzer._safe_column(cgroup, 'memory_pressure_some_avg10')
        if pressure_some.max() > 0:
            ax3.plot(analyzer.df['elapsed_sec'], pressure_some, label=f'{cgroup} (some)', linewidth=2)
    
    ax3.set_xlabel('Time (seconds)')
    ax3.set_ylabel('Memory Pressure (avg10)')
    ax3.set_title('Memory Pressure Over Time')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. Memory Statistics Summary
    ax4 = axes[1, 1]
    mem_stats = []
    
    for cgroup in analyzer.cgroups:
        current = analyzer._safe_column(cgroup, 'memory_current').iloc[-1]
        peak = analyzer._safe_column(cgroup, 'memory_peak').iloc[-1]
        oom_events = analyzer._safe_column(cgroup, 'memory_oom_events').iloc[-1]
        
        mem_stats.append({
            'cgroup': cgroup,
            'current_mb': current / (1024 * 1024),
            'peak_mb': peak / (1024 * 1024),
            'oom_events': oom_events
        })
    
    mem_df = pd.DataFrame(mem_stats)
    x_pos = np.arange(len(mem_df))
    
    ax4.bar(x_pos - 0.2, mem_df['current_mb'], 0.4, label='Current MB', alpha=0.8)
    ax4.bar(x_pos + 0.2, mem_df['peak_mb'], 0.4, label='Peak MB', alpha=0.8)
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels(mem_df['cgroup'], rotation=45)
    ax4.set_ylabel('Memory (MB)')
    ax4.set_title('Memory Usage Summary')
    ax4.legend()
    
    plt.tight_layout()
    plt.savefig(analyzer.output_dir / 'memory_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    analyzer._print_memory_stats()