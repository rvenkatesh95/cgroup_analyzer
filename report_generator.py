# cgroup_analyzer/report_generator.py
"""
Report generation module
"""

from datetime import datetime
from pathlib import Path
import json
import pandas as pd


def generate_report(analyzer: 'CgroupAnalyzer') -> str:
    """Generate comprehensive text report"""
    report_lines = []
    report_lines.append("="*80)
    report_lines.append("CGROUP MONITORING ANALYSIS REPORT")
    report_lines.append("="*80)
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Data file: {analyzer.csv_file}")
    report_lines.append(f"Monitoring duration: {analyzer.df['elapsed_sec'].max():.2f} seconds")
    report_lines.append(f"Sample count: {len(analyzer.df)}")
    report_lines.append(f"Sample rate: {len(analyzer.df)/analyzer.df['elapsed_sec'].max():.1f} Hz")
    report_lines.append("")
    
    # Executive Summary
    report_lines.append("EXECUTIVE SUMMARY")
    report_lines.append("-" * 50)
    total_cpu_time = 0
    total_memory_peak = 0
    total_throttling = 0
    
    for cgroup in analyzer.cgroups:
        cpu_usage = analyzer._safe_column(cgroup, 'cpu_usage_usec').iloc[-1]
        total_cpu_time += cpu_usage / 1000000
        if analyzer.has_extended_metrics:
            memory_peak = analyzer._safe_column(cgroup, 'memory_peak').iloc[-1]
            total_memory_peak += memory_peak
        throttling = analyzer._safe_column(cgroup, 'cpu_nr_throttled').iloc[-1]
        total_throttling += throttling
    
    report_lines.append(f"• Total CPU time consumed: {total_cpu_time:.2f} seconds")
    if analyzer.has_extended_metrics:
        report_lines.append(f"• Peak memory usage: {total_memory_peak/(1024*1024):.1f} MB")
    report_lines.append(f"• Total throttling events: {total_throttling:.0f}")
    
    # Performance issues detection
    issues = []
    if total_throttling > 100:
        issues.append("High CPU throttling detected")
    if analyzer.has_extended_metrics:
        for cgroup in analyzer.cgroups:
            oom_events = analyzer._safe_column(cgroup, 'memory_oom_events').iloc[-1]
            if oom_events > 0:
                issues.append(f"OOM events in {cgroup}")
            mem_pressure = analyzer._safe_column(cgroup, 'memory_pressure_some_avg10').max()
            if mem_pressure > 30:
                issues.append(f"High memory pressure in {cgroup}")
    
    if issues:
        report_lines.append(f"• Performance issues: {', '.join(issues)}")
    else:
        report_lines.append("• No major performance issues detected")
    
    report_lines.append("")
    
    # Detailed analysis per cgroup
    for cgroup in analyzer.cgroups:
        report_lines.append(f"CGROUP: {cgroup}")
        report_lines.append("-" * 50)
        
        # CPU Analysis
        usage = analyzer._safe_column(cgroup, 'cpu_usage_usec')
        user_time = analyzer._safe_column(cgroup, 'cpu_user_usec')
        system_time = analyzer._safe_column(cgroup, 'cpu_system_usec')
        nr_throttled = analyzer._safe_column(cgroup, 'cpu_nr_throttled')
        
        cpu_seconds = usage.iloc[-1] / 1000000
        user_seconds = user_time.iloc[-1] / 1000000
        system_seconds = system_time.iloc[-1] / 1000000
        
        report_lines.append("CPU Performance:")
        report_lines.append(f"  • Total CPU time: {cpu_seconds:.2f} seconds")
        report_lines.append(f"  • User/System ratio: {user_seconds:.2f}s / {system_seconds:.2f}s")
        report_lines.append(f"  • Throttling events: {nr_throttled.iloc[-1]:.0f}")
        
        # Calculate CPU utilization pattern
        usage_rate = usage.diff() / analyzer.df['elapsed_sec'].diff() / 1000
        usage_rate = usage_rate.dropna()
        if len(usage_rate) > 0:
            report_lines.append(f"  • Average CPU rate: {usage_rate.mean():.2f} ms/sec")
            report_lines.append(f"  • Peak CPU rate: {usage_rate.max():.2f} ms/sec")
            report_lines.append(f"  • CPU utilization variance: {usage_rate.std():.2f}")
        
        # Memory Analysis (if available)
        if analyzer.has_extended_metrics:
            current_mem = analyzer._safe_column(cgroup, 'memory_current').iloc[-1]
            peak_mem = analyzer._safe_column(cgroup, 'memory_peak').iloc[-1]
            anon_mem = analyzer._safe_column(cgroup, 'memory_anon').iloc[-1]
            file_mem = analyzer._safe_column(cgroup, 'memory_file').iloc[-1]
            
            report_lines.append("Memory Performance:")
            report_lines.append(f"  • Current usage: {current_mem/(1024*1024):.1f} MB")
            report_lines.append(f"  • Peak usage: {peak_mem/(1024*1024):.1f} MB")
            report_lines.append(f"  • Anonymous memory: {anon_mem/(1024*1024):.1f} MB")
            report_lines.append(f"  • File cache: {file_mem/(1024*1024):.1f} MB")
            
            # Memory growth analysis
            memory_series = analyzer._safe_column(cgroup, 'memory_current')
            if len(memory_series) > 10:
                memory_growth = (memory_series.iloc[-1] - memory_series.iloc[0]) / (1024*1024)
                report_lines.append(f"  • Memory growth: {memory_growth:+.1f} MB")
        
        report_lines.append("")
    
    # Recommendations
    report_lines.append("RECOMMENDATIONS")
    report_lines.append("-" * 50)
    recommendations = []
    
    for cgroup in analyzer.cgroups:
        throttling = analyzer._safe_column(cgroup, 'cpu_nr_throttled').iloc[-1]
        if throttling > 50:
            recommendations.append(f"• Consider increasing CPU quota for {cgroup} (high throttling)")
        
        if analyzer.has_extended_metrics:
            oom_events = analyzer._safe_column(cgroup, 'memory_oom_events').iloc[-1]
            if oom_events > 0:
                recommendations.append(f"• Increase memory limit for {cgroup} (OOM events detected)")
            mem_pressure = analyzer._safe_column(cgroup, 'memory_pressure_some_avg10').max()
            if mem_pressure > 20:
                recommendations.append(f"• Monitor memory allocation in {cgroup} (pressure detected)")
    
    # General recommendations
    avg_sample_rate = len(analyzer.df) / analyzer.df['elapsed_sec'].max()
    if avg_sample_rate < 10:
        recommendations.append("• Consider increasing monitoring frequency for better resolution")
    elif avg_sample_rate > 1000:
        recommendations.append("• Consider reducing monitoring frequency to reduce overhead")
    
    if not recommendations:
        recommendations.append("• System appears to be performing well within limits")
        recommendations.append("• Continue monitoring for trend analysis")
    
    report_lines.extend(recommendations)
    report_lines.append("")
    report_lines.append("="*80)
    
    report_content = "\n".join(report_lines)
    
    # Save report
    report_file = analyzer.output_dir / 'analysis_report.txt'
    with open(report_file, 'w') as f:
        f.write(report_content)
    print(f"Detailed report saved to: {report_file}")
    
    return report_content