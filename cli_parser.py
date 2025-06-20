# cgroup_analyzer/cli_parser.py
"""
CLI argument parsing module
"""

import argparse
from pathlib import Path
import sys
import datetime


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