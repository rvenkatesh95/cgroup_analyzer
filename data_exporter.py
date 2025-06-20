# cgroup_analyzer/data_exporter.py
"""
Data export module
"""


def export_processed_data(analyzer: 'CgroupAnalyzer') -> None:
    """Export processed data for further analysis"""
    print("\n=== Exporting Processed Data ===")
    
    # Create processed dataframe with calculated metrics
    processed_df = analyzer.df.copy()
    
    for cgroup in analyzer.cgroups:
        # Calculate CPU rates
        usage = analyzer._safe_column(cgroup, 'cpu_usage_usec')
        cpu_rate = usage.diff() / processed_df['elapsed_sec'].diff() / 1000  # ms/sec
        processed_df[f'{cgroup}_cpu_rate_ms_per_sec'] = cpu_rate.fillna(0)
        
        # Calculate CPU utilization percentage (assuming single CPU core = 1000 ms/sec)
        cpu_utilization = (cpu_rate / 1000) * 100
        processed_df[f'{cgroup}_cpu_utilization_pct'] = cpu_utilization.fillna(0)
        
        if analyzer.has_extended_metrics:
            # Memory in MB
            memory_current = analyzer._safe_column(cgroup, 'memory_current')
            processed_df[f'{cgroup}_memory_mb'] = memory_current / (1024 * 1024)
            
            # Memory growth rate
            memory_rate = memory_current.diff() / processed_df['elapsed_sec'].diff() / (1024 * 1024)  # MB/sec
            processed_df[f'{cgroup}_memory_growth_mb_per_sec'] = memory_rate.fillna(0)
    
    # Export to CSV
    export_file = analyzer.output_dir / 'processed_data.csv'
    processed_df.to_csv(export_file, index=False)
    print(f"Processed data exported to: {export_file}")
    
    # Export summary statistics
    summary_stats = {}
    for cgroup in analyzer.cgroups:
        stats = {}
        
        # CPU statistics
        usage = analyzer._safe_column(cgroup, 'cpu_usage_usec')
        cpu_rate = processed_df[f'{cgroup}_cpu_rate_ms_per_sec']
        
        stats['cpu_total_seconds'] = usage.iloc[-1] / 1000000
        stats['cpu_avg_rate_ms_per_sec'] = cpu_rate.mean()
        stats['cpu_max_rate_ms_per_sec'] = cpu_rate.max()
        stats['cpu_std_rate_ms_per_sec'] = cpu_rate.std()
        stats['cpu_throttling_events'] = analyzer._safe_column(cgroup, 'cpu_nr_throttled').iloc[-1]
        
        if analyzer.has_extended_metrics:
            # Memory statistics
            memory_mb = processed_df[f'{cgroup}_memory_mb']
            stats['memory_current_mb'] = memory_mb.iloc[-1]
            stats['memory_peak_mb'] = analyzer._safe_column(cgroup, 'memory_peak').iloc[-1] / (1024 * 1024)
            stats['memory_avg_mb'] = memory_mb.mean()
            stats['memory_max_mb'] = memory_mb.max()
            stats['memory_std_mb'] = memory_mb.std()
            stats['oom_events'] = analyzer._safe_column(cgroup, 'memory_oom_events').iloc[-1]
        
        summary_stats[cgroup] = stats
    
    # Save summary as JSON for easy parsing
    import json
    summary_file = analyzer.output_dir / 'summary_statistics.json'
    with open(summary_file, 'w') as f:
        json.dump(summary_stats, f, indent=2)
    print(f"Summary statistics exported to: {summary_file}")