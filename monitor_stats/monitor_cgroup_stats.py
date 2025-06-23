#!/usr/bin/env python3
import os
import sys
import time
import math
import csv
import argparse
import subprocess
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Constants
CGROUP_ROOT_DEFAULT = "/sys/fs/cgroup"
DEFAULT_CGROUP = "mycpu"
DEFAULT_INTERVAL = 0.001
DEFAULT_DURATION = 60
DEFAULT_OUTPUT = f"cgroup_cpu_monitor_{int(time.time())}.csv"

def parse_args():
    parser = argparse.ArgumentParser(description="Improved Cgroup-Focused CPU Monitoring Script")
    parser.add_argument("-c", "--cgroup", action="append", help="Cgroup to monitor (can be used multiple times)")
    parser.add_argument("-a", "--all-cgroups", action="store_true", help="Monitor all available user cgroups")
    parser.add_argument("-i", "--interval", type=float, default=DEFAULT_INTERVAL, help=f"Polling interval in seconds (default: {DEFAULT_INTERVAL})")
    parser.add_argument("-d", "--duration", type=float, default=DEFAULT_DURATION, help=f"Duration to run in seconds (default: {DEFAULT_DURATION})")
    parser.add_argument("-o", "--output", type=str, default=DEFAULT_OUTPUT, help=f"Output CSV file (default: {DEFAULT_OUTPUT})")
    parser.add_argument("-r", "--root", type=str, default=CGROUP_ROOT_DEFAULT, help=f"Cgroup root path (default: {CGROUP_ROOT_DEFAULT})")
    parser.add_argument("-s", "--simple", action="store_true", help="Simple mode - only essential metrics")
    parser.add_argument("-q", "--quiet", action="store_true", help="Reduce output verbosity")
    return parser.parse_args()

def log(*args):
    if not args[-1].get("quiet", False):
        print(*args[:-1])

def validate_number(value, name):
    if value <= 0:
        raise ValueError(f"Invalid {name}: {value} (must be > 0)")

def read_file(path: str, default="0") -> str:
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception:
        return default

def extract_stat_value(content: str, key: str, default="0"):
    for line in content.splitlines():
        parts = line.strip().split()
        if parts[0] == key:
            return parts[1]
    return default

def parse_pressure_value(content: str, metric: str, field: str) -> str:
    for line in content.splitlines():
        if line.startswith(metric + " "):
            val = line.split(field + "=")[1].split()[0] if field in line else "0"
            return val
    return "0"

def discover_all_cgroups(cgroup_root: str) -> List[str]:
    discovered = []
    cpu_stat_files = Path(cgroup_root).rglob("cpu.stat")
    for path in cpu_stat_files:
        full_path = str(path.parent)
        rel_path = os.path.relpath(full_path, cgroup_root)
        if rel_path in ('.', 'init.scope', 'system.slice') or rel_path.endswith('.service'):
            continue
        discovered.append(rel_path)
    return discovered

def setup_cgroups(args) -> List[str]:
    if args.all_cgroups:
        return discover_all_cgroups(args.root)
    elif args.cgroup:
        return args.cgroup
    else:
        return [DEFAULT_CGROUP]

def get_cgroup_path(cgroup: str, root: str) -> str:
    return os.path.join(root, cgroup)

def is_valid_cgroup(cgroup: str, root: str) -> bool:
    path = get_cgroup_path(cgroup, root)
    return (
        os.path.isdir(path) and
        os.path.isfile(os.path.join(path, "cpu.stat")) and
        os.access(os.path.join(path, "cpu.stat"), os.R_OK)
    )

def build_csv_header(cgroups: List[str], simple_mode: bool) -> List[str]:
    header = ["timestamp", "elapsed_sec"]
    for cgroup in cgroups:
        safe_name = cgroup.replace('/', '_').replace('.', '_').replace('-', '_')
        # Essential CPU metrics
        header += [
            f"{safe_name}_cpu_usage_usec", f"{safe_name}_cpu_user_usec", f"{safe_name}_cpu_system_usec",
            f"{safe_name}_cpu_nr_periods", f"{safe_name}_cpu_nr_throttled", f"{safe_name}_cpu_throttled_usec"
        ]
        if not simple_mode:
            # Extended CPU metrics
            header += [
                f"{safe_name}_cpu_nr_bursts", f"{safe_name}_cpu_burst_usec",
                f"{safe_name}_cpu_weight", f"{safe_name}_cpu_max_quota", f"{safe_name}_cpu_max_period",
                f"{safe_name}_cpu_pressure_some_avg10", f"{safe_name}_cpu_pressure_full_avg10"
            ]
            # Memory metrics
            header += [
                f"{safe_name}_memory_current", f"{safe_name}_memory_peak", f"{safe_name}_memory_max",
                f"{safe_name}_memory_anon", f"{safe_name}_memory_file", f"{safe_name}_memory_kernel",
                f"{safe_name}_memory_swap_current", f"{safe_name}_memory_swap_max"
            ]
            # Memory events
            header += [
                f"{safe_name}_memory_oom_events", f"{safe_name}_memory_oom_kill_events",
                f"{safe_name}_memory_pressure_some_avg10", f"{safe_name}_memory_pressure_full_avg10"
            ]
            # PIDs
            header += [
                f"{safe_name}_pids_current", f"{safe_name}_pids_peak", f"{safe_name}_pids_max",
                f"{safe_name}_cgroup_procs_count"
            ]
    return header

def collect_metrics_for_cgroup(cgroup: str, root: str, simple_mode: bool) -> Dict[str, str]:
    path = get_cgroup_path(cgroup, root)
    safe_name = cgroup.replace('/', '_').replace('.', '_').replace('-', '_')
    metrics = {}

    # CPU stat
    cpu_stat = read_file(os.path.join(path, "cpu.stat"))
    metrics[f"{safe_name}_cpu_usage_usec"] = extract_stat_value(cpu_stat, "usage_usec")
    metrics[f"{safe_name}_cpu_user_usec"] = extract_stat_value(cpu_stat, "user_usec", "0")
    metrics[f"{safe_name}_cpu_system_usec"] = extract_stat_value(cpu_stat, "system_usec", "0")
    metrics[f"{safe_name}_cpu_nr_periods"] = extract_stat_value(cpu_stat, "nr_periods")
    metrics[f"{safe_name}_cpu_nr_throttled"] = extract_stat_value(cpu_stat, "nr_throttled")
    metrics[f"{safe_name}_cpu_throttled_usec"] = extract_stat_value(cpu_stat, "throttled_usec")

    if not simple_mode:
        # Extended CPU
        metrics[f"{safe_name}_cpu_nr_bursts"] = extract_stat_value(cpu_stat, "nr_bursts", "0")
        metrics[f"{safe_name}_cpu_burst_usec"] = extract_stat_value(cpu_stat, "burst_usec", "0")

        weight = read_file(os.path.join(path, "cpu.weight"), "100")
        metrics[f"{safe_name}_cpu_weight"] = weight

        max_quota = read_file(os.path.join(path, "cpu.max"), "max 100000")
        if " " in max_quota:
            quota, period = max_quota.split(" ", 1)
        else:
            quota, period = "max", "100000"
        metrics[f"{safe_name}_cpu_max_quota"] = quota
        metrics[f"{safe_name}_cpu_max_period"] = period

        # Pressure
        cpu_pressure = read_file(os.path.join(path, "cpu.pressure"))
        metrics[f"{safe_name}_cpu_pressure_some_avg10"] = parse_pressure_value(cpu_pressure, "some", "avg10")
        metrics[f"{safe_name}_cpu_pressure_full_avg10"] = parse_pressure_value(cpu_pressure, "full", "avg10")

        # Memory
        metrics[f"{safe_name}_memory_current"] = read_file(os.path.join(path, "memory.current"), "0")
        metrics[f"{safe_name}_memory_peak"] = read_file(os.path.join(path, "memory.peak"), "0")
        metrics[f"{safe_name}_memory_max"] = read_file(os.path.join(path, "memory.max"), "max")

        mem_stat = read_file(os.path.join(path, "memory.stat"))
        metrics[f"{safe_name}_memory_anon"] = extract_stat_value(mem_stat, "anon", "0")
        metrics[f"{safe_name}_memory_file"] = extract_stat_value(mem_stat, "file", "0")
        metrics[f"{safe_name}_memory_kernel"] = extract_stat_value(mem_stat, "kernel", "0")

        metrics[f"{safe_name}_memory_swap_current"] = read_file(os.path.join(path, "memory.swap.current"), "0")
        metrics[f"{safe_name}_memory_swap_max"] = read_file(os.path.join(path, "memory.swap.max"), "max")

        mem_events = read_file(os.path.join(path, "memory.events"))
        metrics[f"{safe_name}_memory_oom_events"] = extract_stat_value(mem_events, "oom", "0")
        metrics[f"{safe_name}_memory_oom_kill_events"] = extract_stat_value(mem_events, "oom_kill", "0")

        mem_pressure = read_file(os.path.join(path, "memory.pressure"))
        metrics[f"{safe_name}_memory_pressure_some_avg10"] = parse_pressure_value(mem_pressure, "some", "avg10")
        metrics[f"{safe_name}_memory_pressure_full_avg10"] = parse_pressure_value(mem_pressure, "full", "avg10")

        # PIDs
        metrics[f"{safe_name}_pids_current"] = read_file(os.path.join(path, "pids.current"), "0")
        metrics[f"{safe_name}_pids_peak"] = read_file(os.path.join(path, "pids.peak"), "0")
        metrics[f"{safe_name}_pids_max"] = read_file(os.path.join(path, "pids.max"), "max")

        procs_count = 0
        procs_file = os.path.join(path, "cgroup.procs")
        if os.path.isfile(procs_file):
            try:
                with open(procs_file, 'r') as f:
                    procs_count = len(f.readlines())
            except Exception:
                pass
        metrics[f"{safe_name}_cgroup_procs_count"] = str(procs_count)

    return metrics

def main():
    args = parse_args()
    quiet = args.quiet

    validate_number(args.interval, "interval")
    validate_number(args.duration, "duration")

    # Setup cgroups
    valid_cgroups = []
    all_cgroups = setup_cgroups(args)
    for cg in all_cgroups:
        if is_valid_cgroup(cg, args.root):
            valid_cgroups.append(cg)
        else:
            if not quiet:
                print(f"✗ {cg}: invalid or inaccessible")

    if not valid_cgroups:
        print("Error: No valid cgroups found to monitor")
        sys.exit(1)

    if not quiet:
        print(f"Setting up cgroup monitoring...")
        print(f"Monitoring {len(valid_cgroups)} valid cgroups")

    # Build CSV Header
    header = build_csv_header(valid_cgroups, args.simple)
    csvfile = open(args.output, 'w', newline='')
    writer = csv.DictWriter(csvfile, fieldnames=header)
    writer.writeheader()

    if not quiet:
        print("Improved Cgroup CPU Monitor")
        print("==========================")
        print(f"Cgroups: {' '.join(valid_cgroups)}")
        print(f"Interval: {args.interval}s")
        print(f"Duration: {args.duration}s")
        print(f"Output: {args.output}")
        print(f"Mode: {'Simple' if args.simple else 'Full'}")
        print("Starting monitoring... (Press Ctrl+C to stop)")

    start_time = time.perf_counter()
    end_time = start_time + args.duration
    sample_count = 0
    buffer = []

    def flush_buffer():
        nonlocal buffer
        if buffer:
            writer.writerows(buffer)
            buffer.clear()

    try:
        while True:
            now = time.perf_counter()
            if now >= end_time:
                break

            timestamp = time.time()
            elapsed = now - start_time
            row = {"timestamp": timestamp, "elapsed_sec": elapsed}

            for cgroup in valid_cgroups:
                metrics = collect_metrics_for_cgroup(cgroup, args.root, args.simple)
                row.update(metrics)

            buffer.append(row)
            sample_count += 1

            # Flush every 100 samples
            if len(buffer) >= 100:
                flush_buffer()

            # Sleep with high precision
            next_time = start_time + ((sample_count) * args.interval)
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        if not quiet:
            print("\nInterrupted by user.")

    finally:
        flush_buffer()
        csvfile.close()

        actual_duration = time.perf_counter() - start_time
        avg_rate = sample_count / actual_duration if actual_duration > 0 else 0
        if not quiet:
            print("Monitoring completed:")
            print(f"  Duration: {actual_duration:.2f}s")
            print(f"  Samples: {sample_count}")
            print(f"  Output: {args.output}")
            print(f"  Average rate: {avg_rate:.2f} Hz")

if __name__ == "__main__":
    main()
