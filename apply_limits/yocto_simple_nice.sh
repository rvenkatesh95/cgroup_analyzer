#!/bin/bash
# Simplified script to apply tiered nice values to processes in the mypids cgroup
# Modified for direct execution as root on Yocto target

# No need for sudo check since we expect to run as root

CGROUP_PATH="/sys/fs/cgroup/mypids"
HIGH_PRIORITY="-15"    # Higher priority (negative nice value)
MEDIUM_PRIORITY="0"    # Normal priority
LOW_PRIORITY="15"      # Lower priority (positive nice value)
HIGH_COUNT=30          # Number of processes for high priority
MEDIUM_COUNT=30        # Number of processes for medium priority

# Function to display colored text
print_color() {
    local color=$1
    local text=$2
    case $color in
        "green") echo -e "\033[0;32m$text\033[0m" ;;
        "red") echo -e "\033[0;31m$text\033[0m" ;;
        "yellow") echo -e "\033[1;33m$text\033[0m" ;;
        "blue") echo -e "\033[0;34m$text\033[0m" ;;
        *) echo "$text" ;;
    esac
}

# Check if cgroup exists
if [ ! -d "$CGROUP_PATH" ]; then
    print_color "red" "Error: cgroup $CGROUP_PATH does not exist"
    exit 1
fi

# Get processes in cgroup
if [ ! -f "$CGROUP_PATH/cgroup.procs" ]; then
    print_color "red" "Error: Cannot read processes in cgroup"
    exit 1
fi

# Count processes in cgroup
proc_count=$(wc -l < "$CGROUP_PATH/cgroup.procs")
if [ $proc_count -eq 0 ]; then
    print_color "yellow" "Warning: No processes found in cgroup"
    exit 0
fi

print_color "green" "✓ Found $proc_count processes in cgroup"

# Read processes into array
mapfile -t pids < "$CGROUP_PATH/cgroup.procs"
total_pids=${#pids[@]}

print_color "blue" "===== APPLYING NICE VALUES ====="
print_color "yellow" "First $HIGH_COUNT processes: High priority (nice $HIGH_PRIORITY)"
print_color "yellow" "Next $MEDIUM_COUNT processes: Medium priority (nice $MEDIUM_PRIORITY)" 
print_color "yellow" "Remaining processes: Low priority (nice $LOW_PRIORITY)"

# Apply high priority
high_limit=$((HIGH_COUNT < total_pids ? HIGH_COUNT : total_pids))
if [ $high_limit -gt 0 ]; then
    print_color "blue" "[1] Applying high priority to first $high_limit processes..."
    for (( i=0; i<high_limit; i++ )); do
        pid=${pids[i]}
        if kill -0 "$pid" 2>/dev/null; then
            renice -n "$HIGH_PRIORITY" -p "$pid" > /dev/null 2>&1
            echo -n "."
        fi
    done
    echo ""
fi

# Apply medium priority
if [ $total_pids -gt $HIGH_COUNT ]; then
    medium_limit=$(( (HIGH_COUNT + MEDIUM_COUNT) < total_pids ? (HIGH_COUNT + MEDIUM_COUNT) : total_pids ))
    medium_count=$((medium_limit - HIGH_COUNT))
    
    print_color "blue" "[2] Applying medium priority to next $medium_count processes..."
    for (( i=HIGH_COUNT; i<medium_limit; i++ )); do
        pid=${pids[i]}
        if kill -0 "$pid" 2>/dev/null; then
            renice -n "$MEDIUM_PRIORITY" -p "$pid" > /dev/null 2>&1
            echo -n "."
        fi
    done
    echo ""
fi

# Apply low priority
if [ $total_pids -gt $((HIGH_COUNT + MEDIUM_COUNT)) ]; then
    low_count=$((total_pids - HIGH_COUNT - MEDIUM_COUNT))
    
    print_color "blue" "[3] Applying low priority to remaining $low_count processes..."
    for (( i=HIGH_COUNT+MEDIUM_COUNT; i<total_pids; i++ )); do
        pid=${pids[i]}
        if kill -0 "$pid" 2>/dev/null; then
            renice -n "$LOW_PRIORITY" -p "$pid" > /dev/null 2>&1
            echo -n "."
        fi
    done
    echo ""
fi

print_color "green" "✓ Completed applying nice values to $proc_count processes"

# Verify nice values
print_color "blue" "===== VERIFYING NICE VALUES ====="
echo "Checking a sample of processes in each priority group..."

# Function to check a PID
check_pid() {
    local pid=$1
    local expected=$2
    local group=$3
    
    if kill -0 "$pid" 2>/dev/null; then
        nice=$(ps -p "$pid" -o ni= 2>/dev/null | tr -d ' ')
        cmd=$(ps -p "$pid" -o comm= 2>/dev/null | cut -c 1-15)
        
        if [ "$nice" = "$expected" ]; then
            print_color "green" "✓ $group: PID $pid ($cmd) has correct nice value: $nice"
            return 0
        else
            print_color "red" "✗ $group: PID $pid ($cmd) has wrong nice value: $nice (expected $expected)"
            return 1
        fi
    fi
    return 1
}

errors=0
success=0

# Check a sample of each group
if [ $high_limit -gt 0 ]; then
    # Check first high priority process
    check_pid "${pids[0]}" "$HIGH_PRIORITY" "High" && ((success++)) || ((errors++))
    
    # Check middle high priority process if available
    if [ $high_limit -gt 2 ]; then
        middle_idx=$((high_limit / 2))
        check_pid "${pids[$middle_idx]}" "$HIGH_PRIORITY" "High" && ((success++)) || ((errors++))
    fi
fi

if [ $total_pids -gt $HIGH_COUNT ]; then
    # Check first medium priority process
    check_pid "${pids[$HIGH_COUNT]}" "$MEDIUM_PRIORITY" "Medium" && ((success++)) || ((errors++))
    
    # Check middle medium priority process if available
    if [ $medium_count -gt 2 ]; then
        middle_idx=$((HIGH_COUNT + medium_count / 2))
        check_pid "${pids[$middle_idx]}" "$MEDIUM_PRIORITY" "Medium" && ((success++)) || ((errors++))
    fi
fi

if [ $total_pids -gt $((HIGH_COUNT + MEDIUM_COUNT)) ]; then
    # Check first low priority process
    check_pid "${pids[$((HIGH_COUNT + MEDIUM_COUNT))]}" "$LOW_PRIORITY" "Low" && ((success++)) || ((errors++))
    
    # Check last process
    check_pid "${pids[$((total_pids - 1))]}" "$LOW_PRIORITY" "Low" && ((success++)) || ((errors++))
fi

echo ""
if [ $errors -eq 0 ]; then
    print_color "green" "✓ All sampled processes have correct nice values!"
else
    print_color "red" "✗ $errors sampled processes have incorrect nice values"
    print_color "yellow" "This may be due to:"
    print_color "yellow" "1. Process ownership (some processes may be owned by different users)"
    print_color "yellow" "2. System restrictions on nice values"
    print_color "yellow" "3. Container/virtualization restrictions"
    print_color "yellow" "4. Process termination during verification"
fi

echo ""
print_color "blue" "===== COMMAND FOR FULL VERIFICATION ====="
echo "To see nice values for all processes in the cgroup, run:"
echo "for pid in \$(cat $CGROUP_PATH/cgroup.procs); do ps -p \$pid -o pid,ni,user,comm --no-headers; done | sort -k2,2n"
