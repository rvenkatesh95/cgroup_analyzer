#!/bin/bash
# Script to apply memory usage limits using memory controller
# Modified for direct execution as root on Yocto target

echo "=== Applying Memory Usage Limits ==="

# Get available system memory
total_memory_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
total_memory_mb=$((total_memory_kb / 1024))
total_memory_gb=$((total_memory_mb / 1024))

echo "System has ${total_memory_gb}GB (${total_memory_mb}MB) of total memory"

# Ensure memory controller is enabled
if ! grep -q "memory" /sys/fs/cgroup/cgroup.subtree_control 2>/dev/null; then
    echo "+memory" > /sys/fs/cgroup/cgroup.subtree_control
    echo "✓ Enabled memory controller"
else
    echo "✓ Memory controller already enabled"
fi

# Ensure the cgroup exists
if [ ! -d /sys/fs/cgroup/mymem ]; then
    echo "Creating cgroup: mymem"
    mkdir -p /sys/fs/cgroup/mymem
    echo "✓ Created cgroup: mymem"
else
    echo "✓ Using existing cgroup: mymem"
fi

# Ask user for memory limit input method
echo ""
echo "Choose memory limit input method:"
echo "1) Percentage of total system memory"
echo "2) Absolute value (MB/GB)"
read -p "Enter choice (1 or 2): " input_method

case $input_method in
    1)
        # Percentage-based input
        read -p "Enter memory limit percentage (1-90): " mem_percent
        
        # Validate input
        if ! [[ "$mem_percent" =~ ^[0-9]+$ ]] || [ "$mem_percent" -lt 1 ] || [ "$mem_percent" -gt 90 ]; then
            echo "Error: Please enter a valid percentage between 1 and 90"
            exit 1
        fi
        
        # Calculate memory limit in bytes
        memory_limit_mb=$((total_memory_mb * mem_percent / 100))
        memory_limit_bytes=$((memory_limit_mb * 1024 * 1024))
        
        echo "✓ Memory limit set to ${mem_percent}% of total memory (${memory_limit_mb}MB)"
        ;;
    2)
        # Absolute value input
        read -p "Enter memory limit (e.g., 512M, 2G, 1024M): " mem_limit
        
        # Parse the input to get bytes
        if [[ "$mem_limit" =~ ^([0-9]+)([MmGg])$ ]]; then
            value="${BASH_REMATCH[1]}"
            unit="${BASH_REMATCH[2]}"
            
            if [[ "$unit" =~ [Mm] ]]; then
                memory_limit_bytes=$((value * 1024 * 1024))
                memory_limit_mb=$value
            else
                memory_limit_bytes=$((value * 1024 * 1024 * 1024))
                memory_limit_mb=$((value * 1024))
            fi
            
            echo "✓ Memory limit set to ${mem_limit} (${memory_limit_mb}MB)"
        else
            echo "Error: Invalid memory limit format"
            exit 1
        fi
        ;;
    *)
        echo "Error: Invalid choice"
        exit 1
        ;;
esac

# Apply the memory limit
echo "$memory_limit_bytes" > /sys/fs/cgroup/mymem/memory.max
echo "✓ Applied memory limit: $memory_limit_bytes bytes"

# Handle swap configuration
if [ -f /sys/fs/cgroup/mymem/memory.swap.max ]; then
    read -p "Do you want to configure swap limit? (y/n): " set_swap
    if [[ "$set_swap" =~ ^[Yy]$ ]]; then
        echo ""
        echo "Swap configuration options:"
        echo "1) Disable swap completely (0)"
        echo "2) Set swap to same as memory limit"
        echo "3) Set custom swap limit"
        echo "4) Use unlimited swap (max)"
        read -p "Choose swap option (1-4): " swap_choice
        
        case $swap_choice in
            1)
                echo "0" > /sys/fs/cgroup/mymem/memory.swap.max
                echo "✓ Swap disabled for this cgroup"
                ;;
            2)
                echo "$memory_limit_bytes" > /sys/fs/cgroup/mymem/memory.swap.max
                echo "✓ Swap limit set same as memory limit (${memory_limit_mb}MB)"
                ;;
            3)
                read -p "Enter swap limit (e.g., 512M, 2G): " swap_limit
                # Parse swap limit
                if [[ "$swap_limit" =~ ^([0-9]+)([MmGg])$ ]]; then
                    swap_value="${BASH_REMATCH[1]}"
                    swap_unit="${BASH_REMATCH[2]}"
                    
                    if [[ "$swap_unit" =~ [Mm] ]]; then
                        swap_bytes=$((swap_value * 1024 * 1024))
                        swap_mb=$swap_value
                    else
                        swap_bytes=$((swap_value * 1024 * 1024 * 1024))
                        swap_mb=$((swap_value * 1024))
                    fi
                    
                    echo "$swap_bytes" > /sys/fs/cgroup/mymem/memory.swap.max
                    echo "✓ Swap limit set to ${swap_limit} (${swap_mb}MB)"
                else
                    echo "⚠ Invalid swap limit format. Using unlimited swap."
                    echo "max" > /sys/fs/cgroup/mymem/memory.swap.max
                fi
                ;;
            4)
                echo "max" > /sys/fs/cgroup/mymem/memory.swap.max
                echo "✓ Swap set to unlimited"
                ;;
            *)
                echo "⚠ Invalid choice. Using unlimited swap."
                echo "max" > /sys/fs/cgroup/mymem/memory.swap.max
                ;;
        esac
    fi
fi

# Handle memory low watermark (soft limit)
read -p "Do you want to set a memory low watermark (soft limit)? (y/n): " set_low
if [[ "$set_low" =~ ^[Yy]$ ]]; then
    echo ""
    echo "Memory low watermark protects memory from reclamation when system is under pressure."
    suggested_low=$((memory_limit_mb * 80 / 100))
    echo "Suggested value: ${suggested_low}MB (80% of memory limit)"
    read -p "Enter memory low watermark in MB (or press Enter for suggested): " low_mb
    
    if [ -z "$low_mb" ]; then
        low_mb=$suggested_low
    fi
    
    if [[ "$low_mb" =~ ^[0-9]+$ ]]; then
        low_bytes=$((low_mb * 1024 * 1024))
        echo "$low_bytes" > /sys/fs/cgroup/mymem/memory.low
        echo "✓ Set memory low watermark to ${low_mb}MB"
    else
        echo "⚠ Invalid input. Skipping low watermark configuration."
    fi
fi

# Handle memory high watermark (throttling)
read -p "Do you want to set a memory high watermark (throttling threshold)? (y/n): " set_high
if [[ "$set_high" =~ ^[Yy]$ ]]; then
    echo ""
    echo "Memory high watermark triggers throttling before hitting the hard limit."
    suggested_high=$((memory_limit_mb * 90 / 100))
    echo "Suggested value: ${suggested_high}MB (90% of memory limit)"
    read -p "Enter memory high watermark in MB (or press Enter for suggested): " high_mb
    
    if [ -z "$high_mb" ]; then
        high_mb=$suggested_high
    fi
    
    if [[ "$high_mb" =~ ^[0-9]+$ ]] && [ "$high_mb" -lt "$memory_limit_mb" ]; then
        high_bytes=$((high_mb * 1024 * 1024))
        echo "$high_bytes" > /sys/fs/cgroup/mymem/memory.high
        echo "✓ Set memory high watermark to ${high_mb}MB"
    else
        echo "⚠ Invalid input or value >= memory limit. Skipping high watermark configuration."
    fi
fi

# Handle OOM killer configuration
read -p "Do you want to disable OOM killer for this cgroup? (y/n): " disable_oom
if [[ "$disable_oom" =~ ^[Yy]$ ]]; then
    echo "1" > /sys/fs/cgroup/mymem/memory.oom.group
    echo "✓ Enabled OOM group kill (kills entire cgroup on OOM)"
    
    echo ""
    echo "Warning: Disabling OOM killer can cause system instability if processes exceed limits."
    read -p "Are you sure you want to disable OOM killer? (y/n): " confirm_oom
    if [[ "$confirm_oom" =~ ^[Yy]$ ]]; then
        echo "1" > /sys/fs/cgroup/mymem/memory.oom_kill_disable
        echo "✓ OOM killer disabled for this cgroup"
        echo "  But OOM group kill is enabled to kill the entire cgroup on OOM"
    fi
fi

# Display current settings
echo ""
echo "Current memory cgroup settings:"
echo "Memory Max: $(cat /sys/fs/cgroup/mymem/memory.max | numfmt --to=iec-i --suffix=B --format="%.1f")"
echo "Memory Current: $(cat /sys/fs/cgroup/mymem/memory.current | numfmt --to=iec-i --suffix=B --format="%.1f")"

if [ -f /sys/fs/cgroup/mymem/memory.low ]; then
    low_val=$(cat /sys/fs/cgroup/mymem/memory.low)
    if [ "$low_val" != "0" ]; then
        echo "Memory Low: $(echo $low_val | numfmt --to=iec-i --suffix=B --format="%.1f")"
    fi
fi

if [ -f /sys/fs/cgroup/mymem/memory.high ]; then
    high_val=$(cat /sys/fs/cgroup/mymem/memory.high)
    if [ "$high_val" != "max" ]; then
        echo "Memory High: $(echo $high_val | numfmt --to=iec-i --suffix=B --format="%.1f")"
    fi
fi

if [ -f /sys/fs/cgroup/mymem/memory.swap.max ]; then
    swap_val=$(cat /sys/fs/cgroup/mymem/memory.swap.max)
    if [ "$swap_val" = "max" ]; then
        echo "Swap Max: unlimited"
    else
        echo "Swap Max: $(echo $swap_val | numfmt --to=iec-i --suffix=B --format="%.1f")"
    fi
fi

echo "System Total Memory: ${total_memory_gb}GB"

# Show memory statistics
echo ""
echo "Memory statistics (if any processes are in the cgroup):"
if [ -f /sys/fs/cgroup/mymem/memory.stat ]; then
    echo "Anon memory: $(grep "^anon " /sys/fs/cgroup/mymem/memory.stat | awk '{print $2}' | numfmt --to=iec-i --suffix=B --format="%.1f")"
    echo "File memory: $(grep "^file " /sys/fs/cgroup/mymem/memory.stat | awk '{print $2}' | numfmt --to=iec-i --suffix=B --format="%.1f")"
fi

echo ""
echo "To run a process in this cgroup, use: echo \$PID > /sys/fs/cgroup/mymem/cgroup.procs"
echo "To monitor memory usage: watch -n 1 'cat /sys/fs/cgroup/mymem/memory.current | numfmt --to=iec-i --suffix=B'"
