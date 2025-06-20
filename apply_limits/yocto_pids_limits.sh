#!/bin/bash
# Script to apply process/thread limits using pids controller
# Modified for direct execution as root on Yocto target

echo "=== Applying Process/Thread Limits ==="

# Get current system process information
total_processes=$(ps aux --no-headers | wc -l)
total_threads=$(ps -eLf --no-headers | wc -l)
kernel_threads=$(ps -eLf --no-headers | awk '$3 == 2 {print $2}' | sort -u | wc -l)
user_threads=$((total_threads - kernel_threads))

echo "Current system statistics:"
echo "Total processes: $total_processes"
echo "Total threads: $total_threads"
echo "User threads: $user_threads"
echo "Kernel threads: $kernel_threads"

# Get system limits
if [ -f /proc/sys/kernel/pid_max ]; then
    system_pid_max=$(cat /proc/sys/kernel/pid_max)
    echo "System PID max: $system_pid_max"
fi

if [ -f /proc/sys/kernel/threads-max ]; then
    system_threads_max=$(cat /proc/sys/kernel/threads-max)
    echo "System threads max: $system_threads_max"
fi

echo ""

# Enable pids controller if not already enabled
if ! grep -q "pids" /sys/fs/cgroup/cgroup.subtree_control 2>/dev/null; then
    echo "+pids" > /sys/fs/cgroup/cgroup.subtree_control
    echo "✓ Enabled pids controller"
else
    echo "✓ pids controller already enabled"
fi

# Ensure the cgroup exists
if [ ! -d /sys/fs/cgroup/mypids ]; then
    echo "Creating cgroup: mypids"
    mkdir -p /sys/fs/cgroup/mypids
    echo "✓ Created cgroup: mypids"
else
    echo "✓ Using existing cgroup: mypids"
fi

# Ask user for PID limit configuration method
echo ""
echo "Choose PID limit configuration method:"
echo "1) Set absolute limit (number of PIDs/threads)"
echo "2) Set percentage of system maximum"
echo "3) Set based on current system usage + buffer"
echo "4) Set unlimited (remove restrictions)"
read -p "Enter choice (1-4): " limit_method

case $limit_method in
    1)
        # Absolute limit
        echo ""
        echo "Setting absolute PID/thread limit..."
        read -p "Enter maximum number of PIDs/threads: " pid_limit
        
        # Validate input
        if ! [[ "$pid_limit" =~ ^[0-9]+$ ]] || [ "$pid_limit" -lt 1 ]; then
            echo "Error: Please enter a valid number greater than 0"
            exit 1
        fi
        
        # Warn if limit is very low
        if [ "$pid_limit" -lt 10 ]; then
            echo "⚠ Warning: Very low PID limit ($pid_limit) may cause system instability"
            read -p "Continue? (y/n): " confirm_low
            if [[ ! "$confirm_low" =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
        
        echo "✓ PID limit set to $pid_limit"
        ;;
    2)
        # Percentage of system maximum
        echo ""
        if [ -n "$system_threads_max" ]; then
            read -p "Enter percentage of system maximum (1-90): " pid_percent
            
            # Validate input
            if ! [[ "$pid_percent" =~ ^[0-9]+$ ]] || [ "$pid_percent" -lt 1 ] || [ "$pid_percent" -gt 90 ]; then
                echo "Error: Please enter a valid percentage between 1 and 90"
                exit 1
            fi
            
            pid_limit=$((system_threads_max * pid_percent / 100))
            echo "✓ PID limit set to ${pid_percent}% of system max ($pid_limit PIDs)"
        else
            echo "Error: Could not determine system maximum threads"
            exit 1
        fi
        ;;
    3)
        # Based on current usage + buffer
        echo ""
        echo "Current thread usage: $total_threads"
        echo "Buffer options:"
        echo "1) Conservative (current + 50%)"
        echo "2) Moderate (current + 100%)"  
        echo "3) Liberal (current + 200%)"
        echo "4) Custom buffer"
        read -p "Choose buffer option (1-4): " buffer_choice
        
        case $buffer_choice in
            1)
                pid_limit=$((total_threads + total_threads / 2))
                echo "✓ PID limit set to current usage + 50% ($pid_limit PIDs)"
                ;;
            2)
                pid_limit=$((total_threads * 2))
                echo "✓ PID limit set to current usage + 100% ($pid_limit PIDs)"
                ;;
            3)
                pid_limit=$((total_threads * 3))
                echo "✓ PID limit set to current usage + 200% ($pid_limit PIDs)"
                ;;
            4)
                read -p "Enter buffer percentage (e.g., 50 for 50% extra): " custom_buffer
                if [[ "$custom_buffer" =~ ^[0-9]+$ ]]; then
                    pid_limit=$((total_threads + (total_threads * custom_buffer / 100)))
                    echo "✓ PID limit set to current usage + ${custom_buffer}% ($pid_limit PIDs)"
                else
                    echo "Error: Invalid buffer percentage"
                    exit 1
                fi
                ;;
            *)
                echo "Error: Invalid choice"
                exit 1
                ;;
        esac
        ;;
    4)
        # Unlimited
        pid_limit="max"
        echo "✓ PID limit set to unlimited"
        ;;
    *)
        echo "Error: Invalid choice"
        exit 1
        ;;
esac

# Apply the PID limit
echo "$pid_limit" > /sys/fs/cgroup/mypids/pids.max
echo "✓ Applied PID limit: $pid_limit"

# Handle additional PID controller features
echo ""
echo "Additional PID controller options:"

# Fork bomb protection
read -p "Enable fork bomb protection? (y/n): " enable_forkbomb
if [[ "$enable_forkbomb" =~ ^[Yy]$ ]]; then
    if [ "$pid_limit" != "max" ]; then
        # Calculate a limit that will trigger before system-wide limits
        forkbomb_limit=$((pid_limit * 90 / 100))
        echo "$forkbomb_limit" > /sys/fs/cgroup/mypids/pids.max
        echo "✓ Reduced PID limit to $forkbomb_limit for fork bomb protection"
        pid_limit=$forkbomb_limit
    else
        echo "⚠ Cannot enable fork bomb protection with unlimited PIDs"
    fi
fi

# Process monitoring alerts
read -p "Set up process monitoring alerts? (y/n): " setup_alerts
if [[ "$setup_alerts" =~ ^[Yy]$ ]]; then
    if [ "$pid_limit" != "max" ]; then
        read -p "Alert threshold percentage (e.g., 80 for 80% of limit): " alert_percent
        
        if [[ "$alert_percent" =~ ^[0-9]+$ ]] && [ "$alert_percent" -gt 0 ] && [ "$alert_percent" -lt 100 ]; then
            alert_threshold=$((pid_limit * alert_percent / 100))
            
            # Create a monitoring script
            monitor_script="/usr/local/bin/pids_monitor.sh"
            cat > "$monitor_script" << EOF
#!/bin/bash
CGROUP_PATH="/sys/fs/cgroup/mypids"
ALERT_THRESHOLD=$alert_threshold
LIMIT=$pid_limit

while true; do
    if [ -f "\$CGROUP_PATH/pids.current" ]; then
        CURRENT=\$(cat "\$CGROUP_PATH/pids.current")
        if [ \$CURRENT -ge \$ALERT_THRESHOLD ]; then
            echo "ALERT: PID usage at \$CURRENT/\$LIMIT (threshold: \$ALERT_THRESHOLD)" >&2
            # Add additional alert actions here (e.g., send to syslog)
            logger -p daemon.warning "cgroup PID usage at \$CURRENT/\$LIMIT"
        fi
    fi
    sleep 10
done
EOF
            chmod +x "$monitor_script"
            echo "✓ Created monitoring script at $monitor_script"
            echo "  Run in background: nohup $monitor_script > /var/log/pids_monitor.log 2>&1 &"
        else
            echo "⚠ Invalid threshold percentage. Skipping alert setup."
        fi
    else
        echo "⚠ Cannot set up alerts with unlimited PIDs"
    fi
fi

# Display current settings and statistics
echo ""
echo "Current PID cgroup settings:"
echo "PIDs Max: $(cat /sys/fs/cgroup/mypids/pids.max)"
echo "PIDs Current: $(cat /sys/fs/cgroup/mypids/pids.current)"

# Show events if any
if [ -f /sys/fs/cgroup/mypids/pids.events ]; then
    events_content=$(cat /sys/fs/cgroup/mypids/pids.events)
    echo "PID Events:"
    echo "$events_content" | while read -r line; do
        echo "  $line"
    done
fi

echo ""
echo "System comparison:"
echo "Cgroup limit: $(cat /sys/fs/cgroup/mypids/pids.max)"
echo "Current system total: $total_threads threads"
echo "Available system max: ${system_threads_max:-unknown}"

# Show processes currently in the cgroup
echo ""
if [ -s /sys/fs/cgroup/mypids/cgroup.procs ]; then
    proc_count=$(wc -l < /sys/fs/cgroup/mypids/cgroup.procs)
    echo "Processes currently in this cgroup: $proc_count"
    if [ "$proc_count" -gt 0 ] && [ "$proc_count" -le 10 ]; then
        cat /sys/fs/cgroup/mypids/cgroup.procs | head -10
    fi
else
    echo "No processes currently in this cgroup"
fi

echo ""
echo "Usage commands:"
echo "Add process to cgroup: echo \$PID > /sys/fs/cgroup/mypids/cgroup.procs"
echo "Add current shell: echo \$\$ > /sys/fs/cgroup/mypids/cgroup.procs"
echo "Monitor usage: watch -n 2 'cat /sys/fs/cgroup/mypids/pids.current'"
echo "Check events: cat /sys/fs/cgroup/mypids/pids.events"
