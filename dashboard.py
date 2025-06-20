# cgroup_analyzer/dashboard.py
"""
Performance dashboard module
"""

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
from typing import List


def create_performance_dashboard(analyzer: 'CgroupAnalyzer') -> None:
    """Create comprehensive performance dashboard"""
    print("\n=== Performance Dashboard ===")
    
    fig = plt.figure(figsize=(24, 18))
    gs = fig.add_gridspec(5, 4, hspace=0.3, wspace=0.3)
    
    # Title
    fig.suptitle('Cgroup Performance Dashboard', fontsize=20, fontweight='bold', y=0.98)
    
    # 1. CPU Usage Heatmap (top-left, spans 2x2)
    ax1 = fig.add_subplot(gs[0:2, 0:2])
    _create_cpu_heatmap(ax1, analyzer)
    
    # 2. Real-time CPU Rate (top-right, spans 2x1)
    ax2 = fig.add_subplot(gs[0:2, 2])
    _create_realtime_cpu_plot(ax2, analyzer)
    
    # 3. Resource Utilization Summary (top-right corner)
    ax3 = fig.add_subplot(gs[0:2, 3])
    _create_resource_summary(ax3, analyzer)
    
    # 4. Memory Usage (bottom-left)
    ax4 = fig.add_subplot(gs[2, 0])
    _create_memory_plot(ax4, analyzer)
    
    # 5. Process Count (bottom-left middle)
    ax5 = fig.add_subplot(gs[2, 1])
    _create_process_plot(ax5, analyzer)
    
    # 6. Throttling Events (bottom-right middle)
    ax6 = fig.add_subplot(gs[2, 2])
    _create_throttling_plot(ax6, analyzer)
    
    # 7. System Health Score (bottom-right)
    ax7 = fig.add_subplot(gs[2, 3])
    _create_health_score(ax7, analyzer)
    
    # 8. CPU Burst Analysis (new section)
    ax8 = fig.add_subplot(gs[3, :2])
    _create_cpu_burst_plot(ax8, analyzer)
    
    # 9. Burst vs Regular CPU Time (new section)
    ax9 = fig.add_subplot(gs[3, 2:])
    _create_burst_distribution_plot(ax9, analyzer)
    
    # 10. Timeline Overview (bottom, spans full width)
    ax10 = fig.add_subplot(gs[4, :])
    _create_timeline_overview(ax10, analyzer)
    
    plt.savefig(analyzer.output_dir / 'performance_dashboard.png', dpi=300, bbox_inches='tight')
    plt.close()


def _create_cpu_heatmap(ax, analyzer):
    """Create CPU usage heatmap"""
    # Prepare data for heatmap
    time_bins = 50
    cpu_data = []
    
    for cgroup in analyzer.cgroups:
        usage = analyzer._safe_column(cgroup, 'cpu_usage_usec')
        usage_rate = usage.diff() / analyzer.df['elapsed_sec'].diff() / 1000
        usage_rate = usage_rate.fillna(0).rolling(window=10).mean()
        
        # Bin the data
        binned_data = []
        bin_size = len(usage_rate) // time_bins
        for i in range(time_bins):
            start_idx = i * bin_size
            end_idx = min((i + 1) * bin_size, len(usage_rate))
            if end_idx > start_idx:
                binned_data.append(usage_rate.iloc[start_idx:end_idx].mean())
            else:
                binned_data.append(0)
        cpu_data.append(binned_data)
    
    if cpu_data:
        heatmap_data = np.array(cpu_data)
        im = ax.imshow(heatmap_data, aspect='auto', cmap='YlOrRd', interpolation='bilinear')
        ax.set_yticks(range(len(analyzer.cgroups)))
        ax.set_yticklabels(analyzer.cgroups)
        ax.set_xlabel('Time Progress →')
        ax.set_title('CPU Usage Intensity Heatmap', fontweight='bold')
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('CPU Rate (ms/sec)')


def _create_realtime_cpu_plot(ax, analyzer):
    """Create real-time style CPU plot"""
    for cgroup in analyzer.cgroups:
        usage = analyzer._safe_column(cgroup, 'cpu_usage_usec')
        usage_rate = usage.diff() / analyzer.df['elapsed_sec'].diff() / 1000
        usage_rate = usage_rate.rolling(window=20).mean()
        ax.plot(analyzer.df['elapsed_sec'], usage_rate, linewidth=2, alpha=0.8, label=cgroup)
    
    ax.fill_between(analyzer.df['elapsed_sec'], 0, ax.get_ylim()[1], alpha=0.1, color='gray')
    ax.set_ylabel('CPU Rate (ms/sec)')
    ax.set_title('Real-time CPU Usage', fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def _create_resource_summary(ax, analyzer):
    """Create resource utilization summary"""
    summary_data = []
    
    for cgroup in analyzer.cgroups:
        cpu_usage = analyzer._safe_column(cgroup, 'cpu_usage_usec').iloc[-1] / 1000000  # Convert to seconds
        
        if analyzer.has_extended_metrics:
            memory_mb = analyzer._safe_column(cgroup, 'memory_current').iloc[-1] / (1024 * 1024)
            processes = analyzer._safe_column(cgroup, 'pids_current').iloc[-1]
        else:
            memory_mb, processes = 0, 0
        
        summary_data.append({
            'Cgroup': cgroup,
            'CPU (sec)': f"{cpu_usage:.1f}",
            'Memory (MB)': f"{memory_mb:.1f}" if memory_mb > 0 else "N/A",
            'Processes': f"{int(processes)}" if processes > 0 else "N/A"
        })
    
    # Create table
    ax.axis('tight')
    ax.axis('off')
    
    if summary_data:
        table_data = []
        headers = ['Cgroup', 'CPU (sec)', 'Memory (MB)', 'Processes']
        for item in summary_data:
            table_data.append([item[h] for h in headers])
        
        table = ax.table(cellText=table_data, colLabels=headers,
                       cellLoc='center', loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.5)


def _create_memory_plot(ax, analyzer):
    """Create memory usage plot"""
    if not analyzer.has_extended_metrics:
        ax.text(0.5, 0.5, 'Memory data\nnot available', transform=ax.transAxes,
               ha='center', va='center', fontsize=10)
        ax.set_title('Memory Usage', fontweight='bold')
        return
    
    for cgroup in analyzer.cgroups:
        memory_current = analyzer._safe_column(cgroup, 'memory_current')
        memory_mb = memory_current / (1024 * 1024)
        ax.plot(analyzer.df['elapsed_sec'], memory_mb, linewidth=2, label=cgroup)
    
    ax.set_ylabel('Memory (MB)')
    ax.set_title('Memory Usage', fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def _create_process_plot(ax, analyzer):
    """Create process count plot"""
    if not analyzer.has_extended_metrics:
        ax.text(0.5, 0.5, 'Process data\nnot available', transform=ax.transAxes,
               ha='center', va='center', fontsize=10)
        ax.set_title('Process Count', fontweight='bold')
        return
    
    for cgroup in analyzer.cgroups:
        pids_current = analyzer._safe_column(cgroup, 'pids_current')
        if pids_current.max() > 0:
            ax.plot(analyzer.df['elapsed_sec'], pids_current, linewidth=2, label=cgroup)
    
    ax.set_ylabel('Process Count')
    ax.set_title('Active Processes', fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def _create_throttling_plot(ax, analyzer):
    """Create CPU throttling plot"""
    throttle_events = []
    
    for cgroup in analyzer.cgroups:
        nr_throttled = analyzer._safe_column(cgroup, 'cpu_nr_throttled')
        total_throttles = nr_throttled.iloc[-1]
        throttle_events.append(total_throttles)
    
    if any(x > 0 for x in throttle_events):
        bars = ax.bar(analyzer.cgroups, throttle_events, alpha=0.7)
        ax.set_ylabel('Throttle Events')
        ax.set_title('CPU Throttling', fontweight='bold')
        ax.tick_params(axis='x', rotation=45)
        
        # Color bars based on severity
        for bar, events in zip(bars, throttle_events):
            if events > 100:
                bar.set_color('red')
            elif events > 10:
                bar.set_color('orange')
            else:
                bar.set_color('green')
    else:
        ax.text(0.5, 0.5, 'No throttling\ndetected', transform=ax.transAxes,
               ha='center', va='center', fontsize=10, color='green')
        ax.set_title('CPU Throttling', fontweight='bold')


def _create_health_score(ax, analyzer):
    """Create system health score"""
    scores = []
    
    for cgroup in analyzer.cgroups:
        score = 100  # Start with perfect score
        
        # Deduct for CPU throttling
        nr_throttled = analyzer._safe_column(cgroup, 'cpu_nr_throttled').iloc[-1]
        if nr_throttled > 100:
            score -= 30
        elif nr_throttled > 10:
            score -= 15
        
        # Deduct for memory pressure (if available)
        if analyzer.has_extended_metrics:
            mem_pressure = analyzer._safe_column(cgroup, 'memory_pressure_some_avg10').max()
            if mem_pressure > 50:
                score -= 25
            elif mem_pressure > 10:
                score -= 10
            
            # Deduct for OOM events
            oom_events = analyzer._safe_column(cgroup, 'memory_oom_events').iloc[-1]
            if oom_events > 0:
                score -= 40
        
        scores.append(max(0, score))
    
    # Create health score visualization
    colors = ['red' if s < 50 else 'orange' if s < 75 else 'green' for s in scores]
    bars = ax.bar(analyzer.cgroups, scores, color=colors, alpha=0.7)
    ax.set_ylim(0, 100)
    ax.set_ylabel('Health Score')
    ax.set_title('System Health', fontweight='bold')
    ax.tick_params(axis='x', rotation=45)
    
    # Add score labels
    for bar, score in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
               f'{score:.0f}', ha='center', va='bottom', fontweight='bold')


def _create_timeline_overview(ax, analyzer):
    """Create timeline overview of key events"""
    # Plot major metrics on the same timeline
    ax2 = ax.twinx()
    
    # CPU usage (left axis)
    for cgroup in analyzer.cgroups:
        usage = analyzer._safe_column(cgroup, 'cpu_usage_usec')
        usage_rate = usage.diff() / analyzer.df['elapsed_sec'].diff() / 1000
        usage_rate = usage_rate.rolling(window=30).mean()
        ax.plot(analyzer.df['elapsed_sec'], usage_rate, linewidth=2, alpha=0.7, label=f'{cgroup} CPU')
    
    # Memory usage (right axis, if available)
    if analyzer.has_extended_metrics:
        for cgroup in analyzer.cgroups:
            memory_current = analyzer._safe_column(cgroup, 'memory_current')
            memory_mb = memory_current / (1024 * 1024)
            ax2.plot(analyzer.df['elapsed_sec'], memory_mb, linewidth=2, alpha=0.7, 
                    linestyle='--', label=f'{cgroup} Memory')
    
    ax.set_xlabel('Time (seconds)')
    ax.set_ylabel('CPU Rate (ms/sec)', color='blue')
    ax2.set_ylabel('Memory (MB)', color='red')
    ax.set_title('System Timeline Overview', fontweight='bold')
    
    # Combine legends
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.3)


def _create_cpu_burst_plot(ax, analyzer):
    """Create CPU burst analysis plot"""
    burst_data = []
    
    for cgroup in analyzer.cgroups:
        nr_bursts = analyzer._safe_column(cgroup, 'cpu_nr_bursts')
        burst_time = analyzer._safe_column(cgroup, 'cpu_burst_usec')
        
        if nr_bursts.max() > 0:
            # Calculate cumulative bursts over time
            cumulative_bursts = nr_bursts.copy()
            
            # Calculate burst rate (bursts per second)
            burst_rate = nr_bursts.diff() / analyzer.df['elapsed_sec'].diff()
            burst_rate = burst_rate.fillna(0).rolling(window=10).mean()
            
            ax.plot(analyzer.df['elapsed_sec'], burst_rate, 
                   label=f'{cgroup} Burst Rate', linewidth=2, alpha=0.8)
            
            # Plot cumulative bursts on secondary Y axis
            ax2 = ax.twinx()
            ax2.plot(analyzer.df['elapsed_sec'], cumulative_bursts, 
                    label=f'{cgroup} Total Bursts', linestyle='--', color='red', alpha=0.6)
            ax2.set_ylabel('Cumulative Burst Count', color='red')
            ax2.tick_params(axis='y', colors='red')
            
            # Add burst stats to data collection
            burst_data.append({
                'cgroup': cgroup,
                'total_bursts': nr_bursts.iloc[-1],
                'total_burst_time_ms': burst_time.iloc[-1] / 1000,
                'avg_burst_duration_ms': burst_time.iloc[-1] / max(nr_bursts.iloc[-1], 1) / 1000
            })
    
    if burst_data:
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Burst Rate (bursts/sec)')
        ax.set_title('CPU Burst Analysis', fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Create a combined legend for both axes
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=8)
        
        # Add annotations with burst statistics
        for i, data in enumerate(burst_data):
            if data['total_bursts'] > 0:
                annotation = (f"Total: {int(data['total_bursts'])} bursts\n"
                             f"Avg: {data['avg_burst_duration_ms']:.1f}ms/burst")
                ax.annotate(annotation, xy=(0.02, 0.98-i*0.15), xycoords='axes fraction',
                           fontsize=9, ha='left', va='top',
                           bbox=dict(boxstyle='round', fc='white', alpha=0.7))
    else:
        ax.text(0.5, 0.5, 'No CPU burst data available', transform=ax.transAxes,
               ha='center', va='center', fontsize=12)
        ax.set_title('CPU Burst Analysis', fontweight='bold')


def _create_burst_distribution_plot(ax, analyzer):
    """Create burst vs regular CPU time distribution plot"""
    burst_data = []
    
    for cgroup in analyzer.cgroups:
        usage = analyzer._safe_column(cgroup, 'cpu_usage_usec').iloc[-1] / 1000000  # sec
        burst_time = analyzer._safe_column(cgroup, 'cpu_burst_usec').iloc[-1] / 1000000  # sec
        
        if usage > 0 and burst_time > 0:
            regular_time = max(0, usage - burst_time)  # Ensure non-negative
            burst_percentage = (burst_time / usage) * 100
            
            burst_data.append({
                'cgroup': cgroup,
                'regular_time': regular_time,
                'burst_time': burst_time,
                'burst_percentage': burst_percentage
            })
    
    if burst_data:
        burst_df = pd.DataFrame(burst_data)
        
        # Create stacked bar chart
        bar_width = 0.6
        x_pos = np.arange(len(burst_df))
        
        ax.bar(x_pos, burst_df['regular_time'], bar_width, label='Regular CPU Time', color='lightblue', alpha=0.8)
        ax.bar(x_pos, burst_df['burst_time'], bar_width, bottom=burst_df['regular_time'],
              label='Burst CPU Time', color='salmon', alpha=0.8)
        
        # Add percentage labels
        for i, (_, row) in enumerate(burst_df.iterrows()):
            # Position label in the middle of the burst segment
            y_pos = row['regular_time'] + row['burst_time']/2
            ax.text(i, y_pos, f"{row['burst_percentage']:.1f}%", 
                   ha='center', va='center', color='white', fontweight='bold')
        
        ax.set_xticks(x_pos)
        ax.set_xticklabels(burst_df['cgroup'], rotation=45)
        ax.set_ylabel('CPU Time (seconds)')
        ax.set_title('CPU Time Distribution - Regular vs Burst', fontweight='bold')
        ax.legend(loc='upper right')
        
        # Add summary annotation
        total_regular = burst_df['regular_time'].sum()
        total_burst = burst_df['burst_time'].sum()
        total_burst_pct = (total_burst / (total_regular + total_burst)) * 100
        
        summary = (f"Overall: {total_burst_pct:.1f}% of CPU time in burst mode\n"
                  f"Total burst time: {total_burst:.2f}s")
        ax.annotate(summary, xy=(0.02, 0.97), xycoords='axes fraction', 
                   fontsize=10, ha='left', va='top',
                   bbox=dict(boxstyle='round', fc='white', alpha=0.7))
    else:
        ax.text(0.5, 0.5, 'No CPU burst data available', transform=ax.transAxes,
               ha='center', va='center', fontsize=12)
        ax.set_title('CPU Time Distribution', fontweight='bold')