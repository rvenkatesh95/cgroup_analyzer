# cgroup_analyzer

A tool to analyze Linux cgroups v2. This project provides a suite of scripts for monitoring, visualizing, and applying limits to cgroups v2 on Linux systems. It includes tools for:

- **Monitoring:** Capturing cgroup metrics such as CPU usage, memory consumption, and process counts over time.
- **Visualization:** Generating plots and dashboards to understand resource utilization.
- **Limiting:** Applying and managing resource limits for cgroups.

## Key Components

- `monitor_stats/`: Contains scripts for monitoring cgroup statistics and outputting them to CSV files.
- `viz/`: Includes Python scripts for visualizing the data collected by the monitoring scripts, generating plots for CPU, memory, PIDs, and combined dashboards.
- `apply_limits/`: Provides shell scripts for applying resource limits to cgroups, such as CPU, memory, and process count limits.

## Usage

1.  **Monitoring:**
    -   Use the scripts in `monitor_stats/` to collect cgroup statistics.
    -   Example: `./monitor_stats/monitor_cgroup_stats.sh -c mycpu -i 0.1 -d 60 -o mycpu_stats.csv`

2.  **Visualization:**
    -   Use the scripts in `viz/` to generate visualizations from the collected CSV data.
    -   Example: `./viz/visualize_cpu_metrics.py --csv mycpu_stats.csv`

3.  **Applying Limits:**
    -   Use the scripts in `apply_limits/` to apply resource limits to cgroups.
    -   Example: `./apply_limits/yocto_cpu_limits.sh`

## Dependencies

- Python 3
- Pandas
- Matplotlib
- Seaborn
- Plotly (for interactive dashboards)
- bc
- awk

Install the required Python packages using:

```bash
pip install -r requirements.txt
```

## License

This project is licensed under the [MIT License](LICENSE).
