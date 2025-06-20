#!/bin/bash
# Test script for Yocto target to validate cgroup v2 functionality

echo "=== CGROUP COMPATIBILITY TEST ==="

# Test 1: Check if we're using cgroup v2
echo "[TEST 1] Checking cgroup version..."
if mount | grep -q "cgroup2 on /sys/fs/cgroup type cgroup2"; then
    echo "✓ PASS: System is using cgroup v2"
else
    echo "✗ FAIL: System is not using cgroup v2"
    exit 1
fi

# Test 2: Check if basic directories exist
echo "[TEST 2] Checking for basic directories..."
if [ -d "/sys/fs/cgroup" ]; then
    echo "✓ PASS: /sys/fs/cgroup exists"
else
    echo "✗ FAIL: /sys/fs/cgroup does not exist"
    exit 1
fi

# Test 3: Check if we can read controllers
echo "[TEST 3] Checking available controllers..."
if [ -f "/sys/fs/cgroup/cgroup.controllers" ]; then
    controllers=$(cat /sys/fs/cgroup/cgroup.controllers)
    echo "✓ PASS: Available controllers: $controllers"
else
    echo "✗ FAIL: Cannot read controllers"
    exit 1
fi

# Test 4: Check if we can write to subtree_control
echo "[TEST 4] Testing controller activation..."
if [ -f "/sys/fs/cgroup/cgroup.subtree_control" ]; then
    # Backup current setting
    curr_subtree=$(cat /sys/fs/cgroup/cgroup.subtree_control)
    
    # Try to enable CPU controller
    echo "+cpu" > /sys/fs/cgroup/cgroup.subtree_control 2>/dev/null
    if grep -q "cpu" /sys/fs/cgroup/cgroup.subtree_control 2>/dev/null; then
        echo "✓ PASS: Can enable controllers"
    else
        echo "✗ FAIL: Cannot enable controllers (permission issue?)"
    fi
    
    # Restore original setting if we need to
    if [ "$curr_subtree" != "$(cat /sys/fs/cgroup/cgroup.subtree_control)" ]; then
        echo "$curr_subtree" > /sys/fs/cgroup/cgroup.subtree_control 2>/dev/null
    fi
else
    echo "✗ FAIL: No cgroup.subtree_control file found"
    exit 1
fi

# Test 5: Check if we can create a cgroup
echo "[TEST 5] Testing cgroup creation..."
TEST_CGROUP="/sys/fs/cgroup/test_yocto_compat"
if [ -d "$TEST_CGROUP" ]; then
    # Clean up from previous test
    rmdir "$TEST_CGROUP" 2>/dev/null
fi

mkdir "$TEST_CGROUP" 2>/dev/null
if [ -d "$TEST_CGROUP" ]; then
    echo "✓ PASS: Can create cgroups"
    
    # Test 5b: Check if we can write to it
    echo "100000 100000" > "$TEST_CGROUP/cpu.max" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✓ PASS: Can write to cgroup files"
    else
        echo "✗ FAIL: Cannot write to cgroup files (permission issue?)"
    fi
    
    # Clean up
    rmdir "$TEST_CGROUP" 2>/dev/null
else
    echo "✗ FAIL: Cannot create cgroups (permission issue?)"
fi

# Test 6: Check specific controllers needed by our scripts
echo "[TEST 6] Testing required controllers..."

for ctrl in "cpu" "memory" "pids"; do
    if grep -q "$ctrl" /sys/fs/cgroup/cgroup.controllers 2>/dev/null; then
        echo "✓ PASS: $ctrl controller available"
    else
        echo "✗ FAIL: $ctrl controller not available"
    fi
done

# Test 7: Check if we can assign processes to cgroups
echo "[TEST 7] Testing process assignment..."
TEST_CGROUP="/sys/fs/cgroup/test_proc"
mkdir "$TEST_CGROUP" 2>/dev/null

if [ -d "$TEST_CGROUP" ]; then
    # Try to assign current process to cgroup
    echo $$ > "$TEST_CGROUP/cgroup.procs" 2>/dev/null
    
    if grep -q $$ "$TEST_CGROUP/cgroup.procs" 2>/dev/null; then
        echo "✓ PASS: Can assign processes to cgroups"
        # Move back to root cgroup
        echo $$ > /sys/fs/cgroup/cgroup.procs
    else
        echo "✗ FAIL: Cannot assign processes to cgroups"
    fi
    
    # Clean up
    rmdir "$TEST_CGROUP" 2>/dev/null
else
    echo "✗ FAIL: Could not create test cgroup"
fi

# Summary
echo ""
echo "=== TEST SUMMARY ==="
echo "System appears to be $(grep -q "cgroup2" /proc/mounts && echo "compatible" || echo "incompatible") with the cgroup scripts."
echo ""
echo "If all tests passed, the scripts should work on this system."
echo "If any tests failed, you may need to modify the scripts or check permissions."
