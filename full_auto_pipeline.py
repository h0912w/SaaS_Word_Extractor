#!/usr/bin/env python3
"""
Full Auto Pipeline — Fully automated processing of all 28M words

This script orchestrates the entire pipeline:
1. Processes batches sequentially (100k words each)
2. Executes prep phase (Steps 1-4) via Python
3. Executes AI phase (Steps 5-7) via Agent calls
4. Executes consensus phase (Steps 8-10) via Python
5. Continues until all 282 batches complete
6. Auto-merges all results at end

No user intervention required — runs from start to finish.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auto_batch_processor import (
    load_progress_state, save_progress_state, reset_progress_state,
    cleanup_intermediate_files, print_batch_summary, prepare_next_batch_instructions,
    update_progress_after_batch, check_batch_output, BATCH_SIZE
)
from utils import get_logger

log = get_logger("full_auto_pipeline")


def run_command(cmd: list, description: str) -> Tuple[bool, str]:
    """Run a command and return success status and output."""
    log.info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hour timeout
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        log.error(f"Command failed: {e}")
        return False, e.stderr
    except subprocess.TimeoutExpired:
        log.error(f"Command timed out after 2 hours")
        return False, "Timeout"


def run_prep_phase(start_line: int, max_words: int) -> bool:
    """Run prep phase (Steps 1-4)."""
    log.info(f"Starting Prep Phase (Steps 1-4): Lines {start_line}-{start_line + max_words - 1}")

    cmd = [
        sys.executable, "src/pipeline.py",
        "--phase", "prep",
        "--batch-start", str(start_line),
        "--max-words", str(max_words)
    ]

    success, _ = run_command(cmd, "Prep Phase")
    return success


def run_consensus_phase() -> bool:
    """Run consensus and export phase (Steps 8-10)."""
    log.info("Starting Consensus Phase (Steps 8-10)")

    cmd = [sys.executable, "src/pipeline.py", "--phase", "consensus"]
    success, _ = run_command(cmd, "Consensus Phase")
    return success


def create_ai_instructions_file(batch_num: int, start_line: int, max_words: int) -> Path:
    """Create instructions file for AI agents."""
    instructions = prepare_next_batch_instructions({
        'current_batch': batch_num - 1,
        'last_start_line': start_line,
        'total_lines': 28108856,
        'total_batches': 282
    })

    instructions_file = Path("output/ai_instructions.json")
    instructions_file.parent.mkdir(parents=True, exist_ok=True)

    with open(instructions_file, 'w') as f:
        json.dump({
            'batch_number': batch_num,
            'start_line': start_line,
            'max_words': max_words,
            'total_batches': 282,
            'current_step': 'awaiting_ai_execution',
            'created_at': datetime.now().isoformat()
        }, f, indent=2)

    return instructions_file


def process_single_batch(batch_num: int, start_line: int) -> Optional[dict]:
    """
    Process a single batch through the full pipeline.

    Returns batch result dict if successful, None if failed.
    """
    log.info("=" * 70)
    log.info(f"PROCESSING BATCH {batch_num}: Lines {start_line}-{start_line + BATCH_SIZE - 1}")
    log.info("=" * 70)

    start_time = datetime.now()

    # Step 1: Prep Phase (Steps 1-4)
    if not run_prep_phase(start_line, BATCH_SIZE):
        log.error(f"Batch {batch_num}: Prep phase failed")
        return None

    # Step 2: Create AI instructions (signals AI agents to run)
    ai_instructions = create_ai_instructions_file(batch_num, start_line, BATCH_SIZE)
    log.info(f"AI instructions created: {ai_instructions}")
    log.info("Awaiting AI execution (Steps 5-7)...")

    # At this point, the orchestrator will detect ai_instructions.json
    # and execute the AI steps (5-7) using Agent tool calls
    # The AI steps will:
    # 1. Read the instructions
    # 2. Execute Step 5 (saas-title-judge agent)
    # 3. Execute Step 6 (challenge-reviewer agent)
    # 4. Execute Step 7 (rebuttal-reviewer agent)
    # 5. Write completion signal to ai_instructions.json

    # Wait for AI completion signal
    ai_completion_file = Path("output/ai_completion.json")
    max_wait_minutes = 30  # Maximum wait time for AI steps

    for i in range(max_wait_minutes * 2):  # Check every 30 seconds
        if ai_completion_file.exists():
            with open(ai_completion_file) as f:
                completion_data = json.load(f)
                if completion_data.get('batch_number') == batch_num:
                    log.info("AI execution completed successfully")
                    ai_completion_file.unlink()  # Clean up
                    break
        import time
        time.sleep(30)
    else:
        log.error(f"AI execution timed out after {max_wait_minutes} minutes")
        return None

    # Step 3: Consensus Phase (Steps 8-10)
    if not run_consensus_phase():
        log.error(f"Batch {batch_num}: Consensus phase failed")
        return None

    # Step 4: Verify output
    if not check_batch_output(batch_num):
        log.error(f"Batch {batch_num}: Output verification failed")
        return None

    elapsed = (datetime.now() - start_time).total_seconds()

    result = {
        'batch_number': batch_num,
        'start_line': start_line,
        'end_line': start_line + BATCH_SIZE - 1,
        'elapsed_seconds': elapsed,
        'completed_at': datetime.now().isoformat()
    }

    log.info(f"Batch {batch_num} completed in {elapsed:.0f} seconds")
    return result


def process_all_batches(skip_qa: bool = True):
    """Process all batches from start to finish."""
    log.info("=" * 70)
    log.info("FULL AUTO PIPELINE STARTING")
    log.info("=" * 70)
    log.info(f"Total batches to process: 282")
    log.info(f"Batch size: {BATCH_SIZE:,} words")
    log.info(f"Skip QA: {skip_qa}")

    # Reset state for fresh run
    state = reset_progress_state()
    cleanup_intermediate_files()

    batch_num = 1
    start_line = 1
    consecutive_failures = 0
    max_consecutive_failures = 3

    while batch_num <= 282:
        log.info("")
        log.info("=" * 70)
        log.info(f"STARTING BATCH {batch_num}/282")
        log.info(f"Progress: {100 * (batch_num - 1) / 282:.1f}% complete")
        log.info("=" * 70)

        result = process_single_batch(batch_num, start_line)

        if result:
            # Success - update progress
            consecutive_failures = 0
            update_progress_after_batch(
                state,
                batch_num,
                start_line,
                BATCH_SIZE
            )

            # Move to next batch
            start_line += BATCH_SIZE
            batch_num += 1

        else:
            # Failure - retry or abort
            consecutive_failures += 1
            log.error(f"Batch {batch_num} failed (consecutive failures: {consecutive_failures})")

            if consecutive_failures >= max_consecutive_failures:
                log.error(f"Too many consecutive failures ({max_consecutive_failures}), aborting")
                break

            log.info(f"Retrying batch {batch_num}...")
            continue

    # All done
    log.info("")
    log.info("=" * 70)
    log.info("ALL BATCHES PROCESSED")
    log.info("=" * 70)

    if not skip_qa:
        log.info("Running QA phase...")
        # Run QA (Steps 11-12)
        run_command([sys.executable, "src/pipeline.py", "--phase", "qa"], "QA Phase")

    log.info("Full auto pipeline complete!")
    log.info("To merge all batch results:")
    log.info("  python src/batch_orchestrator.py --phase merge")


def resume_from_checkpoint():
    """Resume processing from last checkpoint."""
    state = load_progress_state()
    print_batch_summary(state)

    if state['status'] == 'completed':
        log.info("All batches already completed!")
        return

    batch_num = state['current_batch'] + 1
    start_line = state['last_start_line']

    log.info(f"Resuming from batch {batch_num} (line {start_line})")

    consecutive_failures = 0
    max_consecutive_failures = 3

    while batch_num <= 282:
        log.info("")
        log.info(f"RESUMING BATCH {batch_num}/282")
        log.info(f"Progress: {100 * (batch_num - 1) / 282:.1f}% complete")

        result = process_single_batch(batch_num, start_line)

        if result:
            consecutive_failures = 0
            update_progress_after_batch(state, batch_num, start_line, BATCH_SIZE)
            start_line += BATCH_SIZE
            batch_num += 1
        else:
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log.error("Too many failures, aborting")
                break
            log.info("Retrying...")

    log.info("Resume complete!")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Full Auto Pipeline")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--skip-qa", action="store_true", default=True, help="Skip QA phase")
    args = parser.parse_args()

    if args.resume:
        resume_from_checkpoint()
    else:
        process_all_batches(skip_qa=args.skip_qa)


if __name__ == "__main__":
    main()
