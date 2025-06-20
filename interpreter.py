from typing import Dict, List, Any
import pandas as pd


class CgroupInterpreter:
    """Enhanced data interpretation with anomaly detection, pattern recognition, and statistical insights"""
    
    def __init__(self, analyzer: 'CgroupAnalyzer'):
        self.analyzer = analyzer
        self.df = analyzer.df
        self.cgroups = analyzer.cgroups
        self.has_extended_metrics = analyzer.has_extended_metrics

    def detect_anomalies(self) -> Dict[str, Dict[str, List[Any]]]:
        """
        Detect anomalies in CPU and memory usage using statistical methods
        Returns a dictionary with anomalous time periods and their severity
        """
        anomalies = {}

        for cgroup in self.cgroups:
            cgroup_anomalies = {
                'cpu': {'timestamps': [], 'values': [], 'severity': []},
                'memory': {'timestamps': [], 'values': [], 'severity': []}
            }

            # CPU anomaly detection
            usage = self.analyzer._safe_column(cgroup, 'cpu_usage_usec')
            usage_rate = usage.diff() / self.df['elapsed_sec'].diff() / 1000
            if len(usage_rate) < 2:
                continue  # Not enough data to analyze

            q1 = usage_rate.quantile(0.25)
            q3 = usage_rate.quantile(0.75)
            iqr = q3 - q1
            upper_bound = q3 + 1.5 * iqr
            extreme_bound = q3 + 3.0 * iqr

            for i, val in enumerate(usage_rate):
                if pd.isna(val):
                    continue
                if val > extreme_bound:
                    cgroup_anomalies['cpu']['timestamps'].append(self.df['elapsed_sec'].iloc[i])
                    cgroup_anomalies['cpu']['values'].append(val)
                    cgroup_anomalies['cpu']['severity'].append('extreme')
                elif val > upper_bound:
                    cgroup_anomalies['cpu']['timestamps'].append(self.df['elapsed_sec'].iloc[i])
                    cgroup_anomalies['cpu']['values'].append(val)
                    cgroup_anomalies['cpu']['severity'].append('high')

            # Memory anomaly detection (if available)
            if self.has_extended_metrics:
                memory = self.analyzer._safe_column(cgroup, 'memory_current')
                # Convert string values to numeric before division
                memory = pd.to_numeric(memory, errors='coerce')
                memory = memory / (1024 * 1024)
                memory_rate = memory.diff() / self.df['elapsed_sec'].diff()
                if len(memory_rate) > 0:
                    mq1 = memory_rate.quantile(0.25)
                    mq3 = memory_rate.quantile(0.75)
                    miqr = mq3 - mq1
                    m_upper = mq3 + 1.5 * miqr
                    m_extreme = mq3 + 3.0 * miqr

                    for i, val in enumerate(memory_rate):
                        if pd.isna(val):
                            continue
                        if val > m_extreme:
                            cgroup_anomalies['memory']['timestamps'].append(self.df['elapsed_sec'].iloc[i])
                            cgroup_anomalies['memory']['values'].append(val)
                            cgroup_anomalies['memory']['severity'].append('extreme')
                        elif val > m_upper:
                            cgroup_anomalies['memory']['timestamps'].append(self.df['elapsed_sec'].iloc[i])
                            cgroup_anomalies['memory']['values'].append(val)
                            cgroup_anomalies['memory']['severity'].append('high')

            anomalies[cgroup] = cgroup_anomalies

        return anomalies

    def cluster_anomalies(self) -> Dict[str, Dict[str, List]]:
        """
        Group anomalies into clusters based on their temporal proximity and characteristics
        Returns:
            Dictionary with clusters of related anomalies
        """
        MAX_TIME_GAP = 10  # seconds between related anomalies
        anomalies = self.detect_anomalies()
        clustered_anomalies = {}

        for cgroup in self.cgroups:
            cpu_clusters = []
            memory_clusters = []

            # Cluster CPU anomalies
            timestamps = anomalies[cgroup]['cpu']['timestamps']
            values = anomalies[cgroup]['cpu']['values']
            severities = anomalies[cgroup]['cpu']['severity']

            if timestamps:
                current_cluster = {
                    'start_time': timestamps[0],
                    'end_time': timestamps[0],
                    'max_value': values[0],
                    'timestamps': [timestamps[0]],
                    'values': [values[0]],
                    'severities': [severities[0]]
                }

                for i in range(1, len(timestamps)):
                    # If this anomaly is close to the previous one, add to current cluster
                    if timestamps[i] - current_cluster['end_time'] < MAX_TIME_GAP:
                        current_cluster['end_time'] = timestamps[i]
                        current_cluster['max_value'] = max(current_cluster['max_value'], values[i])
                        current_cluster['timestamps'].append(timestamps[i])
                        current_cluster['values'].append(values[i])
                        current_cluster['severities'].append(severities[i])
                    else:
                        # Start a new cluster
                        cpu_clusters.append(current_cluster)
                        current_cluster = {
                            'start_time': timestamps[i],
                            'end_time': timestamps[i],
                            'max_value': values[i],
                            'timestamps': [timestamps[i]],
                            'values': [values[i]],
                            'severities': [severities[i]]
                        }

                # Add the last cluster
                cpu_clusters.append(current_cluster)

            # Cluster memory anomalies (if available)
            if self.has_extended_metrics:
                timestamps = anomalies[cgroup]['memory']['timestamps']
                values = anomalies[cgroup]['memory']['values']
                severities = anomalies[cgroup]['memory']['severity']

                if timestamps:
                    current_cluster = {
                        'start_time': timestamps[0],
                        'end_time': timestamps[0],
                        'max_value': values[0],
                        'timestamps': [timestamps[0]],
                        'values': [values[0]],
                        'severities': [severities[0]]
                    }

                    for i in range(1, len(timestamps)):
                        # If this anomaly is close to the previous one, add to current cluster
                        if timestamps[i] - current_cluster['end_time'] < MAX_TIME_GAP:
                            current_cluster['end_time'] = timestamps[i]
                            current_cluster['max_value'] = max(current_cluster['max_value'], values[i])
                            current_cluster['timestamps'].append(timestamps[i])
                            current_cluster['values'].append(values[i])
                            current_cluster['severities'].append(severities[i])
                        else:
                            # Start a new cluster
                            memory_clusters.append(current_cluster)
                            current_cluster = {
                                'start_time': timestamps[i],
                                'end_time': timestamps[i],
                                'max_value': values[i],
                                'timestamps': [timestamps[i]],
                                'values': [values[i]],
                                'severities': [severities[i]]
                            }

                    # Add the last cluster
                    memory_clusters.append(current_cluster)

            # Add to results
            clustered_anomalies[cgroup] = {
                'cpu': cpu_clusters,
                'memory': memory_clusters
            }

        return clustered_anomalies

    def identify_usage_patterns(self) -> Dict[str, Dict[str, str]]:
        """
        Identify resource usage patterns for each cgroup
        Returns:
            Dictionary with cgroups and their usage pattern classifications
        """
        patterns = {}

        for cgroup in self.cgroups:
            cpu_pattern = "unknown"
            memory_pattern = "unknown"

            # CPU pattern detection
            usage = self.analyzer._safe_column(cgroup, 'cpu_usage_usec')
            if len(usage) > 10:  # Need enough data for pattern detection
                # Convert any string values to numeric
                usage = pd.to_numeric(usage, errors='coerce')
                usage_rate = usage.diff() / self.df['elapsed_sec'].diff() / 1000
                
                # Calculate basic statistics for pattern recognition
                mean_usage = usage_rate.mean()
                std_usage = usage_rate.std()
                max_usage = usage_rate.max()
                min_usage = usage_rate.min()
                
                # Detect patterns based on statistical properties
                cv = std_usage / mean_usage if mean_usage > 0 else 0
                
                if cv > 1.5:
                    if len(usage_rate[usage_rate > mean_usage * 2]) > len(usage_rate) * 0.1:
                        cpu_pattern = "bursty"
                    else:
                        cpu_pattern = "variable"
                elif cv > 0.5:
                    cpu_pattern = "moderate variability"
                else:
                    cpu_pattern = "stable"
                    
                # Check for periodic patterns using autocorrelation
                try:
                    from statsmodels.tsa.stattools import acf
                    lag_acf = acf(usage_rate.fillna(0), nlags=min(50, len(usage_rate)//2))
                    if any(lag_acf[1:] > 0.5):  # If any autocorrelation > 0.5
                        period_idx = next((i for i, x in enumerate(lag_acf[1:], 1) if x > 0.5), None)
                        if period_idx:
                            cpu_pattern = f"{cpu_pattern} with periodicity (~{period_idx} samples)"
                except (ImportError, Exception):
                    # statsmodels might not be available
                    pass

            # Memory pattern detection (if available)
            if self.has_extended_metrics:
                memory = self.analyzer._safe_column(cgroup, 'memory_current')
                if len(memory) > 10:
                    # Convert any string values to numeric
                    memory = pd.to_numeric(memory, errors='coerce')
                    memory_mb = memory / (1024 * 1024)  # Convert to MB
                    memory_rate = memory_mb.diff() / self.df['elapsed_sec'].diff()
                    
                    # Calculate growth trends
                    if memory_mb.iloc[-1] > memory_mb.iloc[0] * 1.5:
                        growth_rate = (memory_mb.iloc[-1] - memory_mb.iloc[0]) / max(1, self.df['elapsed_sec'].iloc[-1])
                        if growth_rate > 0.5:  # More than 0.5 MB/s
                            memory_pattern = "rapidly increasing"
                        else:
                            memory_pattern = "gradually increasing"
                    elif memory_mb.iloc[-1] < memory_mb.iloc[0] * 0.5:
                        memory_pattern = "decreasing"
                    elif memory_mb.max() > memory_mb.mean() * 2:
                        memory_pattern = "spike patterns"
                    else:
                        # Check for oscillating patterns
                        memory_diffs = memory_mb.diff()
                        sign_changes = ((memory_diffs.shift(1) * memory_diffs) < 0).sum()
                        if sign_changes > len(memory_mb) * 0.4:  # Many direction changes
                            memory_pattern = "oscillating"
                        else:
                            memory_pattern = "stable"

            patterns[cgroup] = {
                'cpu_pattern': cpu_pattern,
                'memory_pattern': memory_pattern
            }

        return patterns

    def generate_insights(self) -> Dict[str, List[str]]:
        """
        Generate actionable insights based on the analysis results
        
        Returns:
            Dictionary with cgroups and insights for each
        """
        insights = {}
        anomalies = self.detect_anomalies()
        clusters = self.cluster_anomalies()
        patterns = self.identify_usage_patterns()
        
        for cgroup in self.cgroups:
            cgroup_insights = []
            
            # CPU usage insights
            cpu_anomaly_count = len(anomalies.get(cgroup, {}).get('cpu', {}).get('timestamps', []))
            cpu_clusters_count = len(clusters.get(cgroup, {}).get('cpu', []))
            cpu_pattern = patterns.get(cgroup, {}).get('cpu_pattern', 'unknown')
            
            if cpu_anomaly_count > 10:
                cgroup_insights.append(f"High number of CPU anomalies detected ({cpu_anomaly_count}), suggesting unstable workload")
            
            if "bursty" in cpu_pattern.lower():
                cgroup_insights.append(f"CPU usage shows bursty pattern. Consider tuning CPU shares or limiting concurrent operations")
            
            if "periodicity" in cpu_pattern.lower():
                cgroup_insights.append(f"Periodic CPU usage detected. This might indicate scheduled tasks or polling operations")
                
            # CPU burst analysis
            nr_bursts = self.analyzer._safe_column(cgroup, 'cpu_nr_bursts')
            burst_time = self.analyzer._safe_column(cgroup, 'cpu_burst_usec')
            usage = self.analyzer._safe_column(cgroup, 'cpu_usage_usec')
            
            if nr_bursts.iloc[-1] > 0:
                total_bursts = nr_bursts.iloc[-1]
                avg_burst_duration = burst_time.iloc[-1] / max(total_bursts, 1) / 1000  # ms
                burst_percent = (burst_time.iloc[-1] / usage.iloc[-1]) * 100
                
                if total_bursts > 50:
                    cgroup_insights.append(f"High number of CPU bursts detected ({int(total_bursts)}). This indicates periods of intense CPU activity")
                
                if avg_burst_duration > 10:  # More than 10ms per burst
                    cgroup_insights.append(f"Long average burst duration ({avg_burst_duration:.1f}ms) may indicate inefficient CPU usage patterns")
                
                if burst_percent > 30:  # More than 30% of CPU time in burst mode
                    cgroup_insights.append(f"Significant portion of CPU time ({burst_percent:.1f}%) spent in burst mode. Consider optimizing for more consistent CPU usage")

            # Memory usage insights (if available)
            if self.has_extended_metrics:
                mem_anomaly_count = len(anomalies.get(cgroup, {}).get('memory', {}).get('timestamps', []))
                mem_clusters_count = len(clusters.get(cgroup, {}).get('memory', []))
                mem_pattern = patterns.get(cgroup, {}).get('memory_pattern', 'unknown')
                
                if mem_anomaly_count > 5:
                    cgroup_insights.append(f"High number of memory anomalies detected ({mem_anomaly_count}), suggesting potential memory management issues")
                
                if "increasing" in mem_pattern.lower():
                    # Get current and max memory values
                    memory = self.analyzer._safe_column(cgroup, 'memory_current')
                    memory_limit = self.analyzer._safe_column(cgroup, 'memory_max')
                    
                    if not memory.empty and not memory_limit.empty and len(memory) > 0 and len(memory_limit) > 0:
                        # Convert to numeric before division
                        mem_current = pd.to_numeric(memory.iloc[-1], errors='coerce')
                        mem_limit = pd.to_numeric(memory_limit.iloc[-1], errors='coerce')
                        
                        mem_current_mb = mem_current / (1024 * 1024)  # MB
                        mem_limit_mb = mem_limit / (1024 * 1024) if mem_limit > 0 else float('inf')
                        
                        if mem_limit_mb != float('inf'):
                            usage_percent = (mem_current_mb / mem_limit_mb) * 100
                            if usage_percent > 80:
                                cgroup_insights.append(f"Memory usage is high ({usage_percent:.1f}% of limit) and increasing. Risk of OOM termination")
                            else:
                                cgroup_insights.append(f"Memory usage is increasing. Currently at {usage_percent:.1f}% of limit")
                        else:
                            cgroup_insights.append(f"Memory usage is increasing. No memory limit set")
                
                if "spike" in mem_pattern.lower():
                    cgroup_insights.append(f"Memory usage shows spike patterns. Consider investigating potential memory leaks or garbage collection issues")
            
            # System pressure insights
            try:
                pressure_cols = [col for col in self.df.columns if col.startswith('pressure_') and cgroup in col]
                if pressure_cols:
                    for col in pressure_cols:
                        if 'cpu' in col and 'some_avg60' in col:
                            cpu_pressure = self.df[col].mean()
                            if cpu_pressure > 10:
                                cgroup_insights.append(f"High CPU pressure detected (avg: {cpu_pressure:.1f}). System may be CPU constrained")
                        
                        if 'memory' in col and 'some_avg60' in col:
                            memory_pressure = self.df[col].mean()
                            if memory_pressure > 10:
                                cgroup_insights.append(f"High memory pressure detected (avg: {memory_pressure:.1f}). System may need more memory")
                        
                        if 'io' in col and 'some_avg60' in col:
                            io_pressure = self.df[col].mean()
                            if io_pressure > 10:
                                cgroup_insights.append(f"High I/O pressure detected (avg: {io_pressure:.1f}). Disk performance may be limiting factor")
            except Exception:
                pass
                
            # Add general insights if none specific were found
            if not cgroup_insights:
                cgroup_insights.append("No significant issues detected")
                
            insights[cgroup] = cgroup_insights
                
        return insights

    def calculate_advanced_statistics(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Calculate advanced statistical metrics for each cgroup's resources
        Returns:
            Dictionary with cgroups and their detailed statistics
        """
        statistics = {}
        
        for cgroup in self.cgroups:
            cgroup_stats = {
                'cpu': {},
                'memory': {},
                'io': {}
            }
            
            # CPU statistics
            usage = self.analyzer._safe_column(cgroup, 'cpu_usage_usec')
            usage_rate = usage.diff() / self.df['elapsed_sec'].diff() / 1000
            
            if len(usage_rate) > 1:
                # Remove NaN values
                usage_rate = usage_rate.dropna()
                
                # Basic statistics
                cgroup_stats['cpu']['mean'] = usage_rate.mean()
                cgroup_stats['cpu']['median'] = usage_rate.median()
                cgroup_stats['cpu']['std'] = usage_rate.std()
                cgroup_stats['cpu']['min'] = usage_rate.min()
                cgroup_stats['cpu']['max'] = usage_rate.max()
                
                # Advanced statistics
                cgroup_stats['cpu']['coefficient_of_variation'] = cgroup_stats['cpu']['std'] / max(cgroup_stats['cpu']['mean'], 0.001)
                cgroup_stats['cpu']['p95'] = usage_rate.quantile(0.95)
                cgroup_stats['cpu']['p99'] = usage_rate.quantile(0.99)
                cgroup_stats['cpu']['skewness'] = usage_rate.skew()
                cgroup_stats['cpu']['kurtosis'] = usage_rate.kurtosis()
                
                # Time-based metrics
                rolling_mean = usage_rate.rolling(window=min(10, len(usage_rate))).mean()
                cgroup_stats['cpu']['trend_coefficient'] = (rolling_mean.iloc[-1] - rolling_mean.iloc[0]) / max(len(rolling_mean), 1)
            
            # Memory statistics (if available)
            if self.has_extended_metrics:
                memory = self.analyzer._safe_column(cgroup, 'memory_current')
                # Convert to numeric
                memory = pd.to_numeric(memory, errors='coerce')
                memory = memory / (1024 * 1024)  # Convert to MB
                
                if len(memory) > 1:
                    # Basic statistics
                    cgroup_stats['memory']['mean'] = memory.mean()
                    cgroup_stats['memory']['median'] = memory.median()
                    cgroup_stats['memory']['std'] = memory.std()
                    cgroup_stats['memory']['min'] = memory.min()
                    cgroup_stats['memory']['max'] = memory.max()
                    
                    # Advanced statistics
                    cgroup_stats['memory']['coefficient_of_variation'] = cgroup_stats['memory']['std'] / max(cgroup_stats['memory']['mean'], 0.001)
                    cgroup_stats['memory']['p95'] = memory.quantile(0.95)
                    cgroup_stats['memory']['p99'] = memory.quantile(0.99)
                    
                    # Growth metrics
                    if len(memory) >= 2:
                        cgroup_stats['memory']['growth_rate'] = (memory.iloc[-1] - memory.iloc[0]) / max(len(memory), 1)
            
            # I/O statistics (if available)
            io_read = self.analyzer._safe_column(cgroup, 'io_rbytes')
            
            if not io_read.empty and len(io_read) > 1:
                # Convert to numeric
                io_read = pd.to_numeric(io_read, errors='coerce')
                io_read = io_read / (1024 * 1024)  # Convert to MB
                
                # Calculate I/O rates
                io_read_rate = io_read.diff() / self.df['elapsed_sec'].diff()
                
                if len(io_read_rate) > 1:
                    io_read_rate = io_read_rate.dropna()
                    cgroup_stats['io']['read_rate_mean'] = io_read_rate.mean()
                    cgroup_stats['io']['read_rate_max'] = io_read_rate.max()
            
            statistics[cgroup] = cgroup_stats
                
        return statistics