# cgroup_analyzer/cpu_analysis.py
"""
CPU performance analysis module
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import List


def analyze_cpu_performance(analyzer: 'CgroupAnalyzer') -> None:
    """Comprehensive CPU performance analysis"""
    print("\n=== CPU Performance Analysis ===")
    
    fig, axes = plt.subplots(3, 2, figsize=(20, 20))
    fig.suptitle('CPU Performance Analysis', fontsize=16, fontweight='bold')
    
    # 1. CPU Usage Over Time
    ax1 = axes[0, 0]
    for cgroup in analyzer.cgroups:
        usage = analyzer._safe_column(cgroup, 'cpu_usage_usec')
        # Calculate usage rate (microseconds per second)
        usage_rate = usage.diff() / analyzer.df['elapsed_sec'].diff() / 1000  # Convert to milliseconds/second
        usage_rate = usage_rate.rolling(window=50, center=True).mean()  # Smooth the data
        ax1.plot(analyzer.df['elapsed_sec'], usage_rate, label=cgroup, linewidth=2, alpha=0.8)
    
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('CPU Usage Rate (ms/sec)')
    ax1.set_title('CPU Usage Rate Over Time')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. CPU Throttling Analysis
    ax2 = axes[0, 1]
    throttle_data = []
    
    for cgroup in analyzer.cgroups:
        nr_throttled = analyzer._safe_column(cgroup, 'cpu_nr_throttled')
        throttled_time = analyzer._safe_column(cgroup, 'cpu_throttled_usec')
        
        if nr_throttled.max() > 0:
            throttle_rate = nr_throttled.diff().fillna(0)
            throttle_data.append({
                'cgroup': cgroup,
                'total_throttles': nr_throttled.iloc[-1],
                'total_throttled_ms': throttled_time.iloc[-1] / 1000,
                'avg_throttle_rate': throttle_rate.mean()
            })
    
    if throttle_data:
        throttle_df = pd.DataFrame(throttle_data)
        bars = ax2.bar(throttle_df['cgroup'], throttle_df['total_throttles'])
        ax2.set_ylabel('Total Throttling Events')
        ax2.set_title('CPU Throttling by Cgroup')
        ax2.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar, value in zip(bars, throttle_df['total_throttles']):
            if value > 0:
                ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        f'{int(value)}', ha='center', va='bottom')
    else:
        ax2.text(0.5, 0.5, 'No CPU throttling detected', transform=ax2.transAxes,
                ha='center', va='center', fontsize=12)
        ax2.set_title('CPU Throttling Analysis')
    
    # 3. CPU User vs System Time
    ax3 = axes[1, 0]
    for cgroup in analyzer.cgroups:
        user_time = analyzer._safe_column(cgroup, 'cpu_user_usec')
        system_time = analyzer._safe_column(cgroup, 'cpu_system_usec')
        
        # Calculate rates
        user_rate = user_time.diff() / analyzer.df['elapsed_sec'].diff() / 1000
        system_rate = system_time.diff() / analyzer.df['elapsed_sec'].diff() / 1000
        
        user_rate = user_rate.rolling(window=30).mean()
        system_rate = system_rate.rolling(window=30).mean()
        
        ax3.plot(analyzer.df['elapsed_sec'], user_rate, label=f'{cgroup} (user)', linewidth=2)
        ax3.plot(analyzer.df['elapsed_sec'], system_rate, label=f'{cgroup} (system)', linewidth=2, linestyle='--')
    
    ax3.set_xlabel('Time (seconds)')
    ax3.set_ylabel('CPU Time Rate (ms/sec)')
    ax3.set_title('User vs System CPU Time')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. CPU Efficiency Metrics
    ax4 = axes[1, 1]
    efficiency_data = []
    
    for cgroup in analyzer.cgroups:
        usage = analyzer._safe_column(cgroup, 'cpu_usage_usec')
        user_time = analyzer._safe_column(cgroup, 'cpu_user_usec')
        system_time = analyzer._safe_column(cgroup, 'cpu_system_usec')
        
        total_cpu = user_time + system_time
        
        if total_cpu.iloc[-1] > 0:
            user_ratio = (user_time.iloc[-1] / total_cpu.iloc[-1]) * 100
            system_ratio = (system_time.iloc[-1] / total_cpu.iloc[-1]) * 100
            
            efficiency_data.append({
                'cgroup': cgroup,
                'user_pct': user_ratio,
                'system_pct': system_ratio
            })
    
    if efficiency_data:
        eff_df = pd.DataFrame(efficiency_data)
        x_pos = np.arange(len(eff_df))
        
        ax4.bar(x_pos, eff_df['user_pct'], label='User CPU %', alpha=0.8)
        ax4.bar(x_pos, eff_df['system_pct'], bottom=eff_df['user_pct'], 
               label='System CPU %', alpha=0.8)
        
        ax4.set_xticks(x_pos)
        ax4.set_xticklabels(eff_df['cgroup'], rotation=45)
        ax4.set_ylabel('CPU Time Distribution (%)')
        ax4.set_title('CPU Time Distribution by Cgroup')
        ax4.legend()
    
    # 5. CPU Burst Analysis
    ax5 = axes[2, 0]
    burst_data = []
    
    for cgroup in analyzer.cgroups:
        nr_bursts = analyzer._safe_column(cgroup, 'cpu_nr_bursts')
        burst_time = analyzer._safe_column(cgroup, 'cpu_burst_usec')
        
        if nr_bursts.max() > 0:
            burst_data.append({
                'cgroup': cgroup,
                'total_bursts': nr_bursts.iloc[-1],
                'total_burst_ms': burst_time.iloc[-1] / 1000,
                'avg_burst_duration': burst_time.iloc[-1] / max(nr_bursts.iloc[-1], 1) / 1000
            })
    
    if burst_data:
        burst_df = pd.DataFrame(burst_data)
        bars = ax5.bar(burst_df['cgroup'], burst_df['total_bursts'])
        ax5.set_ylabel('Total Burst Events')
        ax5.set_title('CPU Burst Events by Cgroup')
        ax5.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar, value in zip(bars, burst_df['total_bursts']):
            if value > 0:
                ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        f'{int(value)}', ha='center', va='bottom')
                
        # Add a twin axis for average burst duration
        ax5_twin = ax5.twinx()
        ax5_twin.plot(burst_df['cgroup'], burst_df['avg_burst_duration'], 'ro-', linewidth=2, label='Avg Duration (ms)')
        ax5_twin.set_ylabel('Average Burst Duration (ms)', color='r')
        ax5_twin.tick_params(axis='y', colors='r')
    else:
        ax5.text(0.5, 0.5, 'No CPU bursts detected', transform=ax5.transAxes,
                ha='center', va='center', fontsize=12)
        ax5.set_title('CPU Burst Analysis')
    
    # 6. Burst Time Distribution
    ax6 = axes[2, 1]
    if burst_data:
        # Create pie chart for total burst time vs normal CPU time
        for cgroup in analyzer.cgroups:
            usage = analyzer._safe_column(cgroup, 'cpu_usage_usec').iloc[-1] / 1000000  # sec
            burst_time = analyzer._safe_column(cgroup, 'cpu_burst_usec').iloc[-1] / 1000000  # sec
            
            if usage > 0 and burst_time > 0:
                regular_time = max(0, usage - burst_time)  # Ensure non-negative
                
                # Create data for pie chart
                labels = ['Regular CPU Time', 'Burst CPU Time']
                sizes = [regular_time, burst_time]
                colors = ['lightblue', 'salmon']
                explode = (0, 0.1)  # Explode the burst slice
                
                ax6.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
                       shadow=True, startangle=90)
                ax6.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
                ax6.set_title(f'{cgroup} - CPU Burst Time Distribution')
                break  # Just show the first cgroup with bursts
    else:
        ax6.text(0.5, 0.5, 'No CPU burst data available', transform=ax6.transAxes,
                ha='center', va='center', fontsize=12)
        ax6.set_title('CPU Burst Time Distribution')
    
    plt.tight_layout()
    plt.savefig(analyzer.output_dir / 'cpu_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Print CPU statistics
    analyzer._print_cpu_stats()