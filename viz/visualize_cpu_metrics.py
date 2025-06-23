#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from pathlib import Path

# Set the style for better visualization
plt.style.use('seaborn-v0_8')
sns.set_theme(style="darkgrid")
sns.set_palette("husl")

def detect_cgroup_name(df):
    """Detect cgroup name from DataFrame columns."""
    # Find columns that match cgroup metrics pattern (excluding timestamp and elapsed_sec)
    cgroup_columns = [col for col in df.columns if col not in ['timestamp', 'elapsed_sec']]
    
    if not cgroup_columns:
        raise ValueError("No cgroup metric columns found in the DataFrame")
    
    # Extract the cgroup name from the first cgroup metric column
    # Format is expected to be {cgroup_name}_{metric_name}
    first_column = cgroup_columns[0]
    cgroup_name = first_column.split('_')[0]
    
    # Validate that this prefix is consistent across cgroup columns
    if not all(col.startswith(f"{cgroup_name}_") for col in cgroup_columns):
        raise ValueError("Inconsistent cgroup prefixes found in column names")
        
    return cgroup_name

def create_column_mapping(df, cgroup_name):
    """Create mapping between generic metric names and actual column names."""
    mapping = {}
    generic_metrics = [
        'cpu_usage_usec', 'cpu_user_usec', 'cpu_system_usec',
        'cpu_nr_periods', 'cpu_nr_throttled', 'cpu_throttled_usec',
        'cpu_nr_bursts', 'cpu_burst_usec', 'cpu_weight',
        'cpu_max_quota', 'cpu_max_period',
        'cpu_pressure_some_avg10', 'cpu_pressure_full_avg10'
    ]
    
    for metric in generic_metrics:
        column_name = f"{cgroup_name}_{metric}"
        if column_name in df.columns:
            mapping[metric] = column_name
    
    return mapping

def load_and_prepare_data(csv_file, cgroup_name=None):
    """Load and prepare the CSV data for visualization."""
    df = pd.read_csv(csv_file)
    # Convert timestamps to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    
    # Detect cgroup name if not provided
    if not cgroup_name:
        cgroup_name = detect_cgroup_name(df)
    
    return df, cgroup_name

def plot_cpu_usage(df, output_dir, column_map):
    """Plot CPU usage (total, user, system) and usage rate."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Convert microseconds to seconds
    df['cpu_usage_sec'] = df[column_map['cpu_usage_usec']] / 1e6
    df['cpu_user_sec'] = df[column_map['cpu_user_usec']] / 1e6
    df['cpu_system_sec'] = df[column_map['cpu_system_usec']] / 1e6
    
    # Calculate rate of change (usage per second)
    df['cpu_usage_rate'] = df['cpu_usage_sec'].diff() / df['elapsed_sec'].diff()
    df['cpu_user_rate'] = df['cpu_user_sec'].diff() / df['elapsed_sec'].diff()
    df['cpu_system_rate'] = df['cpu_system_sec'].diff() / df['elapsed_sec'].diff()
    
    # Plot cumulative usage
    ax1.plot(df['elapsed_sec'], df['cpu_usage_sec'], label='Total CPU')
    ax1.plot(df['elapsed_sec'], df['cpu_user_sec'], label='User CPU')
    ax1.plot(df['elapsed_sec'], df['cpu_system_sec'], label='System CPU')
    ax1.set_title('Cumulative CPU Usage Over Time')
    ax1.set_xlabel('Elapsed Time (seconds)')
    ax1.set_ylabel('CPU Time (seconds)')
    ax1.legend()
    ax1.grid(True)
    
    # Plot usage rate
    ax2.plot(df['elapsed_sec'], df['cpu_usage_rate'] * 100, label='Total CPU')
    ax2.plot(df['elapsed_sec'], df['cpu_user_rate'] * 100, label='User CPU')
    ax2.plot(df['elapsed_sec'], df['cpu_system_rate'] * 100, label='System CPU')
    ax2.set_title('CPU Usage Rate')
    ax2.set_xlabel('Elapsed Time (seconds)')
    ax2.set_ylabel('CPU Usage (%)')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'cpu_usage.png')
    plt.close()

def plot_cpu_throttling(df, output_dir, column_map):
    """Plot CPU throttling metrics."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Plot number of periods and throttled periods
    ax1.plot(df['elapsed_sec'], df[column_map['cpu_nr_periods']], label='Total Periods')
    ax1.plot(df['elapsed_sec'], df[column_map['cpu_nr_throttled']], label='Throttled Periods')
    ax1.set_title('CPU Periods and Throttling')
    ax1.set_xlabel('Elapsed Time (seconds)')
    ax1.set_ylabel('Count')
    ax1.legend()
    ax1.grid(True)
    
    # Plot throttled time
    throttled_ms = df[column_map['cpu_throttled_usec']] / 1000  # Convert to milliseconds
    ax2.plot(df['elapsed_sec'], throttled_ms, label='Throttled Time', color='red')
    ax2.set_title('CPU Throttled Time')
    ax2.set_xlabel('Elapsed Time (seconds)')
    ax2.set_ylabel('Throttled Time (ms)')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'cpu_throttling.png')
    plt.close()

def plot_cpu_pressure(df, output_dir, column_map):
    """Plot CPU pressure metrics."""
    plt.figure(figsize=(12, 6))
    
    plt.plot(df['elapsed_sec'], df[column_map['cpu_pressure_some_avg10']], 
             label='Some Pressure (10s avg)')
    plt.plot(df['elapsed_sec'], df[column_map['cpu_pressure_full_avg10']], 
             label='Full Pressure (10s avg)')
    
    plt.title('CPU Pressure Over Time')
    plt.xlabel('Elapsed Time (seconds)')
    plt.ylabel('Pressure Value')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_dir / 'cpu_pressure.png')
    plt.close()

def plot_cpu_burst(df, output_dir, column_map):
    """Plot CPU burst metrics."""
    # Check if burst metrics exist in the dataset
    if 'cpu_nr_bursts' not in column_map or 'cpu_burst_usec' not in column_map:
        print("CPU burst metrics not found in dataset, skipping burst plot")
        return
        
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Plot number of bursts
    ax1.plot(df['elapsed_sec'], df[column_map['cpu_nr_bursts']], label='Burst Events')
    ax1.set_title('CPU Burst Events')
    ax1.set_xlabel('Elapsed Time (seconds)')
    ax1.set_ylabel('Number of Bursts')
    ax1.legend()
    ax1.grid(True)
    
    # Plot burst time
    burst_ms = df[column_map['cpu_burst_usec']] / 1000  # Convert to milliseconds
    ax2.plot(df['elapsed_sec'], burst_ms, label='Burst Time', color='orange')
    ax2.set_title('CPU Burst Time')
    ax2.set_xlabel('Elapsed Time (seconds)')
    ax2.set_ylabel('Burst Time (ms)')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'cpu_burst.png')
    plt.close()

def plot_cpu_scheduling(df, output_dir, column_map):
    """Plot CPU scheduling parameters (weight, quota, period)."""
    # Check if scheduling metrics exist
    required_metrics = ['cpu_weight', 'cpu_max_quota', 'cpu_max_period']
    if not all(metric in column_map for metric in required_metrics):
        print("CPU scheduling metrics not found in dataset, skipping scheduling plot")
        return
        
    plt.figure(figsize=(12, 6))
    
    # Create normalized values for better visualization
    max_val = max(
        df[column_map['cpu_max_quota']].replace('max', str(float('inf'))).astype(float).max(),
        df[column_map['cpu_max_period']].max()
    )
    
    # Plot scheduling parameters
    plt.plot(df['elapsed_sec'], df[column_map['cpu_weight']], 
             label='CPU Weight', color='blue')
    plt.plot(df['elapsed_sec'], 
             df[column_map['cpu_max_quota']].replace('max', str(max_val)).astype(float), 
             label='CPU Max Quota', color='red')
    plt.plot(df['elapsed_sec'], df[column_map['cpu_max_period']], 
             label='CPU Period', color='green')
    
    plt.title('CPU Scheduling Parameters')
    plt.xlabel('Elapsed Time (seconds)')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True)
    
    # Add a second y-axis for weight
    ax2 = plt.gca().twinx()
    ax2.set_ylabel('CPU Weight', color='blue')
    ax2.tick_params(axis='y', labelcolor='blue')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'cpu_scheduling.png')
    plt.close()

def plot_cpu_correlations(df, output_dir, column_map):
    """Plot correlations between different CPU metrics."""
    plt.figure(figsize=(15, 12))
    
    # Calculate CPU usage rates
    df['cpu_usage_rate'] = df[column_map['cpu_usage_usec']].diff() / df['elapsed_sec'].diff()
    df['cpu_user_rate'] = df[column_map['cpu_user_usec']].diff() / df['elapsed_sec'].diff()
    df['cpu_system_rate'] = df[column_map['cpu_system_usec']].diff() / df['elapsed_sec'].diff()
    
    # Select relevant CPU metrics for correlation
    cpu_metrics = {
        'CPU Usage Rate': 'cpu_usage_rate',
        'User CPU Rate': 'cpu_user_rate',
        'System CPU Rate': 'cpu_system_rate',
        'CPU Periods': column_map['cpu_nr_periods'],
        'Throttled Count': column_map['cpu_nr_throttled'],
        'Throttled Time': column_map['cpu_throttled_usec'],
    }
    
    # Add optional metrics if they exist
    if 'cpu_nr_bursts' in column_map:
        cpu_metrics['Burst Count'] = column_map['cpu_nr_bursts']
    if 'cpu_burst_usec' in column_map:
        cpu_metrics['Burst Time'] = column_map['cpu_burst_usec']
    if 'cpu_pressure_some_avg10' in column_map:
        cpu_metrics['Some Pressure'] = column_map['cpu_pressure_some_avg10']
    if 'cpu_pressure_full_avg10' in column_map:
        cpu_metrics['Full Pressure'] = column_map['cpu_pressure_full_avg10']
    if 'cpu_weight' in column_map:
        cpu_metrics['CPU Weight'] = column_map['cpu_weight']
    
    # Create correlation matrix
    corr_matrix = df[list(cpu_metrics.values())].corr()
    
    # Plot correlation heatmap
    mask = np.triu(np.ones_like(corr_matrix), k=1)  # Mask upper triangle
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr_matrix,
                xticklabels=list(cpu_metrics.keys()),
                yticklabels=list(cpu_metrics.keys()),
                annot=True,
                fmt='.2f',
                cmap='coolwarm',
                center=0,
                square=True,
                mask=mask,
                vmin=-1, vmax=1,
                cbar_kws={'label': 'Correlation Coefficient'})
    
    plt.title('CPU Metrics Correlation Heatmap')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / 'cpu_correlations.png', dpi=300, bbox_inches='tight')
    plt.close()

def plot_cpu_heatmap(df, output_dir, column_map):
    """Generate a heatmap of CPU usage intensity over time."""
    # Create time bins (every minute) and usage intensity bins
    # Create time bins
    df['time_bin'] = pd.cut(df['elapsed_sec'], bins=50)  # 50 time segments
    
    # Calculate CPU usage percentage
    df['cpu_usage_pct'] = df['cpu_usage_rate'] * 100
    
    try:
        # Try to create quantile bins, but handle cases with duplicate values
        df['intensity_bin'] = pd.qcut(
            df['cpu_usage_pct'], 
            q=10, 
            labels=['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', 
                   '50-60%', '60-70%', '70-80%', '80-90%', '90-100%'],
            duplicates='drop'
        )
    except ValueError:
        # If quantile binning fails, use regular bins
        df['intensity_bin'] = pd.cut(
            df['cpu_usage_pct'],
            bins=10,
            labels=['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', 
                   '50-60%', '60-70%', '70-80%', '80-90%', '90-100%']
        )
    
    # Create pivot table for heatmap
    heatmap_data = pd.crosstab(df['time_bin'], df['intensity_bin'])
    
    # Create heatmap
    plt.figure(figsize=(15, 8))
    sns.heatmap(heatmap_data, cmap='YlOrRd', annot=True, fmt='d', cbar_kws={'label': 'Count'})
    
    plt.title('CPU Usage Intensity Heatmap')
    plt.xlabel('CPU Usage Intensity')
    plt.ylabel('Time Period')
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'cpu_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()

def main():
    try:
        parser = argparse.ArgumentParser(description='Generate CPU metrics visualizations')
        parser.add_argument('--csv', type=str, required=True,
                          help='Path to the input CSV file')
        parser.add_argument('--cgroup-name', type=str, required=False,
                          help='Name of the cgroup in the CSV headers')
        args = parser.parse_args()
        
        # Set up paths
        csv_file = Path(args.csv)
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
            
        output_base = csv_file.with_suffix('')  # Remove .csv extension but keep full path
        output_dir = output_base / 'cpu_plots'
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Load data
        print("Loading data from CSV...")
        df, cgroup_name = load_and_prepare_data(csv_file, args.cgroup_name)
        
        # Create mapping from generic metric names to actual column names
        column_map = create_column_mapping(df, cgroup_name)
        print(f"Using cgroup name: {cgroup_name}")
        
        # Create plots
        print("Generating CPU usage plots...")
        plot_cpu_usage(df, output_dir, column_map)
        plot_cpu_throttling(df, output_dir, column_map)
        plot_cpu_pressure(df, output_dir, column_map)
        plot_cpu_burst(df, output_dir, column_map)
        plot_cpu_scheduling(df, output_dir, column_map)
        plot_cpu_correlations(df, output_dir, column_map)
        plot_cpu_heatmap(df, output_dir, column_map)
        
        # Print statistics
        print("\nKey Statistical Insights:")
        print("========================")
        total_time = df['elapsed_sec'].max() - df['elapsed_sec'].min()
        throttled_time = df[column_map['cpu_throttled_usec']].sum() / 1e6
        
        print(f"1. Total monitoring time: {total_time:.2f} seconds")
        print(f"2. Time spent throttled: {throttled_time:.2f}s ({(throttled_time/total_time)*100:.2f}%)")
        
        # Report burst stats if available
        if 'cpu_nr_bursts' in column_map and 'cpu_burst_usec' in column_map:
            burst_time = df[column_map['cpu_burst_usec']].sum() / 1e6
            print(f"3. Time spent in burst: {burst_time:.2f}s ({(burst_time/total_time)*100:.2f}%)")
        
        # Report pressure if available
        if 'cpu_pressure_some_avg10' in column_map:
            print(f"4. Average CPU pressure: {df[column_map['cpu_pressure_some_avg10']].mean():.2f}%")
        
        print(f"\nPlots have been saved to: {output_dir}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
