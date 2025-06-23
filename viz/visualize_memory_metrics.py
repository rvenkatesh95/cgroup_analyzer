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
        'memory_current', 'memory_peak', 'memory_max',
        'memory_anon', 'memory_file', 'memory_kernel', 
        'memory_swap_current', 'memory_swap_max',
        'memory_oom_events', 'memory_oom_kill_events',
        'memory_pressure_some_avg10', 'memory_pressure_full_avg10'
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

def plot_memory_usage(df, output_dir, column_map):
    """Plot memory usage metrics."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    
    # Convert to MB for better readability
    df['memory_current_mb'] = df[column_map['memory_current']] / (1024 * 1024)
    df['memory_peak_mb'] = df[column_map['memory_peak']] / (1024 * 1024)
    df['memory_max_mb'] = df[column_map['memory_max']].replace('max', str(float('inf'))).astype(float) / (1024 * 1024)
    
    # Plot current and peak memory
    ax1.plot(df['elapsed_sec'], df['memory_current_mb'], label='Current Memory')
    ax1.plot(df['elapsed_sec'], df['memory_peak_mb'], label='Peak Memory')
    if not np.isinf(df['memory_max_mb'].iloc[0]):
        ax1.axhline(y=df['memory_max_mb'].iloc[0], color='r', linestyle='--', label='Memory Limit')
    ax1.set_title('Memory Usage Over Time')
    ax1.set_xlabel('Elapsed Time (seconds)')
    ax1.set_ylabel('Memory Usage (MB)')
    ax1.legend()
    ax1.grid(True)
    
    # Plot memory usage percentage if limit is set
    if not np.isinf(df['memory_max_mb'].iloc[0]):
        usage_pct = (df['memory_current_mb'] / df['memory_max_mb'].iloc[0]) * 100
        peak_pct = (df['memory_peak_mb'] / df['memory_max_mb'].iloc[0]) * 100
        ax2.plot(df['elapsed_sec'], usage_pct, label='Current Usage')
        ax2.plot(df['elapsed_sec'], peak_pct, label='Peak Usage')
        ax2.axhline(y=100, color='r', linestyle='--', label='Limit')
    else:
        # If no limit, show usage relative to peak
        usage_pct = (df['memory_current_mb'] / df['memory_peak_mb'].max()) * 100
        ax2.plot(df['elapsed_sec'], usage_pct, label='Current Usage')
    ax2.set_title('Memory Usage Percentage')
    ax2.set_xlabel('Elapsed Time (seconds)')
    ax2.set_ylabel('Usage %')
    ax2.legend()
    ax2.grid(True)
    
    # Plot memory components absolute values
    df['anon_mb'] = df[column_map['memory_anon']] / (1024 * 1024)
    df['file_mb'] = df[column_map['memory_file']] / (1024 * 1024)
    df['kernel_mb'] = df[column_map['memory_kernel']] / (1024 * 1024)
    
    ax3.stackplot(df['elapsed_sec'], 
                 [df['anon_mb'], df['file_mb'], df['kernel_mb']],
                 labels=['Anonymous Memory', 'File-backed Memory', 'Kernel Memory'])
    ax3.set_title('Memory Components')
    ax3.set_xlabel('Elapsed Time (seconds)')
    ax3.set_ylabel('Memory Usage (MB)')
    ax3.legend(loc='upper left', bbox_to_anchor=(1, 1))
    ax3.grid(True)
    
    # Plot memory components as percentages
    total_memory = df['anon_mb'] + df['file_mb'] + df['kernel_mb']
    anon_pct = (df['anon_mb'] / total_memory) * 100
    file_pct = (df['file_mb'] / total_memory) * 100
    kernel_pct = (df['kernel_mb'] / total_memory) * 100
    
    ax4.stackplot(df['elapsed_sec'], 
                 [anon_pct, file_pct, kernel_pct],
                 labels=['Anonymous Memory', 'File-backed Memory', 'Kernel Memory'])
    ax4.set_title('Memory Components Distribution')
    ax4.set_xlabel('Elapsed Time (seconds)')
    ax4.set_ylabel('Percentage')
    ax4.legend(loc='upper left', bbox_to_anchor=(1, 1))
    ax4.grid(True)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'memory_usage.png', bbox_inches='tight', dpi=300)
    plt.close()

def plot_memory_events(df, output_dir, column_map):
    """Plot memory events (OOM events)."""
    plt.figure(figsize=(12, 6))
    
    plt.plot(df['elapsed_sec'], df[column_map['memory_oom_events']], 
             label='OOM Events', marker='o')
    plt.plot(df['elapsed_sec'], df[column_map['memory_oom_kill_events']], 
             label='OOM Kill Events', marker='x')
    
    plt.title('Memory OOM Events')
    plt.xlabel('Elapsed Time (seconds)')
    plt.ylabel('Event Count')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_dir / 'memory_events.png')
    plt.close()

def plot_memory_pressure(df, output_dir, column_map):
    """Plot memory pressure metrics."""
    plt.figure(figsize=(12, 6))
    
    plt.plot(df['elapsed_sec'], df[column_map['memory_pressure_some_avg10']], 
             label='Some Pressure (10s avg)')
    plt.plot(df['elapsed_sec'], df[column_map['memory_pressure_full_avg10']], 
             label='Full Pressure (10s avg)')
    
    plt.title('Memory Pressure Over Time')
    plt.xlabel('Elapsed Time (seconds)')
    plt.ylabel('Pressure Value')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_dir / 'memory_pressure.png')
    plt.close()

def plot_memory_swap(df, output_dir, column_map):
    """Plot swap usage metrics."""
    plt.figure(figsize=(12, 6))
    
    # Convert to MB
    df['swap_current_mb'] = df[column_map['memory_swap_current']] / (1024 * 1024)
    swap_max = df[column_map['memory_swap_max']].replace('max', str(float('inf'))).astype(float) / (1024 * 1024)
    
    plt.plot(df['elapsed_sec'], df['swap_current_mb'], label='Swap Usage')
    if not np.isinf(swap_max.iloc[0]):
        plt.axhline(y=swap_max.iloc[0], color='r', linestyle='--', label='Swap Limit')
    
    plt.title('Swap Usage Over Time')
    plt.xlabel('Elapsed Time (seconds)')
    plt.ylabel('Swap Usage (MB)')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_dir / 'memory_swap.png')
    plt.close()

def plot_memory_correlations(df, output_dir, column_map):
    """Plot correlations between different memory metrics."""
    # Calculate memory rates
    df['memory_rate'] = df[column_map['memory_current']].diff() / df['elapsed_sec'].diff()
    
    # Select relevant memory metrics
    memory_metrics = {
        'Memory Usage': column_map['memory_current'],
        'Memory Rate': 'memory_rate',
        'Anonymous Mem': column_map['memory_anon'],
        'File Mem': column_map['memory_file'],
        'Kernel Mem': column_map['memory_kernel'],
        'Swap Usage': column_map['memory_swap_current'],
        'OOM Events': column_map['memory_oom_events'],
        'Some Pressure': column_map['memory_pressure_some_avg10'],
        'Full Pressure': column_map['memory_pressure_full_avg10']
    }
    
    # Create correlation matrix
    corr_matrix = df[memory_metrics.values()].corr()
    
    # Plot correlation heatmap
    mask = np.triu(np.ones_like(corr_matrix), k=1)
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr_matrix,
                xticklabels=memory_metrics.keys(),
                yticklabels=memory_metrics.keys(),
                annot=True,
                fmt='.2f',
                cmap='coolwarm',
                center=0,
                square=True,
                mask=mask,
                vmin=-1, vmax=1,
                cbar_kws={'label': 'Correlation Coefficient'})
    
    plt.title('Memory Metrics Correlation Heatmap')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / 'memory_correlations.png', dpi=300, bbox_inches='tight')
    plt.close()

def plot_memory_heatmap(df, output_dir, column_map):
    """Generate a heatmap of memory usage intensity over time."""
    # Create time bins (every minute) and usage intensity bins
    # Create time bins
    df['time_bin'] = pd.cut(df['elapsed_sec'], bins=50)  # 50 time segments
    
    # Calculate memory usage percentage
    max_memory = df[column_map['memory_max']].replace('max', str(float('inf'))).astype(float)
    if np.all(np.isinf(max_memory)):
        # If no memory limit is set, calculate percentage relative to peak memory
        max_memory = df[column_map['memory_peak']].max()
    
    df['memory_usage_pct'] = (df[column_map['memory_current']] / max_memory) * 100
    
    try:
        # Try to create quantile bins, but handle cases with duplicate values
        df['intensity_bin'] = pd.qcut(
            df['memory_usage_pct'], 
            q=10, 
            labels=['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', 
                   '50-60%', '60-70%', '70-80%', '80-90%', '90-100%'],
            duplicates='drop'
        )
    except ValueError:
        # If quantile binning fails, use regular bins
        df['intensity_bin'] = pd.cut(
            df['memory_usage_pct'],
            bins=10,
            labels=['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', 
                   '50-60%', '70-80%', '80-90%', '90-100%']
        )
    
    # Create pivot table for heatmap
    heatmap_data = pd.crosstab(df['time_bin'], df['intensity_bin'])
    
    # Create heatmap
    plt.figure(figsize=(15, 8))
    sns.heatmap(heatmap_data, cmap='YlOrRd', annot=True, fmt='d', cbar_kws={'label': 'Count'})
    
    plt.title('Memory Usage Intensity Heatmap')
    plt.xlabel('Memory Usage Intensity')
    plt.ylabel('Time Period')
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'memory_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()

def main():
    try:
        parser = argparse.ArgumentParser(description='Generate memory metrics visualizations')
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
        output_dir = output_base / 'memory_plots'
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Load data
        print("Loading data from CSV...")
        df, cgroup_name = load_and_prepare_data(csv_file, args.cgroup_name)
        
        # Create mapping from generic metric names to actual column names
        column_map = create_column_mapping(df, cgroup_name)
        print(f"Using cgroup name: {cgroup_name}")
        
        # Create plots
        print("Generating memory usage plots...")
        plot_memory_usage(df, output_dir, column_map)
        plot_memory_events(df, output_dir, column_map)
        plot_memory_pressure(df, output_dir, column_map)
        plot_memory_swap(df, output_dir, column_map)
        plot_memory_correlations(df, output_dir, column_map)
        plot_memory_heatmap(df, output_dir, column_map)
        
        # Print statistics
        print("\nKey Memory Statistical Insights:")
        print("==============================")
        current_mb = df[column_map['memory_current']].iloc[-1] / (1024 * 1024)
        peak_mb = df[column_map['memory_peak']].max() / (1024 * 1024)
        print(f"1. Current memory usage: {current_mb:.2f} MB")
        print(f"2. Peak memory usage: {peak_mb:.2f} MB")
        print(f"3. Total OOM events: {df[column_map['memory_oom_events']].max()}")
        print(f"4. Memory pressure (10s avg): {df[column_map['memory_pressure_some_avg10']].mean():.2f}%")
        print(f"\nPlots have been saved to: {output_dir}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
