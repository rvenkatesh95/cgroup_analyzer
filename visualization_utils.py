# cgroup_analyzer/visualization_utils.py
"""
Visualization utility functions
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import seaborn as sns
from interpreter import CgroupInterpreter


def plot_advanced_visualizations(interpreter: 'CgroupInterpreter', output_dir: Path) -> None:
    """Generate advanced visualizations for deeper analysis"""
    # Create directory for advanced visualizations
    adv_dir = output_dir / "advanced_analysis"
    adv_dir.mkdir(exist_ok=True, parents=True)
    
    # 1. Distribution plots
    _plot_distribution_analysis(adv_dir, interpreter)
    
    # 2. Anomaly detection plot
    _plot_anomaly_detection(adv_dir, interpreter)
    
    # 3. Correlation matrix
    if interpreter.has_extended_metrics:
        _plot_correlation_matrix(adv_dir, interpreter)
    
    # 4. Percentiles over time
    _plot_percentiles_over_time(adv_dir, interpreter)


def plot_workload_heatmap(interpreter: 'CgroupInterpreter', output_dir: Path) -> None:
    """Create a heatmap visualization showing workload intensity across time"""
    # Create combined heatmap for all cgroups
    plt.figure(figsize=(15, 8))
    
    # Prepare data structure for heatmap
    num_cgroups = len(interpreter.cgroups)
    time_bins = 100  # Number of time bins
    
    # Create time bins
    min_time = interpreter.analyzer.df['elapsed_sec'].min()
    max_time = interpreter.analyzer.df['elapsed_sec'].max()
    time_edges = np.linspace(min_time, max_time, time_bins+1)
    time_centers = (time_edges[:-1] + time_edges[1:]) / 2
    
    # Prepare data array
    heatmap_data = np.zeros((num_cgroups, time_bins))
    
    # Fill the array with CPU usage rates
    for i, cgroup in enumerate(interpreter.cgroups):
        usage = interpreter.analyzer._safe_column(cgroup, 'cpu_usage_usec')
        usage_rate = usage.diff() / interpreter.analyzer.df['elapsed_sec'].diff() / 1000
        usage_rate = usage_rate.fillna(0)
        
        # For each time bin, calculate average CPU rate
        for j in range(time_bins):
            bin_start = time_edges[j]
            bin_end = time_edges[j+1]
            mask = (interpreter.analyzer.df['elapsed_sec'] >= bin_start) & (interpreter.analyzer.df['elapsed_sec'] < bin_end)
            if mask.any():
                bin_avg = usage_rate[mask].mean()
                heatmap_data[i, j] = bin_avg
    
    # Plot heatmap
    im = plt.imshow(heatmap_data, aspect='auto', cmap='viridis', interpolation='nearest')
    
    # Add colorbar
    cbar = plt.colorbar(im)
    cbar.set_label('CPU Usage Rate (ms/sec)')
    
    # Set labels
    plt.yticks(np.arange(num_cgroups), interpreter.cgroups)
    plt.xlabel('Time (seconds)')
    plt.ylabel('Cgroup')
    
    # Add time ticks
    num_time_ticks = min(10, time_bins)
    time_tick_indices = np.linspace(0, time_bins-1, num_time_ticks, dtype=int)
    plt.xticks(time_tick_indices, [f"{time_centers[i]:.1f}" for i in time_tick_indices])
    
    # Add title
    plt.title('Workload Intensity Heatmap', fontsize=14, fontweight='bold')
    
    # Add annotations for anomalies
    clustered_anomalies = interpreter.cluster_anomalies()
    
    for i, cgroup in enumerate(interpreter.cgroups):
        cpu_clusters = clustered_anomalies[cgroup]['cpu']
        for cluster in cpu_clusters:
            if 'extreme' in cluster['severities']:
                # Find the bin for this timestamp
                start_time = cluster['start_time']
                end_time = cluster['end_time']
                
                # Convert time to bin indices
                start_bin = max(0, min(time_bins-1, int((start_time - min_time) / (max_time - min_time) * time_bins)))
                end_bin = max(0, min(time_bins-1, int((end_time - min_time) / (max_time - min_time) * time_bins)))
                
                # Mark the anomaly on the heatmap
                plt.plot([start_bin, end_bin], [i, i], 'r-', linewidth=3, alpha=0.7)
    
    plt.tight_layout()
    plt.savefig(output_dir / "workload_heatmap.png", dpi=300)
    plt.close()
    
    # Create memory heatmap if available
    if interpreter.has_extended_metrics:
        plt.figure(figsize=(15, 8))
        
        # Prepare data array for memory
        mem_heatmap_data = np.zeros((num_cgroups, time_bins))
        
        # Fill the array with memory usage
        for i, cgroup in enumerate(interpreter.cgroups):
            memory = interpreter.analyzer._safe_column(cgroup, 'memory_current') / (1024 * 1024)  # in MB
            
            # For each time bin, calculate average memory usage
            for j in range(time_bins):
                bin_start = time_edges[j]
                bin_end = time_edges[j+1]
                mask = (interpreter.analyzer.df['elapsed_sec'] >= bin_start) & (interpreter.analyzer.df['elapsed_sec'] < bin_end)
                if mask.any():
                    bin_avg = memory[mask].mean()
                    mem_heatmap_data[i, j] = bin_avg
        
        # Plot heatmap
        im = plt.imshow(mem_heatmap_data, aspect='auto', cmap='plasma', interpolation='nearest')
        
        # Add colorbar
        cbar = plt.colorbar(im)
        cbar.set_label('Memory Usage (MB)')
        
        # Set labels
        plt.yticks(np.arange(num_cgroups), interpreter.cgroups)
        plt.xlabel('Time (seconds)')
        plt.ylabel('Cgroup')
        
        # Add time ticks
        plt.xticks(time_tick_indices, [f"{time_centers[i]:.1f}" for i in time_tick_indices])
        
        # Add title
        plt.title('Memory Usage Heatmap', fontsize=14, fontweight='bold')
        
        # Add annotations for anomalies
        for i, cgroup in enumerate(interpreter.cgroups):
            mem_clusters = clustered_anomalies[cgroup]['memory']
            for cluster in mem_clusters:
                if 'extreme' in cluster['severities']:
                    # Find the bin for this timestamp
                    start_time = cluster['start_time']
                    end_time = cluster['end_time']
                    
                    # Convert time to bin indices
                    start_bin = max(0, min(time_bins-1, int((start_time - min_time) / (max_time - min_time) * time_bins)))
                    end_bin = max(0, min(time_bins-1, int((end_time - min_time) / (max_time - min_time) * time_bins)))
                    
                    # Mark the anomaly on the heatmap
                    plt.plot([start_bin, end_bin], [i, i], 'r-', linewidth=3, alpha=0.7)
        
        plt.tight_layout()
        plt.savefig(output_dir / "memory_heatmap.png", dpi=300)
        plt.close()


def _plot_distribution_analysis(output_dir: Path, interpreter: 'CgroupInterpreter') -> None:
    """Create distribution plots for CPU and memory usage"""
    for cgroup in interpreter.cgroups:
        # CPU usage distribution
        plt.figure(figsize=(12, 6))
        
        # Get CPU usage rate
        usage = interpreter.analyzer._safe_column(cgroup, 'cpu_usage_usec')
        usage_rate = usage.diff() / interpreter.analyzer.df['elapsed_sec'].diff() / 1000
        usage_rate = usage_rate.dropna()
        
        sns.histplot(usage_rate, kde=True, stat="density", linewidth=0)
        plt.title(f"{cgroup} - CPU Usage Distribution")
        plt.xlabel('CPU Usage Rate (ms/sec)')
        plt.ylabel('Density')
        
        # Add percentile lines
        stats = usage_rate.describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99])
        colors = ['green', 'blue', 'purple', 'orange', 'red']
        labels = ['Median', 'p75', 'p90', 'p95', 'p99']
        
        for i, p in enumerate([0.5, 0.75, 0.9, 0.95, 0.99]):
            plt.axvline(stats[f"{int(p*100)}%"], color=colors[i], linestyle='--', alpha=0.7, 
                      label=f"{labels[i]}: {stats[f'{int(p*100)}%']:.2f}")
        
        plt.legend()
        plt.tight_layout()
        plt.savefig(output_dir / f"{cgroup}_cpu_distribution.png", dpi=200)
        plt.close()
        
        # Memory distribution (if available)
        if interpreter.has_extended_metrics:
            plt.figure(figsize=(12, 6))
            memory = interpreter.analyzer._safe_column(cgroup, 'memory_current') / (1024 * 1024)  # in MB
            sns.histplot(memory, kde=True, stat="density", linewidth=0)
            plt.title(f"{cgroup} - Memory Usage Distribution")
            plt.xlabel('Memory Usage (MB)')
            plt.ylabel('Density')
            
            # Add percentile lines
            mem_stats = memory.describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99])
            
            for i, p in enumerate([0.5, 0.75, 0.9, 0.95, 0.99]):
                plt.axvline(mem_stats[f"{int(p*100)}%"], color=colors[i], linestyle='--', alpha=0.7, 
                          label=f"{labels[i]}: {mem_stats[f'{int(p*100)}%']:.2f} MB")
            
            plt.legend()
            plt.tight_layout()
            plt.savefig(output_dir / f"{cgroup}_memory_distribution.png", dpi=200)
            plt.close()


def _plot_anomaly_detection(output_dir: Path, interpreter: 'CgroupInterpreter') -> None:
    """Plot time series with anomalies highlighted"""
    anomalies = interpreter.detect_anomalies()
    
    for cgroup in interpreter.cgroups:
        # CPU anomalies
        plt.figure(figsize=(14, 7))
        
        # Plot the time series
        usage = interpreter.analyzer._safe_column(cgroup, 'cpu_usage_usec')
        usage_rate = usage.diff() / interpreter.analyzer.df['elapsed_sec'].diff() / 1000
        plt.plot(interpreter.analyzer.df['elapsed_sec'], usage_rate, label='CPU Usage Rate', linewidth=1, alpha=0.7)
        
        # Highlight anomalies
        cpu_anomalies = anomalies[cgroup]['cpu']
        if cpu_anomalies['timestamps']:
            extreme_indices = [i for i, sev in enumerate(cpu_anomalies['severity']) if sev == 'extreme']
            high_indices = [i for i, sev in enumerate(cpu_anomalies['severity']) if sev == 'high']
            
            if extreme_indices:
                ext_timestamps = [cpu_anomalies['timestamps'][i] for i in extreme_indices]
                ext_values = [cpu_anomalies['values'][i] for i in extreme_indices]
                plt.scatter(ext_timestamps, ext_values, color='red', s=50, label='Extreme Anomalies', zorder=5)
            
            if high_indices:
                high_timestamps = [cpu_anomalies['timestamps'][i] for i in high_indices]
                high_values = [cpu_anomalies['values'][i] for i in high_indices]
                plt.scatter(high_timestamps, high_values, color='orange', s=30, label='High Anomalies', zorder=4)
        
        plt.title(f"{cgroup} - CPU Usage Anomaly Detection")
        plt.xlabel('Time (seconds)')
        plt.ylabel('CPU Usage Rate (ms/sec)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / f"{cgroup}_cpu_anomalies.png", dpi=200)
        plt.close()
        
        # Memory anomalies (if available)
        if interpreter.has_extended_metrics:
            plt.figure(figsize=(14, 7))
            
            # Plot the time series
            memory = interpreter.analyzer._safe_column(cgroup, 'memory_current') / (1024 * 1024)  # in MB
            plt.plot(interpreter.analyzer.df['elapsed_sec'], memory, label='Memory Usage', linewidth=1, alpha=0.7)
            
            # Highlight anomalies
            mem_anomalies = anomalies[cgroup]['memory']
            if mem_anomalies['timestamps']:
                extreme_indices = [i for i, sev in enumerate(mem_anomalies['severity']) if sev == 'extreme']
                high_indices = [i for i, sev in enumerate(mem_anomalies['severity']) if sev == 'high']
                
                if extreme_indices:
                    ext_timestamps = [mem_anomalies['timestamps'][i] for i in extreme_indices]
                    ext_values = [mem_anomalies['values'][i] for i in extreme_indices]
                    plt.scatter(ext_timestamps, ext_values, color='red', s=50, label='Extreme Anomalies', zorder=5)
                
                if high_indices:
                    high_timestamps = [mem_anomalies['timestamps'][i] for i in high_indices]
                    high_values = [mem_anomalies['values'][i] for i in high_indices]
                    plt.scatter(high_timestamps, high_values, color='orange', s=30, label='High Anomalies', zorder=4)
            
            plt.title(f"{cgroup} - Memory Usage Anomaly Detection")
            plt.xlabel('Time (seconds)')
            plt.ylabel('Memory Usage (MB)')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(output_dir / f"{cgroup}_memory_anomalies.png", dpi=200)
            plt.close()


def _plot_correlation_matrix(output_dir: Path, interpreter: 'CgroupInterpreter') -> None:
    """Plot correlation matrix between different metrics"""
    if not interpreter.has_extended_metrics:
        return
    
    # Create a dataframe with all relevant metrics
    corr_data = pd.DataFrame()
    
    for cgroup in interpreter.cgroups:
        # CPU metrics
        cpu_usage = interpreter.analyzer._safe_column(cgroup, 'cpu_usage_usec')
        cpu_rate = cpu_usage.diff() / interpreter.analyzer.df['elapsed_sec'].diff() / 1000
        corr_data[f"{cgroup}_cpu_rate"] = cpu_rate
        
        # Memory metrics
        memory = pd.to_numeric(interpreter.analyzer._safe_column(cgroup, 'memory_current'), errors='coerce') / (1024 * 1024)
        corr_data[f"{cgroup}_memory_mb"] = memory
        
        # Pressure metrics
        pressure_cpu = interpreter.analyzer._safe_column(cgroup, 'cpu_pressure_some_avg10')
        pressure_mem = interpreter.analyzer._safe_column(cgroup, 'memory_pressure_some_avg10')
        corr_data[f"{cgroup}_cpu_pressure"] = pressure_cpu
        corr_data[f"{cgroup}_mem_pressure"] = pressure_mem
    
    # Drop NaN values
    corr_data = corr_data.dropna()
    
    # Calculate correlation matrix
    if not corr_data.empty:
        corr_matrix = corr_data.corr()
        
        # Plot correlation matrix
        plt.figure(figsize=(12, 10))
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt=".2f", linewidths=0.5, vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Resource Metrics')
        plt.tight_layout()
        plt.savefig(output_dir / "correlation_matrix.png", dpi=200)
        plt.close()


def _plot_percentiles_over_time(output_dir: Path, interpreter: 'CgroupInterpreter') -> None:
    """Plot percentiles over time for CPU usage"""
    window_size = max(int(len(interpreter.analyzer.df) / 20), 5)  # Reasonable window size
    
    for cgroup in interpreter.cgroups:
        plt.figure(figsize=(14, 7))
        
        # Get CPU usage
        usage = interpreter.analyzer._safe_column(cgroup, 'cpu_usage_usec')
        usage_rate = usage.diff() / interpreter.analyzer.df['elapsed_sec'].diff() / 1000
        
        # Calculate rolling statistics
        mean = usage_rate.rolling(window=window_size).mean()
        median = usage_rate.rolling(window=window_size).median()
        p90 = usage_rate.rolling(window=window_size).quantile(0.9)
        p99 = usage_rate.rolling(window=window_size).quantile(0.99)
        
        # Plot
        plt.plot(interpreter.analyzer.df['elapsed_sec'], mean, label='Mean', linewidth=1.5)
        plt.plot(interpreter.analyzer.df['elapsed_sec'], median, label='Median', linewidth=1.5, linestyle='--')
        plt.plot(interpreter.analyzer.df['elapsed_sec'], p90, label='P90', linewidth=1.5, linestyle='-.')
        plt.plot(interpreter.analyzer.df['elapsed_sec'], p99, label='P99', linewidth=1.5, linestyle=':')
        
        plt.title(f"{cgroup} - CPU Usage Percentiles Over Time")
        plt.xlabel('Time (seconds)')
        plt.ylabel('CPU Usage Rate (ms/sec)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / f"{cgroup}_cpu_percentiles.png", dpi=200)
        plt.close()
        
        # Memory percentiles (if available)
        if interpreter.has_extended_metrics:
            plt.figure(figsize=(14, 7))
            
            # Get memory usage
            memory = pd.to_numeric(interpreter.analyzer._safe_column(cgroup, 'memory_current'), errors='coerce') / (1024 * 1024)
            
            # Calculate rolling statistics
            mean = memory.rolling(window=window_size).mean()
            median = memory.rolling(window=window_size).median()
            p90 = memory.rolling(window=window_size).quantile(0.9)
            p99 = memory.rolling(window=window_size).quantile(0.99)
            
            # Plot
            plt.plot(interpreter.analyzer.df['elapsed_sec'], mean, label='Mean', linewidth=1.5)
            plt.plot(interpreter.analyzer.df['elapsed_sec'], median, label='Median', linewidth=1.5, linestyle='--')
            plt.plot(interpreter.analyzer.df['elapsed_sec'], p90, label='P90', linewidth=1.5, linestyle='-.')
            plt.plot(interpreter.analyzer.df['elapsed_sec'], p99, label='P99', linewidth=1.5, linestyle=':')
            
            plt.title(f"{cgroup} - Memory Usage Percentiles Over Time")
            plt.xlabel('Time (seconds)')
            plt.ylabel('Memory Usage (MB)')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(output_dir / f"{cgroup}_memory_percentiles.png", dpi=200)
            plt.close()


def _calculate_sustained_load(series: pd.Series, window: int) -> float:
    """Calculate sustained load over a sliding window"""
    if len(series) < window:
        return series.max() if not series.empty else 0
    
    # Use rolling window to find max sustained load
    sustained = series.rolling(window=window).mean().max()
    return sustained if not pd.isna(sustained) else 0


def fingerprint_workload_patterns(interpreter: 'CgroupInterpreter') -> Dict[str, Dict[str, str]]:
    """Create a distinctive fingerprint characterizing each cgroup's workload behavior pattern"""
    fingerprints = {}
    
    for cgroup in interpreter.cgroups:
        # Get base CPU data
        usage = interpreter.analyzer._safe_column(cgroup, 'cpu_usage_usec')
        usage_rate = usage.diff() / interpreter.analyzer.df['elapsed_sec'].diff() / 1000
        usage_rate = usage_rate.fillna(0)
        
        # Calculate workload characteristics
        # 1. Overall pattern type
        patterns = interpreter.identify_usage_patterns()
        pattern_type = patterns[cgroup]['cpu_pattern']
        
        # 2. Periodicity detection
        has_periodicity = False
        dominant_period = 0
        
        if len(usage_rate) > 50:
            # Use autocorrelation to detect periodicity
            try:
                n = len(usage_rate)
                # Truncate to reasonable length for performance
                max_lag = min(n - 1, 500)  
                autocorr = np.correlate(usage_rate - usage_rate.mean(), 
                                      usage_rate - usage_rate.mean(), 
                                      mode='full')[n-1:n+max_lag] / (usage_rate.std() ** 2 * n)
                
                # Find peaks in autocorrelation
                peaks = []
                for i in range(1, len(autocorr)-1):
                    if autocorr[i] > autocorr[i-1] and autocorr[i] > autocorr[i+1] and autocorr[i] > 0.2:
                        peaks.append((i, autocorr[i]))
                
                # If we found peaks, get the dominant period
                if peaks:
                    peaks.sort(key=lambda x: x[1], reverse=True)
                    dominant_period = peaks[0][0]
                    has_periodicity = True
            except:
                pass
        
        # 3. Burstiness score (ratio of p95 to median)
        burstiness = usage_rate.quantile(0.95) / max(usage_rate.median(), 0.001)
        
        # 4. CPU cycle intensity ratio (system vs user)
        user_time = interpreter.analyzer._safe_column(cgroup, 'cpu_user_usec').iloc[-1]
        system_time = interpreter.analyzer._safe_column(cgroup, 'cpu_system_usec').iloc[-1]
        cycle_ratio = system_time / max(user_time, 1) if user_time > 0 else 0
        
        # Determine workload type based on the metrics
        workload_type = "Unknown"
        
        if has_periodicity and dominant_period > 0:
            workload_type = "Periodic"
            if burstiness > 5:
                workload_type += " with bursts"
        elif pattern_type.startswith("Steady"):
            workload_type = "Continuous"
            if cycle_ratio > 0.8:
                workload_type += " system-intensive"
            else:
                workload_type += " user-intensive"
        elif pattern_type.startswith("Bursty"):
            workload_type = "Batch processing"
        else:
            workload_type = "Variable"
            if cycle_ratio > 0.8:
                workload_type += " I/O-bound"
            else:
                workload_type += " CPU-bound"
        
        # Memory pattern (if available)
        memory_type = "N/A"
        
        if interpreter.has_extended_metrics:
            memory = pd.to_numeric(interpreter.analyzer._safe_column(cgroup, 'memory_current'), errors='coerce')
            mem_stats = interpreter.calculate_advanced_statistics()[cgroup]['memory']
            
            # Check for constant memory growth
            if patterns[cgroup]['memory_pattern'] == "Rapidly growing":
                memory_type = "Memory leaking"
            
            # Check for stable memory
            elif mem_stats['coefficient_of_variation'] < 0.1:
                memory_type = "Static memory"
            
            # Check for cyclical memory pattern
            else:
                memory_delta = memory.diff()
                pos_changes = (memory_delta > 0).sum()
                neg_changes = (memory_delta < 0).sum()
                
                if pos_changes > 0 and neg_changes > 0:
                    # If memory goes up and down
                    if abs(pos_changes - neg_changes) / max(pos_changes, neg_changes) < 0.3:
                        memory_type = "Dynamic allocation/deallocation"
                    else:
                        memory_type = "Gradually expanding"
        
        # Check for CPU burst utilization
        burst_tendency = "N/A"
        burst_score = 0.0
        nr_bursts = interpreter.analyzer._safe_column(cgroup, 'cpu_nr_bursts')
        burst_time = interpreter.analyzer._safe_column(cgroup, 'cpu_burst_usec')
        
        if nr_bursts.max() > 0:
            # Calculate total CPU usage & burst percentage
            usage = interpreter.analyzer._safe_column(cgroup, 'cpu_usage_usec').iloc[-1]
            burst_pct = (burst_time.iloc[-1] / max(usage, 1)) * 100
            burst_score = burst_pct
            
            if burst_pct > 30:
                burst_tendency = "High burst utilization"
                # Modify workload type to reflect high burst usage
                if not "burst" in workload_type.lower():
                    workload_type = workload_type + " (burst-heavy)"
            elif burst_pct > 10:
                burst_tendency = "Moderate burst utilization"
            else:
                burst_tendency = "Low burst utilization"
        
        fingerprints[cgroup] = {
            'workload_type': workload_type,
            'memory_behavior': memory_type,
            'burstiness': f"{burstiness:.2f}",
            'cpu_burst_tendency': burst_tendency,
            'cpu_burst_score': f"{burst_score:.1f}",
            'cpu_system_user_ratio': f"{cycle_ratio:.2f}",
            'has_periodicity': str(has_periodicity),
            'dominant_period_lag': str(dominant_period)
        }
    
    return fingerprints