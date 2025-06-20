#!/bin/bash
# Improved Cgroup-Focused CPU Monitoring Script
# Fixed CSV output issues and improved performance

set -euo pipefail

# Default values
DEFAULT_CGROUP="mycpu"
INTERVAL=0.001
DURATION=60
OUTPUT_FILE="cgroup_cpu_monitor_$(date +%Y%m%d_%H%M%S).csv"
CGROUP_ROOT="/sys/fs/cgroup"
BUFFER_SIZE=100
VALIDATE_CGROUPS=true

# Arrays for tracking
declare -a MONITOR_CGROUPS=()
declare -A CGROUP_PATHS=()
declare -A CGROUP_VALID=()

# Global variables
START_TIME=""
SAMPLES_COLLECTED=0
BUFFER_COUNT=0
declare -a BUFFER_LINES=()

usage() {
    cat << EOF
Improved Cgroup CPU Monitor

Usage: $0 [options]

Options:
  -c, --cgroup NAME      Specific cgroup to monitor (can be used multiple times)
  -a, --all-cgroups      Monitor all available user cgroups
  -i, --interval SEC     Polling interval in seconds (default: 0.001)
  -d, --duration SEC     Duration to run in seconds (default: 60)
  -o, --output FILE      Output CSV file
  -r, --root PATH        Cgroup root path (default: /sys/fs/cgroup)
  -s, --simple           Simple mode - only essential metrics
  -q, --quiet            Reduce output verbosity
  -h, --help             Show this help

Examples:
  $0 -c myapp -i 0.01 -d 120
  $0 -a -s -o monitor.csv
  $0 -c user.slice/user-1000.slice
EOF
    exit 1
}

# Parse command line arguments
parse_args() {
    SIMPLE_MODE=false
    QUIET=false
    DISCOVER_ALL=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--cgroup)
                [[ $# -lt 2 ]] && { echo "Error: Missing cgroup name" >&2; usage; }
                MONITOR_CGROUPS+=("$2")
                shift 2
                ;;
            -a|--all-cgroups)
                DISCOVER_ALL=true
                shift
                ;;
            -i|--interval)
                [[ $# -lt 2 ]] && { echo "Error: Missing interval value" >&2; usage; }
                INTERVAL="$2"
                shift 2
                ;;
            -d|--duration)
                [[ $# -lt 2 ]] && { echo "Error: Missing duration value" >&2; usage; }
                DURATION="$2"
                shift 2
                ;;
            -o|--output)
                [[ $# -lt 2 ]] && { echo "Error: Missing filename" >&2; usage; }
                OUTPUT_FILE="$2"
                shift 2
                ;;
            -r|--root)
                [[ $# -lt 2 ]] && { echo "Error: Missing path" >&2; usage; }
                CGROUP_ROOT="$2"
                shift 2
                ;;
            -s|--simple)
                SIMPLE_MODE=true
                shift
                ;;
            -q|--quiet)
                QUIET=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            *)
                echo "Unknown option: $1" >&2
                usage
                ;;
        esac
    done
}

# Logging function
log() {
    [[ "${QUIET:-false}" != "true" ]] && echo "$@" >&2
}

# Check dependencies
check_dependencies() {
    local missing=()
    for cmd in bc awk; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Error: Missing required commands: ${missing[*]}" >&2
        exit 1
    fi
    
    if [[ ! -d "$CGROUP_ROOT" ]]; then
        echo "Error: Cgroup root directory not found: $CGROUP_ROOT" >&2
        exit 1
    fi
}

# Discover available cgroups
discover_cgroups() {
    log "Discovering available cgroups..."
    
    local discovered=()
    
    # Find directories with cpu.stat files
    while IFS= read -r -d '' path; do
        local cgroup_name
        cgroup_name=$(realpath --relative-to="$CGROUP_ROOT" "$path" 2>/dev/null) || continue
        
        # Skip root and system cgroups
        if [[ "$cgroup_name" == "." ]] || \
           [[ "$cgroup_name" =~ ^(init\.scope|system\.slice) ]] || \
           [[ "$cgroup_name" =~ \.service$ ]]; then
            continue
        fi
        
        discovered+=("$cgroup_name")
    done < <(find "$CGROUP_ROOT" -name "cpu.stat" -print0 2>/dev/null || true)
    
    if [[ ${#discovered[@]} -eq 0 ]]; then
        log "Warning: No cgroups found. Using default: $DEFAULT_CGROUP"
        discovered=("$DEFAULT_CGROUP")
    fi
    
    MONITOR_CGROUPS=("${discovered[@]}")
    log "Discovered ${#MONITOR_CGROUPS[@]} cgroups"
}

# Setup cgroup paths and validation
setup_cgroups() {
    log "Setting up cgroup monitoring..."
    
    # Use default if no cgroups specified and not discovering all
    if [[ ${#MONITOR_CGROUPS[@]} -eq 0 ]] && [[ "${DISCOVER_ALL:-false}" != "true" ]]; then
        MONITOR_CGROUPS=("$DEFAULT_CGROUP")
    fi
    
    # Discover all if requested
    if [[ "${DISCOVER_ALL:-false}" == "true" ]]; then
        discover_cgroups
    fi
    
    # Setup and validate paths
    local valid_cgroups=()
    for cgroup in "${MONITOR_CGROUPS[@]}"; do
        local full_path="$CGROUP_ROOT/$cgroup"
        CGROUP_PATHS["$cgroup"]="$full_path"
        
        if validate_cgroup "$cgroup" "$full_path"; then
            valid_cgroups+=("$cgroup")
        fi
    done
    
    MONITOR_CGROUPS=("${valid_cgroups[@]}")
    
    if [[ ${#MONITOR_CGROUPS[@]} -eq 0 ]]; then
        echo "Error: No valid cgroups found to monitor" >&2
        exit 1
    fi
    
    log "Monitoring ${#MONITOR_CGROUPS[@]} valid cgroups"
}

# Validate individual cgroup
validate_cgroup() {
    local cgroup="$1"
    local path="$2"
    
    # Check directory exists
    if [[ ! -d "$path" ]]; then
        log "  ✗ $cgroup: directory not found"
        return 1
    fi
    
    # Check essential files
    if [[ ! -f "$path/cpu.stat" ]] || [[ ! -r "$path/cpu.stat" ]]; then
        log "  ✗ $cgroup: cpu.stat not accessible"
        return 1
    fi
    
    log "  ✓ $cgroup: valid"
    return 0
}

# Safe file reading
read_cgroup_file() {
    local file="$1"
    local default="${2:-0}"
    
    if [[ -r "$file" ]]; then
        cat "$file" 2>/dev/null || echo "$default"
    else
        echo "$default"
    fi
}

# Extract value from key-value content
extract_stat_value() {
    local content="$1" 
    local key="$2"
    local default="${3:-0}"
    
    echo "$content" | awk -v key="$key" -v def="$default" '
        $1 == key { print $2; found=1; exit }
        END { if (!found) print def }
    '
}

# Parse pressure metrics - FIXED to return single values
parse_pressure_value() {
    local pressure_content="$1"
    local metric="$2"  # "some" or "full"
    local field="$3"   # "avg10", "avg60", "avg300", or "total"
    
    local line
    line=$(echo "$pressure_content" | grep "^$metric " 2>/dev/null || echo "")
    
    if [[ -n "$line" ]]; then
        local value
        value=$(echo "$line" | sed -n "s/.*${field}=\([0-9.]*\).*/\1/p")
        echo "${value:-0}"
    else
        echo "0"
    fi
}

# Write CSV header
write_csv_header() {
    local header="timestamp,elapsed_sec"
    
    for cgroup in "${MONITOR_CGROUPS[@]}"; do
        local cg_safe
        cg_safe=$(echo "$cgroup" | tr '/' '_' | tr '.' '_' | tr '-' '_')
        
        # Essential CPU metrics
        header="$header,${cg_safe}_cpu_usage_usec,${cg_safe}_cpu_user_usec,${cg_safe}_cpu_system_usec"
        header="$header,${cg_safe}_cpu_nr_periods,${cg_safe}_cpu_nr_throttled,${cg_safe}_cpu_throttled_usec"
        
        if [[ "${SIMPLE_MODE:-false}" != "true" ]]; then
            # Extended CPU metrics
            header="$header,${cg_safe}_cpu_nr_bursts,${cg_safe}_cpu_burst_usec"
            header="$header,${cg_safe}_cpu_weight,${cg_safe}_cpu_max_quota,${cg_safe}_cpu_max_period"
            
            # CPU pressure
            header="$header,${cg_safe}_cpu_pressure_some_avg10,${cg_safe}_cpu_pressure_full_avg10"
            
            # Memory metrics
            header="$header,${cg_safe}_memory_current,${cg_safe}_memory_peak,${cg_safe}_memory_max"
            header="$header,${cg_safe}_memory_anon,${cg_safe}_memory_file,${cg_safe}_memory_kernel"
            header="$header,${cg_safe}_memory_swap_current,${cg_safe}_memory_swap_max"
            
            # Memory events
            header="$header,${cg_safe}_memory_oom_events,${cg_safe}_memory_oom_kill_events"
            
            # Memory pressure
            header="$header,${cg_safe}_memory_pressure_some_avg10,${cg_safe}_memory_pressure_full_avg10"
            
            # PIDs
            header="$header,${cg_safe}_pids_current,${cg_safe}_pids_peak,${cg_safe}_pids_max"
            header="$header,${cg_safe}_cgroup_procs_count"
        fi
    done
    
    echo "$header" > "$OUTPUT_FILE"
    log "CSV header written to $OUTPUT_FILE"
}

# Collect cgroup statistics
collect_cgroup_stats() {
    local timestamp
    timestamp=$(date +%s.%N)
    local elapsed
    elapsed=$(echo "$timestamp - $START_TIME" | bc -l)
    
    local row_data="$timestamp,$elapsed"
    
    for cgroup in "${MONITOR_CGROUPS[@]}"; do
        local path="${CGROUP_PATHS[$cgroup]}"
        
        # CPU statistics
        local cpu_stat_content
        cpu_stat_content=$(read_cgroup_file "$path/cpu.stat")
        
        local usage_usec user_usec system_usec nr_periods nr_throttled throttled_usec
        usage_usec=$(extract_stat_value "$cpu_stat_content" "usage_usec")
        user_usec=$(extract_stat_value "$cpu_stat_content" "user_usec")  
        system_usec=$(extract_stat_value "$cpu_stat_content" "system_usec")
        nr_periods=$(extract_stat_value "$cpu_stat_content" "nr_periods")
        nr_throttled=$(extract_stat_value "$cpu_stat_content" "nr_throttled")
        throttled_usec=$(extract_stat_value "$cpu_stat_content" "throttled_usec")
        
        row_data="$row_data,$usage_usec,$user_usec,$system_usec,$nr_periods,$nr_throttled,$throttled_usec"
        
        if [[ "${SIMPLE_MODE:-false}" != "true" ]]; then
            # Extended CPU metrics
            local nr_bursts burst_usec
            nr_bursts=$(extract_stat_value "$cpu_stat_content" "nr_bursts")
            burst_usec=$(extract_stat_value "$cpu_stat_content" "burst_usec")
            
            local cpu_weight cpu_max_content cpu_max_quota cpu_max_period
            cpu_weight=$(read_cgroup_file "$path/cpu.weight" "100")
            cpu_max_content=$(read_cgroup_file "$path/cpu.max" "max")
            
            cpu_max_quota="max"
            cpu_max_period="100000"
            if [[ "$cpu_max_content" != "max" ]] && [[ "$cpu_max_content" == *" "* ]]; then
                cpu_max_quota=$(echo "$cpu_max_content" | cut -d' ' -f1)
                cpu_max_period=$(echo "$cpu_max_content" | cut -d' ' -f2)
            fi
            
            row_data="$row_data,$nr_bursts,$burst_usec,$cpu_weight,$cpu_max_quota,$cpu_max_period"
            
            # CPU pressure - FIXED: single values only
            local cpu_pressure_content
            cpu_pressure_content=$(read_cgroup_file "$path/cpu.pressure")
            local cpu_some_avg10 cpu_full_avg10
            cpu_some_avg10=$(parse_pressure_value "$cpu_pressure_content" "some" "avg10")
            cpu_full_avg10=$(parse_pressure_value "$cpu_pressure_content" "full" "avg10")
            
            row_data="$row_data,$cpu_some_avg10,$cpu_full_avg10"
            
            # Memory metrics
            local memory_current memory_peak memory_max
            memory_current=$(read_cgroup_file "$path/memory.current" "0")
            memory_peak=$(read_cgroup_file "$path/memory.peak" "0")
            memory_max=$(read_cgroup_file "$path/memory.max" "max")
            
            local memory_stat_content
            memory_stat_content=$(read_cgroup_file "$path/memory.stat")
            local mem_anon mem_file mem_kernel
            mem_anon=$(extract_stat_value "$memory_stat_content" "anon")
            mem_file=$(extract_stat_value "$memory_stat_content" "file")
            mem_kernel=$(extract_stat_value "$memory_stat_content" "kernel")
            
            local memory_swap_current memory_swap_max
            memory_swap_current=$(read_cgroup_file "$path/memory.swap.current" "0")
            memory_swap_max=$(read_cgroup_file "$path/memory.swap.max" "max")
            
            row_data="$row_data,$memory_current,$memory_peak,$memory_max,$mem_anon,$mem_file,$mem_kernel"
            row_data="$row_data,$memory_swap_current,$memory_swap_max"
            
            # Memory events
            local memory_events_content
            memory_events_content=$(read_cgroup_file "$path/memory.events")
            local mem_oom_events mem_oom_kill_events
            mem_oom_events=$(extract_stat_value "$memory_events_content" "oom")
            mem_oom_kill_events=$(extract_stat_value "$memory_events_content" "oom_kill")
            
            row_data="$row_data,$mem_oom_events,$mem_oom_kill_events"
            
            # Memory pressure - FIXED: single values only
            local memory_pressure_content
            memory_pressure_content=$(read_cgroup_file "$path/memory.pressure")
            local mem_some_avg10 mem_full_avg10
            mem_some_avg10=$(parse_pressure_value "$memory_pressure_content" "some" "avg10")
            mem_full_avg10=$(parse_pressure_value "$memory_pressure_content" "full" "avg10")
            
            row_data="$row_data,$mem_some_avg10,$mem_full_avg10"
            
            # PIDs
            local pids_current pids_peak pids_max cgroup_procs_count
            pids_current=$(read_cgroup_file "$path/pids.current" "0")
            pids_peak=$(read_cgroup_file "$path/pids.peak" "0")
            pids_max=$(read_cgroup_file "$path/pids.max" "max")
            
            cgroup_procs_count=0
            if [[ -f "$path/cgroup.procs" ]]; then
                cgroup_procs_count=$(wc -l < "$path/cgroup.procs" 2>/dev/null || echo "0")
            fi
            
            row_data="$row_data,$pids_current,$pids_peak,$pids_max,$cgroup_procs_count"
        fi
    done
    
    # Add to buffer
    BUFFER_LINES+=("$row_data")
    BUFFER_COUNT=$((BUFFER_COUNT + 1))
    
    # Flush buffer when full
    if [[ $BUFFER_COUNT -ge $BUFFER_SIZE ]]; then
        flush_buffer
    fi
}

# Flush buffer to file
flush_buffer() {
    if [[ $BUFFER_COUNT -gt 0 ]]; then
        printf '%s\n' "${BUFFER_LINES[@]}" >> "$OUTPUT_FILE"
        BUFFER_LINES=()
        BUFFER_COUNT=0
    fi
}

# Cleanup function
cleanup() {
    log "Cleaning up..."
    
    # Flush remaining buffer
    flush_buffer
    
    local end_time
    end_time=$(date +%s.%N)
    local actual_duration
    actual_duration=$(echo "$end_time - $START_TIME" | bc -l)
    
    log "Monitoring completed:"
    log "  Duration: $(printf "%.2f" "$actual_duration")s"
    log "  Samples: $SAMPLES_COLLECTED"
    log "  Output: $OUTPUT_FILE"
    
    if [[ $SAMPLES_COLLECTED -gt 0 ]]; then
        local avg_rate
        avg_rate=$(echo "scale=2; $SAMPLES_COLLECTED / $actual_duration" | bc -l)
        log "  Average rate: ${avg_rate} Hz"
    fi
    
    exit 0
}

# Validate numeric input
validate_number() {
    local value="$1"
    local name="$2"
    
    if ! echo "$value" | grep -qE '^[0-9]*\.?[0-9]+$' || \
       [[ $(echo "$value <= 0" | bc -l) -eq 1 ]]; then
        echo "Error: Invalid $name '$value'" >&2
        exit 1
    fi
}

# Main execution
main() {
    trap cleanup INT TERM EXIT
    
    # Parse arguments
    parse_args "$@"
    
    # Validate inputs
    validate_number "$INTERVAL" "interval"
    validate_number "$DURATION" "duration"
    
    # Setup
    check_dependencies
    setup_cgroups
    
    log "Improved Cgroup CPU Monitor"
    log "=========================="
    log "Cgroups: ${MONITOR_CGROUPS[*]}"
    log "Interval: ${INTERVAL}s"
    log "Duration: ${DURATION}s"
    log "Output: $OUTPUT_FILE"
    log "Mode: $([ "${SIMPLE_MODE:-false}" == "true" ] && echo "Simple" || echo "Full")"
    
    # Initialize
    START_TIME=$(date +%s.%N)
    SAMPLES_COLLECTED=0
    
    write_csv_header
    
    log "Starting monitoring... (Press Ctrl+C to stop)"
    
    # Main monitoring loop
    local end_time
    end_time=$(echo "$START_TIME + $DURATION" | bc -l)
    
    while (( $(echo "$(date +%s.%N) < $end_time" | bc -l) )); do
        collect_cgroup_stats
        SAMPLES_COLLECTED=$((SAMPLES_COLLECTED + 1))
        
        # Show progress every 1000 samples
        if [[ $((SAMPLES_COLLECTED % 1000)) -eq 0 ]]; then
            local current_time=$(date +%s.%N)
            local elapsed=$(echo "$current_time - $START_TIME" | bc -l)
            local rate=$(echo "scale=1; $SAMPLES_COLLECTED / $elapsed" | bc -l)
            local percent=$(echo "scale=1; 100 * $elapsed / $DURATION" | bc -l)
            
            log "Progress: ${percent}% (${SAMPLES_COLLECTED} samples @ ${rate} Hz)"
        fi
        
        sleep "$INTERVAL"
    done
    
    log "Monitoring duration completed"
}

# Run main function
main "$@"