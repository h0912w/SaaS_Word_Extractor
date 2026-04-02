#!/usr/bin/env python3
"""
Memory Profiling for QA Pipeline
Tracks memory usage during each phase of the QA pipeline.
"""

import subprocess
import sys
import time
from pathlib import Path

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("WARNING: psutil not available, memory monitoring disabled")


def get_memory_mb():
    """Get current process memory usage in MB."""
    if PSUTIL_AVAILABLE:
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    return 0.0


def run_with_memory_tracking(cmd, phase_name, base_dir):
    """Run a command and track memory usage."""
    print(f"\n{'='*60}")
    print(f"PHASE: {phase_name}")
    print(f"{'='*60}")

    start_mem = get_memory_mb()
    max_mem = start_mem
    min_mem = start_mem
    start_time = time.time()

    print(f"Starting memory: {start_mem:.1f} MB")

    process = subprocess.Popen(
        cmd,
        cwd=base_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=False,
        bufsize=1
    )

    last_check = time.time()
    check_interval = 1  # Check every second

    while True:
        line_bytes = process.stdout.readline()
        if not line_bytes:
            break

        # Periodic memory check
        current_time = time.time()
        if current_time - last_check >= check_interval:
            current_mem = get_memory_mb()
            max_mem = max(max_mem, current_mem)
            min_mem = min(min_mem, current_mem)
            last_check = current_time

        # Check if process completed
        if process.poll() is not None:
            remaining = process.stdout.read()
            break

    return_code = process.wait()
    elapsed = time.time() - start_time
    end_mem = get_memory_mb()

    print(f"\n[{phase_name} Memory Stats]")
    print(f"  Start:  {start_mem:.1f} MB")
    print(f"  End:    {end_mem:.1f} MB")
    print(f"  Max:    {max_mem:.1f} MB")
    print(f"  Min:    {min_mem:.1f} MB")
    print(f"  Delta:  {end_mem - start_mem:+.1f} MB")
    print(f"  Time:   {elapsed:.1f}s")
    print(f"  Status: {'OK' if return_code == 0 else f'FAILED ({return_code})'}")

    return return_code, {
        "phase": phase_name,
        "start_mb": start_mem,
        "end_mb": end_mem,
        "max_mb": max_mem,
        "min_mb": min_mem,
        "delta_mb": end_mem - start_mem,
        "time_sec": elapsed
    }


def main():
    base_dir = Path('C:/Users/h0912/claude_project/SaaS_Word_Extractor')

    print("\n" + "="*60)
    print("MEMORY PROFILING - QA PIPELINE")
    print("="*60)
    print(f"psutil available: {PSUTIL_AVAILABLE}")

    if not PSUTIL_AVAILABLE:
        print("ERROR: psutil required for memory profiling")
        sys.exit(1)

    all_stats = []

    # Phase 1: PREP
    return_code, stats = run_with_memory_tracking(
        [sys.executable, "src/pipeline.py", "--phase", "prep", "--max-words", "10000"],
        "PREP (Steps 1-4)",
        base_dir
    )
    all_stats.append(stats)
    if return_code != 0:
        print("\nERROR: PREP phase failed")
        sys.exit(1)

    # Phase 2: AI REVIEW
    return_code, stats = run_with_memory_tracking(
        [sys.executable, "src/ai_review_batch_processor.py", "--max-words", "10000"],
        "AI REVIEW (Steps 5-7)",
        base_dir
    )
    all_stats.append(stats)
    if return_code != 0:
        print("\nERROR: AI REVIEW phase failed")
        sys.exit(1)

    # Phase 3: CONSENSUS
    return_code, stats = run_with_memory_tracking(
        [sys.executable, "src/pipeline.py", "--phase", "consensus"],
        "CONSENSUS (Step 8)",
        base_dir
    )
    all_stats.append(stats)
    if return_code != 0:
        print("\nERROR: CONSENSUS phase failed")
        sys.exit(1)

    # Phase 4: EXPORT
    return_code, stats = run_with_memory_tracking(
        [sys.executable, "src/pipeline.py", "--phase", "export"],
        "EXPORT (Steps 9-10)",
        base_dir
    )
    all_stats.append(stats)
    if return_code != 0:
        print("\nERROR: EXPORT phase failed")
        sys.exit(1)

    # Summary
    print("\n" + "="*60)
    print("MEMORY PROFILING SUMMARY")
    print("="*60)

    global_max = max(s["max_mb"] for s in all_stats)
    global_min = min(s["min_mb"] for s in all_stats)

    print(f"\nOverall Memory Statistics:")
    print(f"  Global Maximum: {global_max:.1f} MB")
    print(f"  Global Minimum: {global_min:.1f} MB")
    print(f"  Peak Delta:     {global_max - global_min:.1f} MB")

    print(f"\nPer-Phase Statistics:")
    for s in all_stats:
        print(f"  {s['phase']:30s} | Max: {s['max_mb']:7.1f} MB | Min: {s['min_mb']:7.1f} MB | Delta: {s['delta_mb']:+7.1f} MB")

    # Save to file
    output_file = base_dir / "output" / "qa" / "memory_profile.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(output_file, 'w') as f:
        json.dump({
            "global_max_mb": global_max,
            "global_min_mb": global_min,
            "peak_delta_mb": global_max - global_min,
            "phases": all_stats
        }, f, indent=2)
    print(f"\nMemory profile saved to: {output_file}")


if __name__ == "__main__":
    main()
