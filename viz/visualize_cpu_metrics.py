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

def load_and_prepare_data(csv_file):
    """Load and prepare the CSV data for visualization."""
    df = pd.read_csv(csv_file)
    # Convert timestamps to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    return df

def plot_cpu_usage(df, output_dir):
    """Plot CPU usage (total, user, system) and usage rate."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Convert microseconds to seconds
    df['cpu_usage_sec'] = df['mycpu_cpu_usage_usec'] / 1e6
    df['cpu_user_sec'] = df['mycpu_cpu_user_usec'] / 1e6
    df['cpu_system_sec'] = df['mycpu_cpu_system_usec'] / 1e6
    
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

def plot_cpu_throttling(df, output_dir):
    """Plot CPU throttling metrics."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Plot number of periods and throttled periods
    ax1.plot(df['elapsed_sec'], df['mycpu_cpu_nr_periods'], label='Total Periods')
    ax1.plot(df['elapsed_sec'], df['mycpu_cpu_nr_throttled'], label='Throttled Periods')
    ax1.set_title('CPU Periods and Throttling')
    ax1.set_xlabel('Elapsed Time (seconds)')
    ax1.set_ylabel('Count')
    ax1.legend()
    ax1.grid(True)
    
    # Plot throttled time
    throttled_ms = df['mycpu_cpu_throttled_usec'] / 1000  # Convert to milliseconds
    ax2.plot(df['elapsed_sec'], throttled_ms, label='Throttled Time', color='red')
    ax2.set_title('CPU Throttled Time')
    ax2.set_xlabel('Elapsed Time (seconds)')
    ax2.set_ylabel('Throttled Time (ms)')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'cpu_throttling.png')
    plt.close()

def plot_cpu_pressure(df, output_dir):
    """Plot CPU pressure metrics."""
    plt.figure(figsize=(12, 6))
    
    plt.plot(df['elapsed_sec'], df['mycpu_cpu_pressure_some_avg10'], 
             label='Some Pressure (10s avg)')
    plt.plot(df['elapsed_sec'], df['mycpu_cpu_pressure_full_avg10'], 
             label='Full Pressure (10s avg)')
    
    plt.title('CPU Pressure Over Time')
    plt.xlabel('Elapsed Time (seconds)')
    plt.ylabel('Pressure Value')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_dir / 'cpu_pressure.png')
    plt.close()

def plot_cpu_burst(df, output_dir):
    """Plot CPU burst metrics."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Plot number of bursts
    ax1.plot(df['elapsed_sec'], df['mycpu_cpu_nr_bursts'], label='Burst Events')
    ax1.set_title('CPU Burst Events')
    ax1.set_xlabel('Elapsed Time (seconds)')
    ax1.set_ylabel('Number of Bursts')
    ax1.legend()
    ax1.grid(True)
    
    # Plot burst time
    burst_ms = df['mycpu_cpu_burst_usec'] / 1000  # Convert to milliseconds
    ax2.plot(df['elapsed_sec'], burst_ms, label='Burst Time', color='orange')
    ax2.set_title('CPU Burst Time')
    ax2.set_xlabel('Elapsed Time (seconds)')
    ax2.set_ylabel('Burst Time (ms)')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'cpu_burst.png')
    plt.close()

def plot_cpu_scheduling(df, output_dir):
    """Plot CPU scheduling parameters (weight, quota, period)."""
    plt.figure(figsize=(12, 6))
    
    # Create normalized values for better visualization
    max_val = max(df['mycpu_cpu_max_quota'].max(), df['mycpu_cpu_max_period'].max())
    
    # Plot scheduling parameters
    plt.plot(df['elapsed_sec'], df['mycpu_cpu_weight'], 
             label='CPU Weight', color='blue')
    plt.plot(df['elapsed_sec'], 
             df['mycpu_cpu_max_quota'].replace('max', str(max_val)).astype(float), 
             label='CPU Max Quota', color='red')
    plt.plot(df['elapsed_sec'], df['mycpu_cpu_max_period'], 
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

def plot_cpu_correlations(df, output_dir):
    """Plot correlations between different CPU metrics."""
    plt.figure(figsize=(15, 12))
    
    # Calculate CPU usage rates
    df['cpu_usage_rate'] = df['mycpu_cpu_usage_usec'].diff() / df['elapsed_sec'].diff()
    df['cpu_user_rate'] = df['mycpu_cpu_user_usec'].diff() / df['elapsed_sec'].diff()
    df['cpu_system_rate'] = df['mycpu_cpu_system_usec'].diff() / df['elapsed_sec'].diff()
    
    # Select relevant CPU metrics for correlation
    cpu_metrics = {
        'CPU Usage Rate': 'cpu_usage_rate',
        'User CPU Rate': 'cpu_user_rate',
        'System CPU Rate': 'cpu_system_rate',
        'CPU Periods': 'mycpu_cpu_nr_periods',
        'Throttled Count': 'mycpu_cpu_nr_throttled',
        'Throttled Time': 'mycpu_cpu_throttled_usec',
        'Burst Count': 'mycpu_cpu_nr_bursts',
        'Burst Time': 'mycpu_cpu_burst_usec',
        'Some Pressure': 'mycpu_cpu_pressure_some_avg10',
        'Full Pressure': 'mycpu_cpu_pressure_full_avg10',
        'CPU Weight': 'mycpu_cpu_weight'
    }
    
    # Create correlation matrix
    corr_matrix = df[cpu_metrics.values()].corr()
    
    # Plot correlation heatmap
    mask = np.triu(np.ones_like(corr_matrix), k=1)  # Mask upper triangle
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr_matrix,
                xticklabels=cpu_metrics.keys(),
                yticklabels=cpu_metrics.keys(),
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

def plot_cpu_heatmap(df, output_dir):
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
        args = parser.parse_args()
        
        # Set up paths
        csv_file = Path(args.csv)
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
            
        output_dir = csv_file.parent / 'cpu_plots'
        output_dir.mkdir(exist_ok=True)
        
        # Load data
        print("Loading data from CSV...")
        df = load_and_prepare_data(csv_file)
        
        # Create plots
        print("Generating CPU usage plots...")
        plot_cpu_usage(df, output_dir)
        plot_cpu_throttling(df, output_dir)
        plot_cpu_pressure(df, output_dir)
        plot_cpu_burst(df, output_dir)
        plot_cpu_scheduling(df, output_dir)
        plot_cpu_correlations(df, output_dir)
        plot_cpu_heatmap(df, output_dir)
        
        # Print statistics
        print("\nKey Statistical Insights:")
        print("========================")
        total_time = df['elapsed_sec'].max() - df['elapsed_sec'].min()
        throttled_time = df['mycpu_cpu_throttled_usec'].sum() / 1e6
        burst_time = df['mycpu_cpu_burst_usec'].sum() / 1e6
        print(f"1. Total monitoring time: {total_time:.2f} seconds")
        print(f"2. Time spent throttled: {throttled_time:.2f}s ({(throttled_time/total_time)*100:.2f}%)")
        print(f"3. Time spent in burst: {burst_time:.2f}s ({(burst_time/total_time)*100:.2f}%)")
        print(f"4. Average CPU pressure: {df['mycpu_cpu_pressure_some_avg10'].mean():.2f}%")
        print(f"\nPlots have been saved to: {output_dir}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()