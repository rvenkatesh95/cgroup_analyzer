#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path
import sys
import time
import pandas as pd

def detect_cgroup_name(csv_path):
    """Detect cgroup name from CSV headers."""
    try:
        # Read just the header row from the CSV
        df_header = pd.read_csv(csv_path, nrows=0)
        columns = df_header.columns.tolist()
        
        # Find columns that match cgroup metrics pattern (excluding timestamp and elapsed_sec)
        cgroup_columns = [col for col in columns if col not in ['timestamp', 'elapsed_sec']]
        
        if not cgroup_columns:
            raise ValueError("No cgroup metric columns found in the CSV file")
        
        # Extract the cgroup name from the first cgroup metric column
        # Format is expected to be {cgroup_name}_{metric_name}
        first_column = cgroup_columns[0]
        cgroup_name = first_column.split('_')[0]
        
        # Validate that this prefix is consistent across cgroup columns
        if not all(col.startswith(f"{cgroup_name}_") for col in cgroup_columns):
            # If inconsistent, return None to indicate a complex format
            return None
            
        print(f"Detected cgroup name: {cgroup_name}")
        return cgroup_name
        
    except Exception as e:
        print(f"Error detecting cgroup name: {str(e)}")
        return None

def run_visualization(script_name, csv_path, cgroup_name=None):
    """Run a visualization script and handle any errors."""
    print(f"\nRunning {script_name}...")
    try:
        cmd = [sys.executable, script_name, '--csv', str(csv_path)]
        if cgroup_name:
            cmd.extend(['--cgroup-name', cgroup_name])
            
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        if result.stdout.strip():  # Only print if there's output
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}:")
        if e.stderr.strip():  # Only print if there's error output
            print(e.stderr)
        return False
    except Exception as e:
        print(f"Unexpected error running {script_name}: {str(e)}")
        return False

def main():
    try:
        parser = argparse.ArgumentParser(description='Generate cgroup metrics visualizations')
        parser.add_argument('--csv', type=str, required=True,
                          help='Path to the input CSV file')
        args = parser.parse_args()

        csv_path = Path(args.csv)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Get the directory containing this script
        script_dir = Path(__file__).parent

        # Detect cgroup name from CSV headers
        cgroup_name = detect_cgroup_name(csv_path)

        # List of visualization scripts to run
        viz_scripts = [
            'visualize_cpu_metrics.py',
            'visualize_memory_metrics.py',
            'visualize_pids_metrics.py',
            'visualize_dashboard.py'
        ]

        # Verify all scripts exist before starting
        missing_scripts = []
        for script in viz_scripts:
            script_path = script_dir / script
            if not script_path.exists():
                missing_scripts.append(script)

        if missing_scripts:
            raise FileNotFoundError(
                f"Missing visualization scripts: {', '.join(missing_scripts)}"
            )

        # Create output directory based on CSV filename
        output_base = csv_path.with_suffix('')  # Remove .csv extension but keep full path
        output_base.mkdir(exist_ok=True)

        # Create subdirectories
        subdirs = ["cpu_plots", "memory_plots", "pids_plots", "dashboard"]
        for subdir in subdirs:
            (output_base / subdir).mkdir(exist_ok=True)

        print(f"Processing CSV file: {csv_path}")
        print(f"Output directory: {output_base}")
        start_time = time.time()

        # Run each visualization script and track results
        results = []
        for script in viz_scripts:
            script_path = script_dir / script
            success = run_visualization(script_path, csv_path, cgroup_name)
            results.append((script, success))

        end_time = time.time()
        duration = end_time - start_time

        # Print detailed summary
        print("\nVisualization Summary:")
        print("=====================")
        print(f"Time taken: {duration:.2f} seconds")
        print(f"CSV processed: {csv_path}")
        print("\nScript Status:")
        for script, success in results:
            status = "✓ Success" if success else "✗ Failed"
            print(f"{status}: {script}")

        print("\nOutput directories:")
        output_paths = [
            output_base / "cpu_plots",
            output_base / "memory_plots",
            output_base / "pids_plots",
            output_base / "dashboard"
        ]
        for path in output_paths:
            if path.exists():
                file_count = len(list(path.glob('*.png')))
                print(f"- {path.name}/: {file_count} plot(s)")
        
        failed = [s for s, success in results if not success]
        if failed:
            print(f"\nWarning: {len(failed)} script(s) failed!")
            sys.exit(1)
        else:
            print("\nAll visualizations completed successfully!")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
