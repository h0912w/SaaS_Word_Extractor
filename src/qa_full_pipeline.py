#!/usr/bin/env python3
"""
Full QA Pipeline - Runs entire pipeline from scratch for QA testing.

This script:
1. Cleans all intermediate and output files
2. Runs the complete pipeline from Step 1 to export
3. Runs QA analysis
4. Monitors memory usage throughout

Usage:
    python src/qa_full_pipeline.py [--max-words N]
"""

import argparse
import gc
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_memory_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        # Fallback: try Windows-specific method
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulonglong = ctypes.c_ulonglong
            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", c_ulonglong),
                    ("WorkingSetSize", c_ulonglong),
                    ("QuotaPeakPagedPoolUsage", c_ulonglong),
                    ("QuotaPagedPoolUsage", c_ulonglong),
                    ("QuotaPeakNonPagedPoolUsage", c_ulonglong),
                    ("QuotaNonPagedPoolUsage", c_ulonglong),
                    ("PagefileUsage", c_ulonglong),
                    ("PeakPagefileUsage", c_ulonglong),
                    ("PrivateUsage", c_ulonglong),
                ]
            counters = PROCESS_MEMORY_COUNTERS_EX()
            kernel32.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(),
                ctypes.bypointer(counters),
                ctypes.sizeof(counters)
            )
            return counters.WorkingSetSize / 1024 / 1024
        except Exception:
            return 0.0


def check_memory_limit(max_mb: float, phase: str) -> bool:
    """Check if memory usage exceeds limit. Returns True if OK, False if exceeds."""
    mem_mb = get_memory_mb()
    if mem_mb > max_mb:
        print(f"\n[MEMORY ALERT] {phase}: Memory usage {mem_mb:.1f} MB exceeds limit {max_mb} MB")
        print("Recommendation: Reduce batch size or use streaming mode")
        return False
    return True


def cleanup_outputs(base_dir: Path) -> None:
    """Remove all intermediate and output files for clean QA run."""
    print("\n" + "=" * 60)
    print("CLEANUP: Removing intermediate and output files")
    print("=" * 60)

    # Directories to clean
    dirs_to_clean = [
        base_dir / "output" / "intermediate",
        base_dir / "output" / "human_review",
        base_dir / "output" / "qa",
    ]

    # Files to clean
    files_to_clean = [
        base_dir / "output" / "saas_words.jsonl",
        base_dir / "output" / "rejected_words.jsonl",
        base_dir / "output" / "run_summary.json",
    ]

    cleaned_count = 0
    for dir_path in dirs_to_clean:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  Removed directory: {dir_path}")
            cleaned_count += 1

    for file_path in files_to_clean:
        if file_path.exists():
            file_path.unlink()
            print(f"  Removed file: {file_path}")
            cleaned_count += 1

    # Recreate empty directories
    for dir_path in dirs_to_clean:
        dir_path.mkdir(parents=True, exist_ok=True)

    print(f"Cleanup complete: {cleaned_count} items removed")


def run_command(
    cmd: list,
    phase: str,
    timeout: int,
    max_memory_mb: float,
    base_dir: Optional[Path] = None
) -> bool:
    """Run a command with memory monitoring."""
    print("\n" + "=" * 60)
    print(f"PHASE: {phase}")
    print("=" * 60)
    print(f"Command: {' '.join(cmd)}")
    print(f"Timeout: {timeout}s")

    cwd = base_dir if base_dir else Path.cwd()

    start_mem = get_memory_mb()
    start_time = time.time()

    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,  # Use binary mode to avoid encoding issues
            bufsize=1
        )

        # Monitor process with memory checks
        last_check = time.time()
        check_interval = 5  # Check memory every 5 seconds

        output_lines = []
        while True:
            line_bytes = process.stdout.readline()
            if not line_bytes:
                break

            # Decode with error handling
            try:
                line = line_bytes.decode('utf-8', errors='replace')
            except Exception:
                line = str(line_bytes)

            output_lines.append(line)
            # Safe print with error handling
            try:
                print(line.rstrip())
            except UnicodeEncodeError:
                # Fallback for characters that can't be printed
                print(line.encode('ascii', errors='replace').decode('ascii'))

            # Periodic memory check
            current_time = time.time()
            if current_time - last_check >= check_interval:
                current_mem = get_memory_mb()
                delta = current_mem - start_mem
                print(f"[Memory] {current_mem:.1f} MB (delta: +{delta:.1f} MB)", file=sys.stderr)

                if not check_memory_limit(max_memory_mb, phase):
                    print(f"[ERROR] Memory limit exceeded in phase {phase}")
                    process.terminate()
                    process.wait(timeout=10)
                    return False

                last_check = current_time

            # Check if process has completed
            if process.poll() is not None:
                # Read remaining output
                remaining = process.stdout.read()
                if remaining:
                    print(remaining.rstrip())
                break

        return_code = process.wait(timeout=timeout)

        elapsed = time.time() - start_time
        end_mem = get_memory_mb()

        print(f"\n[Phase {phase} completed]")
        print(f"  Return code: {return_code}")
        print(f"  Elapsed: {elapsed:.1f}s")
        print(f"  Memory: {end_mem:.1f} MB (delta: +{end_mem - start_mem:.1f} MB)")

        if return_code != 0:
            print(f"[ERROR] Phase {phase} failed with return code {return_code}")
            return False

        # Force garbage collection between phases
        gc.collect()
        time.sleep(1)  # Brief pause for system stabilization

        return True

    except subprocess.TimeoutExpired:
        print(f"[ERROR] Phase {phase} timed out after {timeout}s")
        try:
            process.kill()
        except Exception:
            pass
        return False
    except Exception as e:
        print(f"[ERROR] Phase {phase} failed with exception: {e}")
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Full QA Pipeline - Run complete pipeline from scratch"
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=0,
        help="Maximum words to process (0=unlimited, default: 0)"
    )
    parser.add_argument(
        "--max-memory-mb",
        type=float,
        default=8192,  # 8 GB default
        help="Maximum memory usage in MB before alert (default: 8192)"
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip cleanup step (use existing intermediates)"
    )
    args = parser.parse_args()

    base_dir = Path('C:/Users/h0912/claude_project/SaaS_Word_Extractor')

    print("\n" + "=" * 60)
    print("FULL QA PIPELINE - SaaS Word Extractor")
    print("=" * 60)
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"Max words: {args.max_words if args.max_words > 0 else 'unlimited'}")
    print(f"Memory limit: {args.max_memory_mb} MB")
    print("=" * 60)

    overall_start = time.time()
    success = True

    # Step 1: Cleanup
    if not args.skip_cleanup:
        cleanup_outputs(base_dir)

    # Step 2: Run prep phase (Steps 1-4)
    prep_cmd = [sys.executable, "src/pipeline.py", "--phase", "prep"]
    if args.max_words > 0:
        prep_cmd.extend(["--max-words", str(args.max_words)])

    if not run_command(
        prep_cmd,
        "PREP (Steps 1-4)",
        timeout=3600,
        max_memory_mb=args.max_memory_mb,
        base_dir=base_dir
    ):
        success = False
        goto_end = True
    else:
        goto_end = False

    # Step 3: Run AI review (Steps 5-7) - Using batch processor
    # The batch processor handles primary, challenge, and rebuttal reviews in one pass
    if not goto_end:
        ai_review_cmd = [sys.executable, "src/ai_review_batch_processor.py"]
        if args.max_words > 0:
            ai_review_cmd.extend(["--max-words", str(args.max_words)])

        if not run_command(
            ai_review_cmd,
            "AI REVIEW (Steps 5-7: Primary, Challenge, Rebuttal)",
            timeout=7200,
            max_memory_mb=args.max_memory_mb,
            base_dir=base_dir
        ):
            success = False
            goto_end = True

    # Step 6: Run consensus (Step 8) - Now uses streaming
    if not goto_end:
        consensus_cmd = [sys.executable, "src/pipeline.py", "--phase", "consensus"]
        if not run_command(
            consensus_cmd,
            "CONSENSUS (Step 8)",
            timeout=1800,
            max_memory_mb=args.max_memory_mb,
            base_dir=base_dir
        ):
            success = False
            goto_end = True

    # Step 7: Run export (Steps 9-10)
    if not goto_end:
        export_cmd = [sys.executable, "src/pipeline.py", "--phase", "export"]
        if not run_command(
            export_cmd,
            "EXPORT (Steps 9-10)",
            timeout=3600,
            max_memory_mb=args.max_memory_mb,
            base_dir=base_dir
        ):
            success = False
            goto_end = True

    # Final report
    overall_elapsed = time.time() - overall_start
    final_mem = get_memory_mb()

    print("\n" + "=" * 60)
    print("QA PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Status: {'SUCCESS' if success else 'FAILED'}")
    print(f"Total elapsed: {overall_elapsed:.1f}s ({overall_elapsed/60:.1f} minutes)")
    print(f"Final memory: {final_mem:.1f} MB")
    print(f"End time: {datetime.now().isoformat()}")
    print("=" * 60)

    if success:
        print("\nNext steps:")
        print("  - Review output files in output/")
        print("  - Check QA report in output/qa/")
        print("  - Run manual verification: python qa_samples.py")
    else:
        print("\nErrors occurred. Check logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
