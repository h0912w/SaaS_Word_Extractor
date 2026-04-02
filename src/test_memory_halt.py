#!/usr/bin/env python3
"""
Test Memory Halt Functionality
================================
Tests that memory monitoring correctly halts when threshold is exceeded.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from memory_monitor import MemoryMonitor, get_memory_mb


def test_memory_halt():
    """Test that memory halt works correctly."""
    print("=" * 60)
    print("TESTING MEMORY HALT FUNCTIONALITY")
    print("=" * 60)

    # Set a very low threshold to trigger halt quickly
    threshold_mb = 100  # Very low threshold for testing

    print(f"\nStarting memory monitor with threshold: {threshold_mb} MB")
    print(f"Current memory: {get_memory_mb():.1f} MB")

    monitor = MemoryMonitor(threshold_mb=threshold_mb, phase_name="TEST")
    monitor.start()

    print("\nAllocating memory to trigger halt...")

    # Allocate memory until halt
    data = []
    try:
        for i in range(100000):
            # Allocate 1MB per iteration
            data.append("x" * (1024 * 1024))  # 1 MB string

            if i % 1000 == 0:
                mem = get_memory_mb()
                print(f"  Allocated {i} MB, current memory: {mem:.1f} MB")

                if monitor.halt_occurred:
                    print(f"\n  HALT OCCURRED at {mem:.1f} MB!")
                    break

    except MemoryError as e:
        print(f"\nMemory error occurred: {e}")
    except Exception as e:
        print(f"\nException occurred: {e}")

    monitor.stop()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print(f"Halt occurred: {monitor.halt_occurred}")
    print(f"Peak memory: {monitor.peak_memory:.1f} MB")

    # Check if crash report was created
    crash_dir = Path("output/crash_reports")
    if crash_dir.exists():
        crash_files = list(crash_dir.glob("crash_*.json"))
        if crash_files:
            print(f"\nCrash report created: {crash_files[-1]}")
            return True
        else:
            print("\nWARNING: No crash report found!")
            return False
    else:
        print("\nWARNING: Crash directory not found!")
        return False


if __name__ == "__main__":
    success = test_memory_halt()
    sys.exit(0 if success else 1)
