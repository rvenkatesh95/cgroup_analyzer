# cgroup_analyzer/pressure_analysis.py
"""
System pressure analysis module
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import List


def analyze_system_pressure(analyzer: 'CgroupAnalyzer') -> None:
    """System pressure analysis"""
    if not analyzer.has_extended_metrics:
        print("Extended metrics not available - skipping pressure analysis")
        return
    
    print("\n=== System Pressure Analysis ===")
    
    fig, axes = plt.subplots(1, 2, figsize=(20, 8))
    fig.suptitle('System Pressure Analysis', fontsize=16, fontweight='bold')
    
    # CPU Pressure
    ax1 = axes[0]
    for cgroup in analyzer.cgroups:
        cpu_pressure_some = analyzer._safe_column(cgroup, 'cpu_pressure_some_avg10')
        cpu_pressure_full = analyzer._safe_column(cgroup, 'cpu_pressure_full_avg10')
        
        if cpu_pressure_some.max() > 0:
            ax1.plot(analyzer.df['elapsed_sec'], cpu_pressure_some, 
                    label=f'{cgroup} (some)', linewidth=2)
        if cpu_pressure_full.max() > 0:
            ax1.plot(analyzer.df['elapsed_sec'], cpu_pressure_full, 
                    label=f'{cgroup} (full)', linewidth=2, linestyle='--')
    
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('CPU Pressure (avg10)')
    ax1.set_title('CPU Pressure Over Time')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Memory Pressure
    ax2 = axes[1]
    for cgroup in analyzer.cgroups:
        mem_pressure_some = analyzer._safe_column(cgroup, 'memory_pressure_some_avg10')
        mem_pressure_full = analyzer._safe_column(cgroup, 'memory_pressure_full_avg10')
        
        if mem_pressure_some.max() > 0:
            ax2.plot(analyzer.df['elapsed_sec'], mem_pressure_some, 
                    label=f'{cgroup} (some)', linewidth=2)
        if mem_pressure_full.max() > 0:
            ax2.plot(analyzer.df['elapsed_sec'], mem_pressure_full, 
                    label=f'{cgroup} (full)', linewidth=2, linestyle='--')
    
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('Memory Pressure (avg10)')
    ax2.set_title('Memory Pressure Over Time')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(analyzer.output_dir / 'pressure_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()