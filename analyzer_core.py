# cgroup_analyzer/analyzer_core.py
"""
Core analysis logic for the Cgroup Analyzer
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import seaborn as sns
from pathlib import Path
import sys
from typing import List, Dict, Tuple, Optional
import json
from datetime import datetime


class CgroupAnalyzer:
    """Main analyzer class for cgroup monitoring data"""
    
    def __init__(self, csv_file: str, output_dir: str = "analysis_output"):
        self.csv_file = Path(csv_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Load and preprocess data
        self.df = self._load_data()
        self.cgroups = self._detect_cgroups()
        self.has_extended_metrics = self._check_extended_metrics()
        
        print(f"Loaded {len(self.df)} samples for {len(self.cgroups)} cgroups")
        print(f"Time range: {self.df['elapsed_sec'].min():.2f}s - {self.df['elapsed_sec'].max():.2f}s")
        print(f"Extended metrics: {'Yes' if self.has_extended_metrics else 'No'}")
    
    def _load_data(self) -> pd.DataFrame:
        """Load and preprocess the CSV data"""
        try:
            df = pd.read_csv(self.csv_file)
            # Convert timestamp to datetime
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            # Calculate time-based metrics
            df['elapsed_min'] = df['elapsed_sec'] / 60
            return df
        except Exception as e:
            print(f"Error loading CSV file: {e}")
            sys.exit(1)
    
    def _detect_cgroups(self) -> List[str]:
        """Detect available cgroups from column names"""
        cgroups = set()
        for col in self.df.columns:
            if '_cpu_usage_usec' in col:
                cgroup = col.replace('_cpu_usage_usec', '')
                cgroups.add(cgroup)
        return sorted(list(cgroups))
    
    def _check_extended_metrics(self) -> bool:
        """Check if extended metrics are available"""
        return any('_memory_current' in col for col in self.df.columns)
    
    def _safe_column(self, cgroup: str, metric: str, default_value=0) -> pd.Series:
        """Safely get column data with fallback"""
        col_name = f"{cgroup}_{metric}"
        if col_name in self.df.columns:
            return self.df[col_name].fillna(default_value)
        return pd.Series([default_value] * len(self.df))
    
    def _print_cpu_stats(self):
        """Print CPU statistics summary"""
        print("\nCPU Statistics Summary:")
        print("-" * 70)
        for cgroup in self.cgroups:
            print(f"\n{cgroup}:")
            usage = self._safe_column(cgroup, 'cpu_usage_usec')
            user_time = self._safe_column(cgroup, 'cpu_user_usec')
            system_time = self._safe_column(cgroup, 'cpu_system_usec')
            nr_throttled = self._safe_column(cgroup, 'cpu_nr_throttled')
            throttled_time = self._safe_column(cgroup, 'cpu_throttled_usec')
            
            # Add CPU burst metrics
            nr_bursts = self._safe_column(cgroup, 'cpu_nr_bursts')
            burst_time = self._safe_column(cgroup, 'cpu_burst_usec')
            
            total_cpu_sec = usage.iloc[-1] / 1000000
            user_sec = user_time.iloc[-1] / 1000000
            system_sec = system_time.iloc[-1] / 1000000
            
            print(f"  Total CPU Time: {total_cpu_sec:.2f} seconds")
            print(f"  User Time: {user_sec:.2f} seconds ({user_sec/total_cpu_sec*100:.1f}%)")
            print(f"  System Time: {system_sec:.2f} seconds ({system_sec/total_cpu_sec*100:.1f}%)")
            print(f"  Throttling Events: {nr_throttled.iloc[-1]:.0f}")
            print(f"  Throttled Time: {throttled_time.iloc[-1]/1000:.1f} ms")
            
            # Print burst statistics if available
            if nr_bursts.iloc[-1] > 0:
                print(f"  CPU Burst Events: {nr_bursts.iloc[-1]:.0f}")
                avg_burst_time = burst_time.iloc[-1] / max(nr_bursts.iloc[-1], 1) / 1000
                print(f"  Total Burst Time: {burst_time.iloc[-1]/1000:.1f} ms")
                print(f"  Average Burst Duration: {avg_burst_time:.1f} ms")
                burst_percentage = (burst_time.iloc[-1] / 1000) / (total_cpu_sec * 1000) * 100
                print(f"  Burst Time Percentage: {burst_percentage:.1f}%")
            
            # Calculate average CPU utilization rate
            duration = self.df['elapsed_sec'].iloc[-1] - self.df['elapsed_sec'].iloc[0]
            avg_cpu_rate = (usage.iloc[-1] - usage.iloc[0]) / duration / 1000  # ms/sec
            print(f"  Average CPU Rate: {avg_cpu_rate:.2f} ms/sec")
    
    def _print_memory_stats(self):
        """Print memory statistics summary"""
        print("\nMemory Statistics Summary:")
        print("-" * 70)
        for cgroup in self.cgroups:
            print(f"\n{cgroup}:")
            current = self._safe_column(cgroup, 'memory_current').iloc[-1]
            peak = self._safe_column(cgroup, 'memory_peak').iloc[-1]
            anon = self._safe_column(cgroup, 'memory_anon').iloc[-1]
            file_cache = self._safe_column(cgroup, 'memory_file').iloc[-1]
            kernel = self._safe_column(cgroup, 'memory_kernel').iloc[-1]
            oom_events = self._safe_column(cgroup, 'memory_oom_events').iloc[-1]
            
            print(f"  Current Memory: {current/(1024*1024):.1f} MB")
            print(f"  Peak Memory: {peak/(1024*1024):.1f} MB")
            print(f"  Anonymous Memory: {anon/(1024*1024):.1f} MB")
            print(f"  File Cache: {file_cache/(1024*1024):.1f} MB")
            print(f"  Kernel Memory: {kernel/(1024*1024):.1f} MB")
            print(f"  OOM Events: {oom_events:.0f}")
            
            if peak > 0:
                efficiency = (current / peak) * 100
                print(f"  Memory Efficiency: {efficiency:.1f}% (current/peak)")
    
    def generate_report(self) -> str:
        """Generate comprehensive text report"""
        report_lines = []
        report_lines.append("="*80)
        report_lines.append("CGROUP MONITORING ANALYSIS REPORT")
        report_lines.append("="*80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Data file: {self.csv_file}")
        report_lines.append(f"Monitoring duration: {self.df['elapsed_sec'].max():.2f} seconds")
        report_lines.append(f"Sample count: {len(self.df)}")
        report_lines.append(f"Sample rate: {len(self.df)/self.df['elapsed_sec'].max():.1f} Hz")
        report_lines.append("")
        
        # Executive Summary
        report_lines.append("EXECUTIVE SUMMARY")
        report_lines.append("-" * 50)
        total_cpu_time = 0
        total_memory_peak = 0
        total_throttling = 0
        
        for cgroup in self.cgroups:
            cpu_usage = self._safe_column(cgroup, 'cpu_usage_usec').iloc[-1]
            total_cpu_time += cpu_usage / 1000000
            if self.has_extended_metrics:
                memory_peak = self._safe_column(cgroup, 'memory_peak').iloc[-1]
                total_memory_peak += memory_peak
            throttling = self._safe_column(cgroup, 'cpu_nr_throttled').iloc[-1]
            total_throttling += throttling
        
        report_lines.append(f"• Total CPU time consumed: {total_cpu_time:.2f} seconds")
        if self.has_extended_metrics:
            report_lines.append(f"• Peak memory usage: {total_memory_peak/(1024*1024):.1f} MB")
        report_lines.append(f"• Total throttling events: {total_throttling:.0f}")
        
        # Performance issues detection
        issues = []
        if total_throttling > 100:
            issues.append("High CPU throttling detected")
        if self.has_extended_metrics:
            for cgroup in self.cgroups:
                oom_events = self._safe_column(cgroup, 'memory_oom_events').iloc[-1]
                if oom_events > 0:
                    issues.append(f"OOM events in {cgroup}")
                mem_pressure = self._safe_column(cgroup, 'memory_pressure_some_avg10').max()
                if mem_pressure > 30:
                    issues.append(f"High memory pressure in {cgroup}")
        
        if issues:
            report_lines.append(f"• Performance issues: {', '.join(issues)}")
        else:
            report_lines.append("• No major performance issues detected")
        
        report_lines.append("")
        
        # Detailed analysis per cgroup
        for cgroup in self.cgroups:
            report_lines.append(f"CGROUP: {cgroup}")
            report_lines.append("-" * 50)
            
            # CPU Analysis
            usage = self._safe_column(cgroup, 'cpu_usage_usec')
            user_time = self._safe_column(cgroup, 'cpu_user_usec')
            system_time = self._safe_column(cgroup, 'cpu_system_usec')
            nr_throttled = self._safe_column(cgroup, 'cpu_nr_throttled')
            
            cpu_seconds = usage.iloc[-1] / 1000000
            user_seconds = user_time.iloc[-1] / 1000000
            system_seconds = system_time.iloc[-1] / 1000000
            
            report_lines.append("CPU Performance:")
            report_lines.append(f"  • Total CPU time: {cpu_seconds:.2f} seconds")
            report_lines.append(f"  • User/System ratio: {user_seconds:.2f}s / {system_seconds:.2f}s")
            report_lines.append(f"  • Throttling events: {nr_throttled.iloc[-1]:.0f}")
            
            # Calculate CPU utilization pattern
            usage_rate = usage.diff() / self.df['elapsed_sec'].diff() / 1000
            usage_rate = usage_rate.dropna()
            if len(usage_rate) > 0:
                report_lines.append(f"  • Average CPU rate: {usage_rate.mean():.2f} ms/sec")
                report_lines.append(f"  • Peak CPU rate: {usage_rate.max():.2f} ms/sec")
                report_lines.append(f"  • CPU utilization variance: {usage_rate.std():.2f}")
            
            # Memory Analysis (if available)
            if self.has_extended_metrics:
                current_mem = self._safe_column(cgroup, 'memory_current').iloc[-1]
                peak_mem = self._safe_column(cgroup, 'memory_peak').iloc[-1]
                anon_mem = self._safe_column(cgroup, 'memory_anon').iloc[-1]
                file_mem = self._safe_column(cgroup, 'memory_file').iloc[-1]
                
                report_lines.append("Memory Performance:")
                report_lines.append(f"  • Current usage: {current_mem/(1024*1024):.1f} MB")
                report_lines.append(f"  • Peak usage: {peak_mem/(1024*1024):.1f} MB")
                report_lines.append(f"  • Anonymous memory: {anon_mem/(1024*1024):.1f} MB")
                report_lines.append(f"  • File cache: {file_mem/(1024*1024):.1f} MB")
                
                # Memory growth analysis
                memory_series = self._safe_column(cgroup, 'memory_current')
                if len(memory_series) > 10:
                    memory_growth = (memory_series.iloc[-1] - memory_series.iloc[0]) / (1024*1024)
                    report_lines.append(f"  • Memory growth: {memory_growth:+.1f} MB")
            
            report_lines.append("")
        
        # Recommendations
        report_lines.append("RECOMMENDATIONS")
        report_lines.append("-" * 50)
        recommendations = []
        
        for cgroup in self.cgroups:
            throttling = self._safe_column(cgroup, 'cpu_nr_throttled').iloc[-1]
            if throttling > 50:
                recommendations.append(f"• Consider increasing CPU quota for {cgroup} (high throttling)")
            
            if self.has_extended_metrics:
                oom_events = self._safe_column(cgroup, 'memory_oom_events').iloc[-1]
                if oom_events > 0:
                    recommendations.append(f"• Increase memory limit for {cgroup} (OOM events detected)")
                mem_pressure = self._safe_column(cgroup, 'memory_pressure_some_avg10').max()
                if mem_pressure > 20:
                    recommendations.append(f"• Monitor memory allocation in {cgroup} (pressure detected)")
        
        # General recommendations
        avg_sample_rate = len(self.df) / self.df['elapsed_sec'].max()
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
        report_file = self.output_dir / 'analysis_report.txt'
        with open(report_file, 'w') as f:
            f.write(report_content)
        print(f"Detailed report saved to: {report_file}")
        
        return report_content
    
    def export_processed_data(self) -> None:
        """Export processed data for further analysis"""
        print("\n=== Exporting Processed Data ===")
        # Create processed dataframe with calculated metrics
        processed_df = self.df.copy()
        
        for cgroup in self.cgroups:
            # Calculate CPU rates
            usage = self._safe_column(cgroup, 'cpu_usage_usec')
            cpu_rate = usage.diff() / processed_df['elapsed_sec'].diff() / 1000  # ms/sec
            processed_df[f'{cgroup}_cpu_rate_ms_per_sec'] = cpu_rate.fillna(0)
            
            # Calculate CPU utilization percentage (assuming single CPU core = 1000 ms/sec)
            cpu_utilization = (cpu_rate / 1000) * 100
            processed_df[f'{cgroup}_cpu_utilization_pct'] = cpu_utilization.fillna(0)
            
            if self.has_extended_metrics:
                # Memory in MB
                memory_current = self._safe_column(cgroup, 'memory_current')
                processed_df[f'{cgroup}_memory_mb'] = memory_current / (1024 * 1024)
                
                # Memory growth rate
                memory_rate = memory_current.diff() / processed_df['elapsed_sec'].diff() / (1024 * 1024)  # MB/sec
                processed_df[f'{cgroup}_memory_growth_mb_per_sec'] = memory_rate.fillna(0)
        
        # Export to CSV
        export_file = self.output_dir / 'processed_data.csv'
        processed_df.to_csv(export_file, index=False)
        print(f"Processed data exported to: {export_file}")
        
        # Export summary statistics
        summary_stats = {}
        for cgroup in self.cgroups:
            stats = {}
            
            # CPU statistics
            usage = self._safe_column(cgroup, 'cpu_usage_usec')
            cpu_rate = processed_df[f'{cgroup}_cpu_rate_ms_per_sec']
            
            stats['cpu_total_seconds'] = usage.iloc[-1] / 1000000
            stats['cpu_avg_rate_ms_per_sec'] = cpu_rate.mean()
            stats['cpu_max_rate_ms_per_sec'] = cpu_rate.max()
            stats['cpu_std_rate_ms_per_sec'] = cpu_rate.std()
            stats['cpu_throttling_events'] = self._safe_column(cgroup, 'cpu_nr_throttled').iloc[-1]
            
            if self.has_extended_metrics:
                # Memory statistics
                memory_mb = processed_df[f'{cgroup}_memory_mb']
                stats['memory_current_mb'] = memory_mb.iloc[-1]
                stats['memory_peak_mb'] = self._safe_column(cgroup, 'memory_peak').iloc[-1] / (1024 * 1024)
                stats['memory_avg_mb'] = memory_mb.mean()
                stats['memory_max_mb'] = memory_mb.max()
                stats['memory_std_mb'] = memory_mb.std()
                stats['oom_events'] = self._safe_column(cgroup, 'memory_oom_events').iloc[-1]
            
            summary_stats[cgroup] = stats
        
        # Save summary as JSON for easy parsing
        import json
        summary_file = self.output_dir / 'summary_statistics.json'
        with open(summary_file, 'w') as f:
            json.dump(summary_stats, f, indent=2)
        print(f"Summary statistics exported to: {summary_file}")