#!/usr/bin/env python3
"""
Cgroup Monitor Data Analysis and Visualization Tool
Analyzes CSV data from the cgroup monitoring script with comprehensive visualizations and intelligent interpretation
"""

import argparse
from pathlib import Path

from analyzer_core import CgroupAnalyzer
from interpreter import CgroupInterpreter
from cpu_analysis import analyze_cpu_performance
from memory_analysis import analyze_memory_performance
from pressure_analysis import analyze_system_pressure
from dashboard import create_performance_dashboard
from report_generator import generate_report
from data_exporter import export_processed_data
from visualization_utils import plot_advanced_visualizations, plot_workload_heatmap, fingerprint_workload_patterns


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Analyze cgroup monitoring data')
    parser.add_argument('csv_file', help='CSV file from cgroup monitor')
    parser.add_argument('-o', '--output', default='analysis_output',
                        help='Output directory for results')
    parser.add_argument('--cpu-only', action='store_true',
                        help='Only perform CPU analysis')
    parser.add_argument('--memory-only', action='store_true',
                        help='Only perform memory analysis')
    parser.add_argument('--dashboard-only', action='store_true',
                        help='Only create performance dashboard')
    parser.add_argument('--report-only', action='store_true',
                        help='Only generate text report')
    parser.add_argument('--export-data', action='store_true',
                        help='Export processed data')
    parser.add_argument('--interpret', action='store_true', default=True,
                        help='Perform enhanced data interpretation (enabled by default)')
    parser.add_argument('--advanced-viz', action='store_true', default=True,
                        help='Generate advanced visualizations (enabled by default)')
    parser.add_argument('--workload-heatmap', action='store_true', default=True,
                        help='Generate workload intensity heatmaps (enabled by default)')
    parser.add_argument('--fingerprint', action='store_true', default=True,
                        help='Generate workload fingerprints (enabled by default)')
    parser.add_argument('--no-interpret', dest='interpret', action='store_false',
                        help='Disable enhanced data interpretation')
    parser.add_argument('--no-advanced-viz', dest='advanced_viz', action='store_false',
                        help='Disable advanced visualizations')
    parser.add_argument('--no-workload-heatmap', dest='workload_heatmap', action='store_false',
                        help='Disable workload intensity heatmaps')
    parser.add_argument('--no-fingerprint', dest='fingerprint', action='store_false',
                        help='Disable workload fingerprints')
    
    return parser.parse_args()


def main():
    """Main function with command line interface"""
    args = parse_args()
    
    # Validate input file
    if not Path(args.csv_file).exists():
        print(f"Error: CSV file '{args.csv_file}' not found")
        exit(1)
    
    # Create analyzer
    try:
        analyzer = CgroupAnalyzer(args.csv_file, args.output)
    except Exception as e:
        print(f"Error initializing analyzer: {e}")
        exit(1)
    
    # Run analysis based on arguments
    if args.cpu_only:
        analyze_cpu_performance(analyzer)
    elif args.memory_only:
        analyze_memory_performance(analyzer)
    elif args.dashboard_only:
        create_performance_dashboard(analyzer)
    elif args.report_only:
        report = generate_report(analyzer)
        print("\n" + report)
    else:
        # Run full analysis
        analyze_cpu_performance(analyzer)
        analyze_memory_performance(analyzer)
        analyze_system_pressure(analyzer)
        create_performance_dashboard(analyzer)
        generate_report(analyzer)
    
    if args.export_data:
        export_processed_data(analyzer)
    
    if args.interpret or args.advanced_viz or args.workload_heatmap or args.fingerprint:
        interpreter = CgroupInterpreter(analyzer)
        
        if args.interpret:
            print("\n=== Enhanced Data Interpretation ===")
            # Detect anomalies
            anomalies = interpreter.detect_anomalies()
            anomaly_count = 0
            if anomalies:
                anomaly_count = sum(
                    len(cg_data.get('cpu', {}).get('timestamps', [])) + 
                    len(cg_data.get('memory', {}).get('timestamps', []))
                    for cg_data in anomalies.values()
                )
            print(f"\nDetected {anomaly_count} anomalies across all cgroups")
            
            # Cluster anomalies
            clusters = interpreter.cluster_anomalies()
            cluster_count = sum(len(cg_clusters['cpu']) + len(cg_clusters['memory']) 
                              for cg_clusters in clusters.values())
            print(f"Grouped into {cluster_count} anomaly clusters")
            
            # Identify usage patterns
            patterns = interpreter.identify_usage_patterns()
            print("\nResource Usage Patterns:")
            for cgroup, pattern in patterns.items():
                print(f"  {cgroup}:")
                print(f"    CPU: {pattern['cpu_pattern']}")
                print(f"    Memory: {pattern['memory_pattern']}")
            

            
            # Generate fingerprints if requested directly or as part of interpret
            if args.fingerprint or args.interpret:
                fingerprints = fingerprint_workload_patterns(interpreter)
                print("\nWorkload Fingerprints:")
                for cgroup, fingerprint in fingerprints.items():
                    print(f"  {cgroup}: {fingerprint['workload_type']}")
                    if fingerprint['memory_behavior'] != "N/A":
                        print(f"    Memory behavior: {fingerprint['memory_behavior']}")
                    if fingerprint['has_periodicity'] == "True":
                        print(f"    Periodic pattern detected (period: {fingerprint['dominant_period_lag']})")
                    print(f"    Burstiness score: {fingerprint['burstiness']}")
                    print(f"    System/User ratio: {fingerprint['cpu_system_user_ratio']}")
                    if fingerprint.get('cpu_burst_tendency', 'N/A') != 'N/A':
                        print(f"    CPU burst tendency: {fingerprint['cpu_burst_tendency']} ({fingerprint['cpu_burst_score']}%)")
            
            # Generate insights
            insights = interpreter.generate_insights()
            print("\nKey Insights:")
            for cgroup, cg_insights in insights.items():
                print(f"\n  {cgroup}:")
                for insight in cg_insights:
                    print(f"    {insight}")
        
        # Generate advanced visualizations
        if args.advanced_viz:
            print("\nGenerating advanced visualizations...")
            plot_advanced_visualizations(interpreter, Path(args.output))
            print(f"Advanced visualizations saved to: {args.output}/advanced_analysis/")
        

        
        # Generate workload heatmaps
        if args.workload_heatmap:
            print("\nGenerating workload intensity heatmaps...")
            plot_workload_heatmap(interpreter, Path(args.output))
            print(f"Workload heatmaps saved to: {args.output}/")
    
    print(f"\nAnalysis complete! Results saved to: {analyzer.output_dir}")


if __name__ == "__main__":
    main()
