"""
Auto Batch Processor — Fully automated batch processing for 28M words

This processor handles:
- 100k word batches sequentially
- Full pipeline (Steps 1-12) for each batch
- Automatic resume from last completed batch
- Progress tracking and error recovery
- No user intervention required
"""

import json
import time
from pathlib import Path
from datetime import datetime

from config import (
    INTER_LOADED, INTER_SCREENED, INTER_PRIMARY,
    INTER_CHALLENGED, INTER_REBUTTED, INTER_CONSENSUS,
    PROGRESS_DIR, OUTPUT_DIR, QA_DIR
)

# Intermediate files for cleanup
INTER_REVIEWED = INTER_PRIMARY  # Alias for compatibility

BATCH_DIR = OUTPUT_DIR / "batch_"  # Will be dynamically constructed
from utils import get_logger, write_json, read_json

log = get_logger("auto_batch_processor")

# Batch size: 100k words per batch
BATCH_SIZE = 100000

# Input file path
INPUT_FILE = Path("input/all_words_deduped.txt")

# Progress state file
PROGRESS_STATE_FILE = PROGRESS_DIR / "auto_batch_progress.json"


def get_total_lines() -> int:
    """Count total lines in input file."""
    count = 0
    with open(INPUT_FILE, 'r', encoding='utf-8', errors='replace') as f:
        for _ in f:
            count += 1
    return count


def load_progress_state() -> dict:
    """Load current progress state."""
    if PROGRESS_STATE_FILE.exists():
        with open(PROGRESS_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    # Initial state
    total_lines = get_total_lines()
    return {
        "total_lines": total_lines,
        "total_batches": (total_lines // BATCH_SIZE) + (1 if total_lines % BATCH_SIZE else 0),
        "current_batch": 0,
        "last_start_line": 1,
        "completed_batches": [],
        "status": "not_started",
        "last_updated": datetime.now().isoformat()
    }


def save_progress_state(state: dict):
    """Save current progress state."""
    state["last_updated"] = datetime.now().isoformat()
    with open(PROGRESS_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    log.info(f"Progress state saved: Batch {state['current_batch']}/{state['total_batches']}")


def reset_progress_state():
    """Reset progress state to start fresh."""
    total_lines = get_total_lines()
    state = {
        "total_lines": total_lines,
        "total_batches": (total_lines // BATCH_SIZE) + (1 if total_lines % BATCH_SIZE else 0),
        "current_batch": 0,
        "last_start_line": 1,
        "completed_batches": [],
        "status": "not_started",
        "last_updated": datetime.now().isoformat()
    }
    save_progress_state(state)
    log.info(f"Progress state reset: {state['total_batches']} batches to process")
    return state


def cleanup_intermediate_files():
    """Clean up intermediate files for fresh start."""
    intermediate_files = [
        INTER_LOADED, INTER_SCREENED, INTER_PRIMARY,
        INTER_CHALLENGED, INTER_REBUTTED, INTER_CONSENSUS
    ]
    for f in intermediate_files:
        if f.exists():
            f.unlink()
            log.info(f"Cleaned up: {f.name}")


def print_batch_summary(state: dict):
    """Print batch processing summary."""
    total = state['total_batches']
    current = state['current_batch']
    completed = len(state['completed_batches'])

    log.info("=" * 60)
    log.info("BATCH PROCESSING SUMMARY")
    log.info("=" * 60)
    log.info(f"Total lines: {state['total_lines']:,}")
    log.info(f"Batch size: {BATCH_SIZE:,}")
    log.info(f"Total batches: {total}")
    log.info(f"Current batch: {current}")
    log.info(f"Completed: {completed}/{total} ({100*completed/total:.1f}%)")
    log.info(f"Next start line: {state['last_start_line']:,}")
    log.info("=" * 60)


def print_final_summary(state: dict):
    """Print final processing summary."""
    total = state['total_batches']
    completed = len(state['completed_batches'])

    log.info("")
    log.info("=" * 60)
    log.info("FINAL PROCESSING SUMMARY")
    log.info("=" * 60)
    log.info(f"Total batches: {total}")
    log.info(f"Completed: {completed}")
    log.info(f"Status: {state['status']}")
    log.info("=" * 60)
    log.info("")
    log.info("To merge all batch results, run:")
    log.info(f"  python src/batch_orchestrator.py --phase merge")
    log.info("=" * 60)


def check_batch_output(batch_num: int) -> bool:
    """Check if batch output files exist and are valid."""
    batch_dir = BATCH_DIR / f"batch_{batch_num:03d}"

    # Check for required output files
    required_files = [
        batch_dir / f"saas_words_batch_{batch_num:03d}.jsonl",
        batch_dir / f"rejected_words_batch_{batch_num:03d}.jsonl",
        batch_dir / f"run_summary_batch_{batch_num:03d}.json"
    ]

    for f in required_files:
        if not f.exists():
            return False

        # Check file is not empty
        if f.stat().st_size == 0:
            return False

    return True


def prepare_next_batch_instructions(state: dict) -> dict:
    """
    Prepare instructions for the next batch.
    This is meant to be called by the main Claude Code session.
    """
    current_batch = state['current_batch'] + 1
    start_line = state['last_start_line']

    # Calculate end line (don't exceed total lines)
    total_lines = state['total_lines']
    end_line = min(start_line + BATCH_SIZE - 1, total_lines)

    instructions = {
        "batch_number": current_batch,
        "start_line": start_line,
        "end_line": end_line,
        "words_to_process": end_line - start_line + 1,
        "command": f"python src/pipeline.py --phase all --batch-start {start_line} --max-words {BATCH_SIZE}",
        "output_dir": str(BATCH_DIR / f"batch_{current_batch:03d}")
    }

    return instructions


def update_progress_after_batch(state: dict, batch_num: int, start_line: int, words_processed: int):
    """Update progress state after completing a batch."""
    # Record completed batch
    if batch_num not in state['completed_batches']:
        state['completed_batches'].append({
            "batch_number": batch_num,
            "start_line": start_line,
            "words_processed": words_processed,
            "completed_at": datetime.now().isoformat()
        })

    # Update state for next batch
    state['current_batch'] = batch_num
    state['last_start_line'] = start_line + words_processed

    if state['last_start_line'] >= state['total_lines']:
        state['status'] = 'completed'
    else:
        state['status'] = 'ready_for_next_batch'

    save_progress_state(state)


def run_auto_check():
    """Run automatic progress check and print status."""
    state = load_progress_state()
    print_batch_summary(state)

    if state['status'] == 'completed':
        print_final_summary(state)
    elif state['status'] == 'ready_for_next_batch':
        instructions = prepare_next_batch_instructions(state)
        log.info("")
        log.info("NEXT BATCH INSTRUCTIONS:")
        log.info(f"  Batch {instructions['batch_number']}: Lines {instructions['start_line']:,}-{instructions['end_line']:,}")
        log.info(f"  Words to process: {instructions['words_to_process']:,}")
        log.info(f"  Command: {instructions['command']}")

    return state


def main():
    """Main entry point for progress checking."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        log.info("Resetting progress state...")
        state = reset_progress_state()
        print_batch_summary(state)
    elif len(sys.argv) > 1 and sys.argv[1] == '--cleanup':
        log.info("Cleaning up intermediate files...")
        cleanup_intermediate_files()
    else:
        run_auto_check()


if __name__ == '__main__':
    main()
