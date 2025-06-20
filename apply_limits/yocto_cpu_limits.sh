#!/bin/bash
# Script to apply CPU usage limits with support for multiple cgroups and weight ratios
# Modified for direct execution as root on Yocto target

echo "=== Applying CPU Usage Limits ==="

# Get available CPU cores
cpu_cores=$(nproc)
echo "System has $cpu_cores CPU cores available"

# Enable CPU controller (needed for cgroup v2)
if ! grep -q "cpu" /sys/fs/cgroup/cgroup.subtree_control 2>/dev/null; then
    echo "+cpu" > /sys/fs/cgroup/cgroup.subtree_control
    echo "✓ Enabled CPU controller"
else
    echo "✓ CPU controller already enabled"
fi

# Enable cpuset controller if available
if ! grep -q "cpuset" /sys/fs/cgroup/cgroup.subtree_control 2>/dev/null; then
    echo "+cpuset" >> /sys/fs/cgroup/cgroup.subtree_control
    echo "✓ Enabled cpuset controller"
else
    echo "✓ cpuset controller already enabled"
fi

# Ask about weight configuration first
echo ""
read -p "Do you want to configure CPU weights for multiple cgroups? (y/n): " use_weights

if [[ "$use_weights" =~ ^[Yy]$ ]]; then
    echo ""
    echo "CPU weights control relative CPU share when cgroups compete for resources."
    echo "You need multiple cgroups to make weights meaningful."
    
    read -p "How many cgroups do you want to create (2-10): " num_cgroups
    
    # Validate cgroup count
    if ! [[ "$num_cgroups" =~ ^[0-9]+$ ]] || [ "$num_cgroups" -lt 2 ] || [ "$num_cgroups" -gt 10 ]; then
        echo "Error: Please enter a number between 2 and 10"
        exit 1
    fi
    
    # Collect cgroup names and weight ratios
    declare -a cgroup_names
    declare -a weight_ratios
    
    echo ""
    echo "Enter cgroup names and their weight ratios:"
    echo "Examples: webserver=300, database=500, batch=100"
    
    for ((i=1; i<=num_cgroups; i++)); do
        read -p "Cgroup $i name: " cgroup_name
        read -p "Cgroup $i weight (1-10000): " weight_ratio
        
        # Validate inputs
        cgroup_names[$i]="$cgroup_name"
        weight_ratios[$i]="$weight_ratio"
    done
    
    # Display the weight distribution
    echo ""
    echo "Weight distribution when all cgroups are competing:"
    total_weight=0
    for ((i=1; i<=num_cgroups; i++)); do
        total_weight=$((total_weight + weight_ratios[i]))
    done
    
    for ((i=1; i<=num_cgroups; i++)); do
        percentage=$((weight_ratios[i] * 100 / total_weight))
        echo "  ${cgroup_names[i]}: weight ${weight_ratios[i]} → ${percentage}% of available CPU"
    done
    
    read -p "Continue with this configuration? (y/n): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        exit 1
    fi
    
    multi_cgroup_mode=true
else
    # Single cgroup mode
    multi_cgroup_mode=false
    num_cgroups=1
    cgroup_names[1]="mycpu"
    echo "✓ Using single cgroup mode: mycpu"
fi

# Get CPU limit settings that will apply to all cgroups
echo ""
read -p "Enter CPU limit percentage for each cgroup (1-100): " cpu_percent

# Validate input
if ! [[ "$cpu_percent" =~ ^[0-9]+$ ]] || [ "$cpu_percent" -lt 1 ] || [ "$cpu_percent" -gt 100 ]; then
    echo "Error: Please enter a valid percentage between 1 and 100"
    exit 1
fi

# Calculate quota based on percentage (using 100000 microseconds as period)
period=100000
quota=$((period * cpu_percent / 100))

# Create and configure all cgroups
echo ""
echo "Creating and configuring cgroups..."

for ((i=1; i<=num_cgroups; i++)); do
    cgroup_name="${cgroup_names[i]}"
    cgroup_path="/sys/fs/cgroup/$cgroup_name"
    
    # Create cgroup
    if [ ! -d "$cgroup_path" ]; then
        mkdir -p "$cgroup_path"
        echo "✓ Created cgroup: $cgroup_name"
    else
        echo "✓ Using existing cgroup: $cgroup_name"
    fi
    
    # Apply CPU limit
    echo "$quota $period" > "$cgroup_path/cpu.max"
    echo "✓ Set CPU limit to ${cpu_percent}% for $cgroup_name (${quota}/${period})"
    
    # Apply weight if in multi-cgroup mode
    if [ "$multi_cgroup_mode" = true ]; then
        echo "${weight_ratios[i]}" > "$cgroup_path/cpu.weight"
        echo "✓ Set CPU weight to ${weight_ratios[i]} for $cgroup_name"
    fi
done

# Handle burst configuration for all cgroups
echo ""
read -p "Do you want to set CPU burst for all cgroups? (y/n): " set_burst
if [[ "$set_burst" =~ ^[Yy]$ ]]; then
    # Suggest burst values based on CPU limit percentage
    min_burst=$((1000 + cpu_percent * 100))
    max_burst=$((5000 + cpu_percent * 500))
    
    echo "Suggested burst range for ${cpu_percent}% CPU limit: ${min_burst}-${max_burst} microseconds"
    read -p "Enter CPU burst in microseconds (same for all cgroups): " burst_value
    
    # Validate burst input
    if [[ "$burst_value" =~ ^[0-9]+$ ]] && [ "$burst_value" -ge 0 ]; then
        for ((i=1; i<=num_cgroups; i++)); do
            echo "$burst_value" > "/sys/fs/cgroup/${cgroup_names[i]}/cpu.max.burst"
            echo "✓ Set CPU burst to ${burst_value} microseconds for ${cgroup_names[i]}"
        done
    else
        echo "⚠ Invalid burst value. Skipping burst configuration."
    fi
fi

# Handle CPU core restriction for all cgroups
echo ""
read -p "Do you want to restrict CPU cores for all cgroups? (y/n): " set_cores
if [[ "$set_cores" =~ ^[Yy]$ ]]; then
    echo "Available CPU cores (0 to $((cpu_cores-1)))"
    read -p "Enter CPU cores to use (e.g., '0-2' or '0,2,3'): " core_list
    
    # Validate core list format (basic validation)
    if [[ "$core_list" =~ ^[0-9,-]+$ ]]; then
        for ((i=1; i<=num_cgroups; i++)); do
            echo "$core_list" > "/sys/fs/cgroup/${cgroup_names[i]}/cpuset.cpus"
            echo "✓ Set CPU cores to ${core_list} for ${cgroup_names[i]}"
        done
    else
        echo "⚠ Invalid core list format. Skipping core restriction."
    fi
else
    # Set all available cores for all cgroups
    all_cores="0-$((cpu_cores-1))"
    
    for ((i=1; i<=num_cgroups; i++)); do
        echo "$all_cores" > "/sys/fs/cgroup/${cgroup_names[i]}/cpuset.cpus"
        echo "✓ Set all CPU cores ($all_cores) for ${cgroup_names[i]}"
    done
fi

# Display current settings for all cgroups
echo ""
echo "=== Current cgroup settings ==="
for ((i=1; i<=num_cgroups; i++)); do
    cgroup_name="${cgroup_names[i]}"
    cgroup_path="/sys/fs/cgroup/$cgroup_name"
    
    echo ""
    echo "Cgroup: $cgroup_name"
    echo "  CPU Max: $(cat $cgroup_path/cpu.max)"
    echo "  CPU Weight: $(cat $cgroup_path/cpu.weight)"
    
    if [ -f "$cgroup_path/cpu.max.burst" ]; then
        echo "  CPU Burst: $(cat $cgroup_path/cpu.max.burst)"
    fi
    
    if [ -f "$cgroup_path/cpuset.cpus" ]; then
        echo "  CPU Cores: $(cat $cgroup_path/cpuset.cpus)"
    fi
done

echo ""
echo "Available CPU cores: $cpu_cores"

# Show usage instructions
echo ""
echo "=== Usage Instructions ==="
for ((i=1; i<=num_cgroups; i++)); do
    cgroup_name="${cgroup_names[i]}"
    echo "To run a process in $cgroup_name:"
    echo "  echo \$PID > /sys/fs/cgroup/$cgroup_name/cgroup.procs"
    echo "  Or: cgexec -g cpu:$cgroup_name your_command (if cgexec is available)"
done

if [ "$multi_cgroup_mode" = true ]; then
    echo ""
    echo "=== Weight Testing ==="
    echo "To test CPU weight distribution, run CPU-intensive tasks in each cgroup:"
    for ((i=1; i<=num_cgroups; i++)); do
        cgroup_name="${cgroup_names[i]}"
        echo "  sh -c 'echo \$\$ > /sys/fs/cgroup/$cgroup_name/cgroup.procs && yes > /dev/null'"
    done
    echo ""
    echo "Monitor with: htop (press F4 to filter by process name)"
    echo "Or: watch -n 1 'for cg in $(ls /sys/fs/cgroup/ | grep -E \"$(echo ${cgroup_names[@]} | tr ' ' '|')\"); do echo \$cg: \$(cat /sys/fs/cgroup/\$cg/cpu.stat | grep usage_usec); done'"
fi
