#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path
import sys
import time

def run_visualization(script_name, csv_path):
    """Run a visualization script and handle any errors."""
    print(f"\nRunning {script_name}...")
    try:
        result = subprocess.run(
            [sys.executable, script_name, '--csv', str(csv_path)],
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

        print(f"Processing CSV file: {csv_path}")
        start_time = time.time()

        # Run each visualization script and track results
        results = []
        for script in viz_scripts:
            script_path = script_dir / script
            success = run_visualization(script_path, csv_path)
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
            csv_path.parent / "cpu_plots",
            csv_path.parent / "memory_plots",
            csv_path.parent / "pids_plots",
            csv_path.parent / "dashboard"
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
