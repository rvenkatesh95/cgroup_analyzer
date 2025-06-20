#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pyo

# Set the style for better visualization
plt.style.use('seaborn-v0_8')
sns.set_theme(style="darkgrid")
sns.set_palette("husl")

def load_and_prepare_data(csv_file):
    """Load and prepare the CSV data for visualization."""
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    return df

def create_static_dashboard(df, output_dir):
    """Create a combined dashboard of all metrics (static PNG)."""
    # Create a large figure with subplots
    fig = plt.figure(figsize=(20, 20))  # Increased height for heatmaps
    gs = fig.add_gridspec(6, 3, hspace=0.4, wspace=0.3)  # Added 2 more rows for heatmaps

    # CPU Metrics (Row 1)
    ax_cpu = fig.add_subplot(gs[0, 0])
    df['cpu_usage_rate'] = df['mycpu_cpu_usage_usec'].diff() / df['elapsed_sec'].diff() / 1e6
    ax_cpu.plot(df['elapsed_sec'], df['cpu_usage_rate'] * 100)
    ax_cpu.set_title('CPU Usage Rate')
    ax_cpu.set_ylabel('CPU Usage (%)')
    ax_cpu.set_xlabel('Time (s)')

    ax_cpu_pressure = fig.add_subplot(gs[0, 1])
    ax_cpu_pressure.plot(df['elapsed_sec'], df['mycpu_cpu_pressure_some_avg10'], 
                        label='Some')
    ax_cpu_pressure.plot(df['elapsed_sec'], df['mycpu_cpu_pressure_full_avg10'], 
                        label='Full')
    ax_cpu_pressure.set_title('CPU Pressure')
    ax_cpu_pressure.legend()

    ax_cpu_throttle = fig.add_subplot(gs[0, 2])
    throttled_ms = df['mycpu_cpu_throttled_usec'] / 1000
    ax_cpu_throttle.plot(df['elapsed_sec'], throttled_ms)
    ax_cpu_throttle.set_title('CPU Throttling')
    ax_cpu_throttle.set_ylabel('Throttled Time (ms)')

    # Memory Metrics (Row 2)
    ax_mem = fig.add_subplot(gs[1, 0])
    df['memory_current_mb'] = df['mycpu_memory_current'] / (1024 * 1024)
    df['memory_peak_mb'] = df['mycpu_memory_peak'] / (1024 * 1024)
    ax_mem.plot(df['elapsed_sec'], df['memory_current_mb'], label='Current')
    ax_mem.plot(df['elapsed_sec'], df['memory_peak_mb'], label='Peak')
    ax_mem.set_title('Memory Usage')
    ax_mem.set_ylabel('Memory (MB)')
    ax_mem.legend()

    ax_mem_pressure = fig.add_subplot(gs[1, 1])
    ax_mem_pressure.plot(df['elapsed_sec'], df['mycpu_memory_pressure_some_avg10'], 
                        label='Some')
    ax_mem_pressure.plot(df['elapsed_sec'], df['mycpu_memory_pressure_full_avg10'], 
                        label='Full')
    ax_mem_pressure.set_title('Memory Pressure')
    ax_mem_pressure.legend()

    ax_swap = fig.add_subplot(gs[1, 2])
    df['swap_mb'] = df['mycpu_memory_swap_current'] / (1024 * 1024)
    ax_swap.plot(df['elapsed_sec'], df['swap_mb'])
    ax_swap.set_title('Swap Usage')
    ax_swap.set_ylabel('Swap (MB)')

    # PIDs and Events (Row 3)
    ax_pids = fig.add_subplot(gs[2, 0])
    ax_pids.plot(df['elapsed_sec'], df['mycpu_pids_current'], label='PIDs')
    ax_pids.plot(df['elapsed_sec'], df['mycpu_cgroup_procs_count'], 
                 label='Processes')
    ax_pids.set_title('PIDs and Processes')
    ax_pids.legend()

    ax_oom = fig.add_subplot(gs[2, 1])
    ax_oom.plot(df['elapsed_sec'], df['mycpu_memory_oom_events'], 
                label='OOM Events', marker='o')
    ax_oom.plot(df['elapsed_sec'], df['mycpu_memory_oom_kill_events'], 
                label='OOM Kills', marker='x')
    ax_oom.set_title('OOM Events')
    ax_oom.legend()

    # CPU Heatmap (Row 4)
    ax_cpu_heat = fig.add_subplot(gs[3, :])
    df['cpu_usage_pct'] = df['cpu_usage_rate'] * 100
    time_bins = pd.cut(df['elapsed_sec'], bins=50)
    
    try:
        # Try to create quantile bins, but handle cases with duplicate values
        intensity_bins = pd.qcut(
            df['cpu_usage_pct'], 
            q=10, 
            labels=['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', 
                   '50-60%', '60-70%', '70-80%', '80-90%', '90-100%'],
            duplicates='drop'
        )
    except ValueError:
        # If quantile binning fails, use regular bins
        intensity_bins = pd.cut(
            df['cpu_usage_pct'],
            bins=10,
            labels=['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', 
                   '50-60%', '60-70%', '70-80%', '80-90%', '90-100%']
        )
    
    cpu_heatmap_data = pd.crosstab(time_bins, intensity_bins)
    sns.heatmap(cpu_heatmap_data, ax=ax_cpu_heat, cmap='YlOrRd', annot=True, fmt='d', 
                cbar_kws={'label': 'Count'})
    ax_cpu_heat.set_title('CPU Usage Intensity Heatmap')
    ax_cpu_heat.set_xlabel('CPU Usage Intensity')
    ax_cpu_heat.set_ylabel('Time Period')

    # Memory Heatmap (Row 5)
    ax_mem_heat = fig.add_subplot(gs[4, :])
    
    # Calculate memory usage percentage
    max_memory = df['mycpu_memory_max'].replace('max', str(float('inf'))).astype(float)
    if np.all(np.isinf(max_memory)):
        # If no memory limit is set, calculate percentage relative to peak memory
        max_memory = df['mycpu_memory_peak'].max()
    
    df['memory_usage_pct'] = (df['mycpu_memory_current'] / max_memory) * 100
    
    try:
        # Try to create quantile bins, but handle cases with duplicate values
        memory_intensity_bins = pd.qcut(
            df['memory_usage_pct'], 
            q=10, 
            labels=['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', 
                   '50-60%', '60-70%', '70-80%', '80-90%', '90-100%'],
            duplicates='drop'
        )
    except ValueError:
        # If quantile binning fails, use regular bins
        memory_intensity_bins = pd.cut(
            df['memory_usage_pct'],
            bins=10,
            labels=['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', 
                   '50-60%', '60-70%', '70-80%', '80-90%', '90-100%']
        )
    
    mem_heatmap_data = pd.crosstab(time_bins, memory_intensity_bins)
    sns.heatmap(mem_heatmap_data, ax=ax_mem_heat, cmap='YlOrRd', annot=True, fmt='d',
                cbar_kws={'label': 'Count'})
    ax_mem_heat.set_title('Memory Usage Intensity Heatmap')
    ax_mem_heat.set_xlabel('Memory Usage Intensity')
    ax_mem_heat.set_ylabel('Time Period')

    # Memory Components (Row 6)
    ax_mem_comp = fig.add_subplot(gs[5, :])
    df['anon_mb'] = df['mycpu_memory_anon'] / (1024 * 1024)
    df['file_mb'] = df['mycpu_memory_file'] / (1024 * 1024)
    df['kernel_mb'] = df['mycpu_memory_kernel'] / (1024 * 1024)
    ax_mem_comp.stackplot(df['elapsed_sec'], 
                         [df['anon_mb'], df['file_mb'], df['kernel_mb']],
                         labels=['Anonymous', 'File-backed', 'Kernel'])
    ax_mem_comp.set_title('Memory Components')
    ax_mem_comp.set_ylabel('Memory (MB)')
    ax_mem_comp.set_xlabel('Time (s)')
    ax_mem_comp.legend()

    plt.suptitle('Cgroup Metrics Dashboard', size=16, y=0.95)
    plt.savefig(output_dir / 'dashboard.png', dpi=300, bbox_inches='tight')
    plt.close()

def create_interactive_dashboard(df, output_dir):
    """Create an interactive HTML dashboard using Plotly."""
    # Prepare data
    df['cpu_usage_rate'] = df['mycpu_cpu_usage_usec'].diff() / df['elapsed_sec'].diff() / 1e6
    df['memory_current_mb'] = df['mycpu_memory_current'] / (1024 * 1024)
    df['memory_peak_mb'] = df['mycpu_memory_peak'] / (1024 * 1024)
    df['swap_mb'] = df['mycpu_memory_swap_current'] / (1024 * 1024)
    df['throttled_ms'] = df['mycpu_cpu_throttled_usec'] / 1000
    df['anon_mb'] = df['mycpu_memory_anon'] / (1024 * 1024)
    df['file_mb'] = df['mycpu_memory_file'] / (1024 * 1024)
    df['kernel_mb'] = df['mycpu_memory_kernel'] / (1024 * 1024)
    
    # Create subplots
    fig = make_subplots(
        rows=3, cols=3,
        subplot_titles=[
            'CPU Usage Rate', 'CPU Pressure', 'CPU Throttling',
            'Memory Usage', 'Memory Pressure', 'Swap Usage',
            'PIDs and Processes', 'OOM Events', 'Memory Components'
        ],
        specs=[[{"secondary_y": False}, {"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Row 1: CPU Metrics
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['cpu_usage_rate'] * 100,
                   mode='lines', name='CPU Usage %',
                   line=dict(color='#FF6B6B')),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['mycpu_cpu_pressure_some_avg10'],
                   mode='lines', name='Some', line=dict(color='#4ECDC4')),
        row=1, col=2
    )
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['mycpu_cpu_pressure_full_avg10'],
                   mode='lines', name='Full', line=dict(color='#45B7D1')),
        row=1, col=2
    )
    
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['throttled_ms'],
                   mode='lines', name='Throttled (ms)',
                   line=dict(color='#FFA07A')),
        row=1, col=3
    )
    
    # Row 2: Memory Metrics
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['memory_current_mb'],
                   mode='lines', name='Current MB', line=dict(color='#98D8C8')),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['memory_peak_mb'],
                   mode='lines', name='Peak MB', line=dict(color='#F7DC6F')),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['mycpu_memory_pressure_some_avg10'],
                   mode='lines', name='Some', line=dict(color='#BB8FCE')),
        row=2, col=2
    )
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['mycpu_memory_pressure_full_avg10'],
                   mode='lines', name='Full', line=dict(color='#85C1E9')),
        row=2, col=2
    )
    
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['swap_mb'],
                   mode='lines', name='Swap MB',
                   line=dict(color='#F8C471')),
        row=2, col=3
    )
    
    # Row 3: PIDs and Events
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['mycpu_pids_current'],
                   mode='lines', name='PIDs', line=dict(color='#82E0AA')),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['mycpu_cgroup_procs_count'],
                   mode='lines', name='Processes', line=dict(color='#D2B4DE')),
        row=3, col=1
    )
    
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['mycpu_memory_oom_events'],
                   mode='markers+lines', name='OOM Events',
                   line=dict(color='#E74C3C'), marker=dict(size=6)),
        row=3, col=2
    )
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['mycpu_memory_oom_kill_events'],
                   mode='markers+lines', name='OOM Kills',
                   line=dict(color='#C0392B'), marker=dict(size=6, symbol='x')),
        row=3, col=2
    )
    
    # Memory Components Stack
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['anon_mb'],
                   mode='lines', name='Anonymous', fill='tonexty',
                   line=dict(color='#3498DB')),
        row=3, col=3
    )
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['file_mb'],
                   mode='lines', name='File-backed', fill='tonexty',
                   line=dict(color='#E67E22')),
        row=3, col=3
    )
    fig.add_trace(
        go.Scatter(x=df['elapsed_sec'], y=df['kernel_mb'],
                   mode='lines', name='Kernel', fill='tonexty',
                   line=dict(color='#9B59B6')),
        row=3, col=3
    )
    
    # Update layout
    fig.update_layout(
        height=900,
        title_text="Interactive Cgroup Metrics Dashboard",
        title_x=0.5,
        showlegend=True,
        template="plotly_white"
    )
    
    # Update x-axis labels
    for i in range(1, 4):
        for j in range(1, 4):
            fig.update_xaxes(title_text="Time (s)", row=i, col=j)
    
    # Update y-axis labels
    fig.update_yaxes(title_text="CPU Usage (%)", row=1, col=1)
    fig.update_yaxes(title_text="Pressure", row=1, col=2)
    fig.update_yaxes(title_text="Throttled (ms)", row=1, col=3)
    fig.update_yaxes(title_text="Memory (MB)", row=2, col=1)
    fig.update_yaxes(title_text="Pressure", row=2, col=2)
    fig.update_yaxes(title_text="Swap (MB)", row=2, col=3)
    fig.update_yaxes(title_text="Count", row=3, col=1)
    fig.update_yaxes(title_text="Events", row=3, col=2)
    fig.update_yaxes(title_text="Memory (MB)", row=3, col=3)
    
    # Save HTML
    html_file = output_dir / 'interactive_dashboard.html'
    fig.write_html(str(html_file))
    
    return html_file

def create_summary_html(df, output_dir):
    """Create a summary HTML page with key statistics."""
    monitoring_time = df['elapsed_sec'].max() - df['elapsed_sec'].min()
    cpu_avg = (df['mycpu_cpu_usage_usec'].diff() / df['elapsed_sec'].diff() / 1e6).mean() * 100
    cpu_max = (df['mycpu_cpu_usage_usec'].diff() / df['elapsed_sec'].diff() / 1e6).max() * 100
    mem_avg_mb = df['mycpu_memory_current'].mean() / (1024 * 1024)
    mem_peak_mb = df['mycpu_memory_peak'].max() / (1024 * 1024)
    pids_avg = df['mycpu_pids_current'].mean()
    pids_max = df['mycpu_pids_current'].max()
    oom_events = df['mycpu_memory_oom_events'].sum()
    oom_kills = df['mycpu_memory_oom_kill_events'].sum()
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cgroup Metrics Dashboard</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 2.5em;
                font-weight: 300;
            }}
            .header p {{
                margin: 10px 0 0 0;
                opacity: 0.9;
                font-size: 1.1em;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                padding: 30px;
            }}
            .stat-card {{
                background: #f8f9fa;
                padding: 25px;
                border-radius: 10px;
                text-align: center;
                transition: transform 0.3s ease;
                border-left: 4px solid #4facfe;
            }}
            .stat-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            }}
            .stat-value {{
                font-size: 2.2em;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }}
            .stat-label {{
                color: #7f8c8d;
                font-size: 1em;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .dashboard-links {{
                padding: 30px;
                text-align: center;
                background: #f8f9fa;
            }}
            .dashboard-links h2 {{
                color: #2c3e50;
                margin-bottom: 20px;
            }}
            .link-button {{
                display: inline-block;
                margin: 10px 15px;
                padding: 15px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 25px;
                font-weight: bold;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }}
            .link-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            }}
            .warning {{
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                color: #856404;
                padding: 15px;
                margin: 20px 30px;
                border-radius: 8px;
            }}
            .timestamp {{
                text-align: center;
                color: #7f8c8d;
                font-size: 0.9em;
                padding: 20px;
                border-top: 1px solid #ecf0f1;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Cgroup Metrics Dashboard</h1>
                <p>Performance monitoring and resource utilization analysis</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{monitoring_time:.1f}s</div>
                    <div class="stat-label">Monitoring Duration</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{cpu_avg:.1f}%</div>
                    <div class="stat-label">Average CPU Usage</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{cpu_max:.1f}%</div>
                    <div class="stat-label">Peak CPU Usage</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{mem_avg_mb:.1f}MB</div>
                    <div class="stat-label">Average Memory</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{mem_peak_mb:.1f}MB</div>
                    <div class="stat-label">Peak Memory</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{pids_avg:.0f}</div>
                    <div class="stat-label">Average PIDs</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{pids_max:.0f}</div>
                    <div class="stat-label">Peak PIDs</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{int(oom_events)}</div>
                    <div class="stat-label">OOM Events</div>
                </div>
            </div>
            
            {f'<div class="warning"><strong>Warning:</strong> {int(oom_kills)} OOM kill events detected. This indicates memory pressure issues.</div>' if oom_kills > 0 else ''}
            
            <div class="dashboard-links">
                <h2>Dashboard Views</h2>
                <a href="interactive_dashboard.html" class="link-button">📊 Interactive Dashboard</a>
                <a href="dashboard.png" class="link-button">📈 Static Dashboard</a>
            </div>
            
            <div class="timestamp">
                Generated on {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
    </body>
    </html>
    """
    
    summary_file = output_dir / 'index.html'
    with open(summary_file, 'w') as f:
        f.write(html_content)
    
    return summary_file

def main():
    try:
        parser = argparse.ArgumentParser(description='Generate combined metrics dashboard')
        parser.add_argument('--csv', type=str, required=True,
                          help='Path to the input CSV file')
        parser.add_argument('--html-only', action='store_true',
                          help='Generate only HTML dashboard (skip static PNG)')
        args = parser.parse_args()
        
        # Set up paths
        csv_file = Path(args.csv)
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
            
        output_dir = csv_file.parent / 'dashboard'
        output_dir.mkdir(exist_ok=True)
        
        # Load data
        print("Loading data from CSV...")
        df = load_and_prepare_data(csv_file)
        
        # Create dashboards
        if not args.html_only:
            print("Generating static PNG dashboard...")
            create_static_dashboard(df, output_dir)
        
        print("Generating interactive HTML dashboard...")
        interactive_file = create_interactive_dashboard(df, output_dir)
        
        print("Generating summary HTML page...")
        summary_file = create_summary_html(df, output_dir)
        
        # Print summary
        print("\nDashboard Generation Complete:")
        print("============================")
        monitoring_time = df['elapsed_sec'].max() - df['elapsed_sec'].min()
        cpu_avg = (df['mycpu_cpu_usage_usec'].diff() / df['elapsed_sec'].diff() / 1e6).mean() * 100
        mem_avg_mb = df['mycpu_memory_current'].mean() / (1024 * 1024)
        pids_avg = df['mycpu_pids_current'].mean()
        
        print(f"1. Total monitoring time: {monitoring_time:.2f} seconds")
        print(f"2. Average CPU usage: {cpu_avg:.2f}%")
        print(f"3. Average memory usage: {mem_avg_mb:.2f} MB")
        print(f"4. Average PIDs count: {pids_avg:.2f}")
        print(f"\nGenerated files:")
        print(f"• Summary page: {summary_file}")
        print(f"• Interactive dashboard: {interactive_file}")
        if not args.html_only:
            print(f"• Static dashboard: {output_dir / 'dashboard.png'}")
        print(f"\nOpen {summary_file} in your browser to view the complete dashboard.")
        
    except ImportError as e:
        if 'plotly' in str(e):
            print("Error: Plotly is required for HTML dashboard generation.")
            print("Install it with: pip install plotly")
            print("Falling back to static dashboard only...")
            # Fallback to static only
            args.html_only = False
            df = load_and_prepare_data(csv_file)
            create_static_dashboard(df, output_dir)
        else:
            raise
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()