#!/usr/bin/env python3
"""
Run All Batches — Sequential batch processor for 28M words

This script runs all 282 batches sequentially without user intervention.
Each batch processes 100k words through the full pipeline (Steps 1-12).

Usage:
    python run_all_batches.py              # Process all 282 batches
    python run_all_batches.py --resume     # Resume from last checkpoint
    python run_all_batches.py --start N    # Start from batch N
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# Batch configuration
BATCH_SIZE = 100000
TOTAL_LINES = 28108856
TOTAL_BATCHES = (TOTAL_LINES // BATCH_SIZE) + (1 if TOTAL_LINES % BATCH_SIZE else 0)

# Paths
PROGRESS_FILE = Path("output/batch_progress.json")
LOG_FILE = Path("output/batch_processing.log")


def log_message(msg: str):
    """Log message to both console and log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_msg + '\n')


def run_command(cmd: list, timeout: int = 7200) -> tuple[bool, str]:
    """
    Run a command and return (success, output).

    Args:
        cmd: Command to run
        timeout: Timeout in seconds (default 2 hours)
    """
    try:
        log_message(f"Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )

        success = result.returncode == 0
        output = result.stdout if success else result.stderr

        # Log last few lines of output
        lines = output.strip().split('\n')
        if lines:
            log_message(f"Output (last 10 lines):")
            for line in lines[-10:]:
                log_message(f"  {line}")

        return success, output

    except subprocess.TimeoutExpired:
        log_message(f"ERROR: Command timed out after {timeout} seconds")
        return False, "Timeout"
    except Exception as e:
        log_message(f"ERROR: {e}")
        return False, str(e)


def load_progress() -> dict:
    """Load batch processing progress."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)

    return {
        "last_completed_batch": 0,
        "last_start_line": 1,
        "completed_batches": [],
        "status": "not_started",
        "last_updated": datetime.now().isoformat()
    }


def save_progress(progress: dict):
    """Save batch processing progress."""
    progress["last_updated"] = datetime.now().isoformat()
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def _clear_intermediate_files():
    """Clear intermediate files to avoid file lock issues."""
    import glob
    import os

    intermediate_patterns = [
        "output/intermediate/*.jsonl",
        "output/intermediate/*.json"
    ]

    for pattern in intermediate_patterns:
        for filepath in glob.glob(pattern):
            try:
                os.remove(filepath)
                log_message(f"Cleared: {filepath}")
            except Exception as e:
                log_message(f"Could not clear {filepath}: {e}")


def run_single_batch(batch_num: int, start_line: int) -> bool:
    """
    Run a single batch through the full pipeline.

    Args:
        batch_num: Batch number (1-indexed)
        start_line: Starting line number

    Returns:
        True if batch completed successfully, False otherwise
    """
    end_line = min(start_line + BATCH_SIZE - 1, TOTAL_LINES)
    word_count = end_line - start_line + 1

    log_message("")
    log_message("=" * 70)
    log_message(f"BATCH {batch_num}/{TOTAL_BATCHES}")
    log_message(f"Lines: {start_line:,} - {end_line:,} ({word_count:,} words)")
    log_message(f"Progress: {100 * (batch_num - 1) / TOTAL_BATCHES:.1f}%")
    log_message("=" * 70)

    start_time = time.time()

    # Don't clear intermediate files at start - they're needed for the pipeline

    # Step 1-4: Prep Phase (screening & normalization)
    log_message("Step 1-4: Prep Phase (screening & normalization)")
    cmd = [
        sys.executable, "src/pipeline.py",
        "--phase", "prep",
        "--batch-start", str(start_line),
        "--max-words", str(BATCH_SIZE)
    ]

    success, output = run_command(cmd, timeout=1800)
    if not success:
        log_message(f"ERROR: Prep phase failed for batch {batch_num}")
        return False

    # Step 5: Primary Review (AI)
    log_message("Step 5: Primary Review (AI - saas-title-judge)")
    cmd = [sys.executable, "src/pipeline.py", "--phase", "step5"]
    success, output = run_command(cmd, timeout=3600)
    if not success:
        log_message(f"ERROR: Step 5 failed for batch {batch_num}")
        return False

    # Step 6: Challenge Review (AI)
    log_message("Step 6: Challenge Review (AI - challenge-reviewer)")
    cmd = [sys.executable, "src/pipeline.py", "--phase", "step6"]
    success, output = run_command(cmd, timeout=3600)
    if not success:
        log_message(f"ERROR: Step 6 failed for batch {batch_num}")
        return False

    # Step 7: Rebuttal Review (AI)
    log_message("Step 7: Rebuttal Review (AI - rebuttal-reviewer)")
    cmd = [sys.executable, "src/pipeline.py", "--phase", "step7"]
    success, output = run_command(cmd, timeout=3600)
    if not success:
        log_message(f"ERROR: Step 7 failed for batch {batch_num}")
        return False

    # Step 8: Consensus Phase (voting)
    log_message("Step 8: Consensus Phase (voting)")
    cmd = [sys.executable, "src/pipeline.py", "--phase", "consensus"]
    success, output = run_command(cmd, timeout=1800)
    if not success:
        log_message(f"ERROR: Consensus phase failed for batch {batch_num}")
        return False

    # Step 9-10: Export Phase (JSONL/JSON + XLSX/CSV)
    log_message("Step 9-10: Export Phase (JSONL/JSON + XLSX/CSV)")
    cmd = [sys.executable, "src/pipeline.py", "--phase", "export"]
    success, output = run_command(cmd, timeout=1800)
    if not success:
        log_message(f"ERROR: Export phase failed for batch {batch_num}")
        return False

    # Move output files to batch directory
    log_message("DEBUG: About to move output files to batch directory...")
    batch_dir = Path(f"output/batch_{batch_num:03d}")
    batch_dir.mkdir(parents=True, exist_ok=True)
    log_message(f"DEBUG: Batch directory created: {batch_dir}")

    # Files to copy
    files_to_copy = [
        ("output/saas_words.jsonl", batch_dir / "saas_words.jsonl"),
        ("output/rejected_words.jsonl", batch_dir / "rejected_words.jsonl"),
        ("output/run_summary.json", batch_dir / "run_summary.json"),
    ]

    import shutil
    for src, dst in files_to_copy:
        src_path = Path(src)
        if src_path.exists():
            try:
                shutil.copy2(src_path, dst)
                log_message(f"  Copied: {src_path.name} -> batch_{batch_num:03d}/")
            except Exception as e:
                log_message(f"  Warning: Could not copy {src_path.name}: {e}")

    elapsed = time.time() - start_time
    log_message(f"Batch {batch_num} completed in {elapsed:.0f} seconds ({elapsed/60:.1f} minutes)")

    # Verify batch output (check for standard naming in batch directory)
    expected_files = [
        batch_dir / "saas_words.jsonl",
        batch_dir / "rejected_words.jsonl",
        batch_dir / "run_summary.json"
    ]

    missing = [f for f in expected_files if not f.exists()]
    if missing:
        log_message(f"WARNING: Missing output files: {[f.name for f in missing]}")
        log_message(f"Batch directory contents: {[f.name for f in batch_dir.iterdir()] if batch_dir.exists() else 'N/A'}")
        return False

    log_message(f"Output verified: batch_{batch_num:03d}/")

    # Clear intermediate files after successful batch completion for next batch
    _clear_intermediate_files()

    return True


def run_all_batches(start_batch: int = 1, resume: bool = False):
    """
    Run all batches from start_batch to TOTAL_BATCHES.

    Args:
        start_batch: Starting batch number (1-indexed)
        resume: If True, resume from last completed batch
    """
    log_message("")
    log_message("=" * 70)
    log_message("ALL BATCHES PROCESSOR STARTING")
    log_message("=" * 70)
    log_message(f"Total batches: {TOTAL_BATCHES}")
    log_message(f"Batch size: {BATCH_SIZE:,} words")
    log_message(f"Total lines: {TOTAL_LINES:,}")

    # Load progress
    progress = load_progress()

    if resume and progress["completed_batches"]:
        last_completed = progress["completed_batches"][-1]["batch_number"]
        start_batch = last_completed + 1
        log_message(f"Resuming from batch {start_batch}")

    # Calculate starting line
    start_line = 1 + (start_batch - 1) * BATCH_SIZE

    log_message(f"Starting from batch {start_batch} (line {start_line:,})")
    log_message("")

    consecutive_failures = 0
    max_consecutive_failures = 5

    for batch_num in range(start_batch, TOTAL_BATCHES + 1):
        # Run the batch
        success = run_single_batch(batch_num, start_line)

        if success:
            # Update progress
            consecutive_failures = 0
            progress["completed_batches"].append({
                "batch_number": batch_num,
                "start_line": start_line,
                "completed_at": datetime.now().isoformat()
            })
            progress["last_completed_batch"] = batch_num
            # Calculate next start line based on batch number (not current start_line)
            progress["last_start_line"] = 1 + batch_num * BATCH_SIZE
            progress["status"] = "in_progress"
            save_progress(progress)

            # Move to next batch
            start_line = 1 + batch_num * BATCH_SIZE

        else:
            # Handle failure
            consecutive_failures += 1
            log_message(f"ERROR: Batch {batch_num} failed (consecutive failures: {consecutive_failures})")

            if consecutive_failures >= max_consecutive_failures:
                log_message(f"CRITICAL: Too many consecutive failures ({max_consecutive_failures}), stopping")
                progress["status"] = "failed"
                save_progress(progress)
                return

            log_message(f"Retrying batch {batch_num} in 10 seconds...")
            time.sleep(10)
            continue  # Retry same batch

    # All batches complete
    progress["status"] = "completed"
    save_progress(progress)

    log_message("")
    log_message("=" * 70)
    log_message("ALL BATCHES COMPLETED SUCCESSFULLY!")
    log_message("=" * 70)
    log_message(f"Total batches processed: {len(progress['completed_batches'])}/{TOTAL_BATCHES}")
    log_message("")
    log_message("To merge all batch results, run:")
    log_message("  python src/batch_orchestrator.py --phase merge")
    log_message("")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run all batches for 28M words")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--start", type=int, default=1, help="Start from batch N")
    args = parser.parse_args()

    run_all_batches(start_batch=args.start, resume=args.resume)


if __name__ == "__main__":
    main()
