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

def plot_pids_usage(df, output_dir):
    """Plot PIDs usage metrics."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Plot absolute numbers
    ax1.plot(df['elapsed_sec'], df['mycpu_pids_current'], label='Current PIDs')
    ax1.plot(df['elapsed_sec'], df['mycpu_pids_peak'], label='Peak PIDs')
    if df['mycpu_pids_max'].iloc[0] != 'max':
        ax1.axhline(y=float(df['mycpu_pids_max'].iloc[0]), 
                   color='r', linestyle='--', label='Max PIDs Limit')
    ax1.plot(df['elapsed_sec'], df['mycpu_cgroup_procs_count'], 
             label='Process Count', linestyle=':')
    
    ax1.set_title('PIDs Usage Over Time')
    ax1.set_xlabel('Elapsed Time (seconds)')
    ax1.set_ylabel('Number of PIDs')
    ax1.legend()
    ax1.grid(True)
    
    # Plot usage percentage if limit is set
    if df['mycpu_pids_max'].iloc[0] != 'max':
        max_pids = float(df['mycpu_pids_max'].iloc[0])
        current_pct = (df['mycpu_pids_current'] / max_pids) * 100
        peak_pct = (df['mycpu_pids_peak'] / max_pids) * 100
        procs_pct = (df['mycpu_cgroup_procs_count'] / max_pids) * 100
        
        ax2.plot(df['elapsed_sec'], current_pct, label='Current PIDs %')
        ax2.plot(df['elapsed_sec'], peak_pct, label='Peak PIDs %')
        ax2.plot(df['elapsed_sec'], procs_pct, label='Process Count %', linestyle=':')
        ax2.axhline(y=100, color='r', linestyle='--', label='Limit')
    else:
        # If no limit, show percentage relative to peak
        peak = df['mycpu_pids_peak'].max()
        current_pct = (df['mycpu_pids_current'] / peak) * 100
        procs_pct = (df['mycpu_cgroup_procs_count'] / peak) * 100
        
        ax2.plot(df['elapsed_sec'], current_pct, label='Current PIDs %')
        ax2.plot(df['elapsed_sec'], procs_pct, label='Process Count %', linestyle=':')
    
    ax2.set_title('PIDs Usage Percentage')
    ax2.set_xlabel('Elapsed Time (seconds)')
    ax2.set_ylabel('Usage %')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'pids_usage.png', dpi=300, bbox_inches='tight')
    plt.close()

def plot_pids_distribution(df, output_dir):
    """Plot PIDs distribution and statistics."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Calculate PIDs to processes ratio
    pids_proc_ratio = df['mycpu_pids_current'] / df['mycpu_cgroup_procs_count']
    
    # Histogram of PIDs per process ratio
    sns.histplot(data=pids_proc_ratio, ax=ax1, bins=30)
    ax1.axvline(pids_proc_ratio.mean(), color='r', linestyle='--', 
                label=f'Mean: {pids_proc_ratio.mean():.2f}')
    ax1.set_title('Distribution of PIDs per Process Ratio')
    ax1.set_xlabel('PIDs/Process Ratio')
    ax1.set_ylabel('Frequency')
    ax1.legend()
    
    # Box plot of PIDs and processes
    plot_data = pd.DataFrame({
        'Current PIDs': df['mycpu_pids_current'],
        'Process Count': df['mycpu_cgroup_procs_count']
    })
    sns.boxplot(data=plot_data, ax=ax2)
    ax2.set_title('PIDs and Processes Distribution')
    ax2.set_ylabel('Count')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'pids_distribution.png', dpi=300, bbox_inches='tight')
    plt.close()

def plot_pids_correlations(df, output_dir):
    """Plot correlations with other metrics."""
    # Calculate PIDs rate of change
    df['pids_rate'] = df['mycpu_pids_current'].diff() / df['elapsed_sec'].diff()
    
    # Select metrics for correlation
    metrics = {
        'Current PIDs': 'mycpu_pids_current',
        'Peak PIDs': 'mycpu_pids_peak',
        'Process Count': 'mycpu_cgroup_procs_count',
        'PIDs Rate': 'pids_rate',
        'Memory Usage': 'mycpu_memory_current',
        'CPU Usage': 'mycpu_cpu_usage_usec',
        'CPU Pressure': 'mycpu_cpu_pressure_some_avg10',
        'Memory Pressure': 'mycpu_memory_pressure_some_avg10'
    }
    
    # Create correlation matrix
    corr_matrix = df[metrics.values()].corr()
    
    # Plot correlation heatmap
    plt.figure(figsize=(10, 8))
    mask = np.triu(np.ones_like(corr_matrix), k=1)
    sns.heatmap(corr_matrix,
                xticklabels=metrics.keys(),
                yticklabels=metrics.keys(),
                annot=True,
                fmt='.2f',
                cmap='coolwarm',
                center=0,
                square=True,
                mask=mask,
                vmin=-1, vmax=1,
                cbar_kws={'label': 'Correlation Coefficient'})
    
    plt.title('PIDs Metrics Correlations')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / 'pids_correlations.png', dpi=300, bbox_inches='tight')
    plt.close()

def main():
    try:
        parser = argparse.ArgumentParser(description='Generate PIDs metrics visualizations')
        parser.add_argument('--csv', type=str, required=True,
                          help='Path to the input CSV file')
        args = parser.parse_args()
        
        # Set up paths
        csv_file = Path(args.csv)
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
            
        output_dir = csv_file.parent / 'pids_plots'
        output_dir.mkdir(exist_ok=True)
        
        # Load data
        print("Loading data from CSV...")
        df = load_and_prepare_data(csv_file)
        
        # Create plots
        print("Generating PIDs usage plots...")
        plot_pids_usage(df, output_dir)
        plot_pids_distribution(df, output_dir)
        plot_pids_correlations(df, output_dir)
        
        # Print statistics
        print("\nKey PIDs Statistical Insights:")
        print("============================")
        current_pids = df['mycpu_pids_current'].iloc[-1]
        peak_pids = df['mycpu_pids_peak'].max()
        avg_procs = df['mycpu_cgroup_procs_count'].mean()
        pids_proc_ratio = (df['mycpu_pids_current'] / df['mycpu_cgroup_procs_count']).mean()
        
        print(f"1. Current PIDs count: {current_pids}")
        print(f"2. Peak PIDs count: {peak_pids}")
        print(f"3. Average process count: {avg_procs:.2f}")
        print(f"4. Average PIDs per process: {pids_proc_ratio:.2f}")
        print(f"\nPlots have been saved to: {output_dir}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()