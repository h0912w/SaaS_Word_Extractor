"""
Main Orchestrator — For use within main Claude Code session

This orchestrator coordinates all batch processing with AI agent execution.
To be called directly from the main Claude Code session.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config import INTER_SCREENED, INTER_REVIEWED, INTER_CHALLENGED, INTER_REBUTTED, BATCH_SIZE
from utils import get_logger, read_jsonl, write_json
from auto_batch_processor import (
    load_progress_state, save_progress_state, reset_progress_state,
    cleanup_intermediate_files, print_batch_summary,
    update_progress_after_batch, PROGRESS_STATE_FILE
)

log = get_logger("main_orchestrator")


def run_subprocess(cmd: list, timeout: int = 3600) -> tuple[bool, str]:
    """Run a subprocess command safely."""
    log.info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        success = result.returncode == 0
        output = result.stdout if success else result.stderr
        return success, output
    except subprocess.TimeoutExpired:
        return False, f"Timeout after {timeout} seconds"
    except Exception as e:
        return False, str(e)


def prepare_batch(start_line: int, max_words: int) -> bool:
    """Run prep phase (Steps 1-4) for a batch."""
    log.info(f"Prep Phase: Lines {start_line}-{start_line + max_words - 1}")

    cmd = [
        sys.executable, "src/pipeline.py",
        "--phase", "prep",
        "--batch-start", str(start_line),
        "--max-words", str(max_words)
    ]

    success, output = run_subprocess(cmd, timeout=1800)
    if not success:
        log.error(f"Prep phase failed: {output[:500]}")
    return success


def finalize_batch() -> bool:
    """Run consensus phase (Steps 8-10) for current batch."""
    log.info("Consensus Phase (Steps 8-10)")

    cmd = [sys.executable, "src/pipeline.py", "--phase", "consensus"]
    success, output = run_subprocess(cmd, timeout=1800)

    if not success:
        log.error(f"Consensus phase failed: {output[:500]}")
    return success


def check_ai_agents_ready() -> bool:
    """Check if AI agents are properly configured."""
    # Check if agent files exist
    agent_dir = Path(".claude/agents")
    required_agents = [
        "saas-title-judge.md",
        "challenge-reviewer.md",
        "rebuttal-reviewer.md"
    ]

    for agent_file in required_agents:
        if not (agent_dir / agent_file).exists():
            log.warning(f"Agent file missing: {agent_file}")
            return False

    return True


def get_current_batch_info() -> Optional[Dict[str, Any]]:
    """Get information about the current batch to process."""
    state = load_progress_state()

    if state['status'] == 'completed':
        return None

    batch_num = state['current_batch'] + 1
    start_line = state['last_start_line']

    return {
        'batch_number': batch_num,
        'start_line': start_line,
        'end_line': min(start_line + BATCH_SIZE - 1, state['total_lines']),
        'total_batches': state['total_batches']
    }


def mark_batch_complete(batch_num: int, start_line: int):
    """Mark a batch as complete in progress tracking."""
    state = load_progress_state()
    update_progress_after_batch(state, batch_num, start_line, BATCH_SIZE)


def get_screened_tokens_count() -> int:
    """Get count of tokens that passed screening (need AI review)."""
    if not INTER_SCREENED.exists():
        return 0

    count = 0
    for record in read_jsonl(INTER_SCREENED):
        # Count tokens that need AI review (not whitelisted or rejected)
        screen_result = record.get('screen_result', '')
        if screen_result not in ('reject', 'whitelist'):
            count += 1

    return count


def orchestrate_single_batch(agent_caller, batch_info: Dict[str, Any]) -> bool:
    """
    Orchestrate a single batch through all pipeline steps.

    Args:
        agent_caller: Function that calls AI agents (provided by main session)
        batch_info: Dict with batch_number, start_line, end_line

    Returns:
        True if batch completed successfully, False otherwise
    """
    batch_num = batch_info['batch_number']
    start_line = batch_info['start_line']
    max_words = BATCH_SIZE

    log.info("")
    log.info("=" * 70)
    log.info(f"BATCH {batch_num}/{batch_info['total_batches']}: Lines {start_line}-{batch_info['end_line']}")
    log.info(f"Progress: {100 * (batch_num - 1) / batch_info['total_batches']:.1f}%")
    log.info("=" * 70)

    start_time = datetime.now()

    # Step 1: Prep Phase (Steps 1-4) - Python scripts
    log.info("Step 1-4: Prep Phase (screening & normalization)")
    if not prepare_batch(start_line, max_words):
        log.error(f"Batch {batch_num}: Prep phase failed")
        return False

    # Check if any tokens need AI review
    screened_count = get_screened_tokens_count()
    if screened_count == 0:
        log.info("No tokens require AI review (all filtered/whitelisted)")
    else:
        log.info(f"Tokens requiring AI review: {screened_count:,}")

        # Step 2: AI Phase (Steps 5-7) - AI Agents
        log.info("Step 5: Primary Review (saas-title-judge agent)")
        if not agent_caller('step5', batch_num):
            log.error(f"Batch {batch_num}: Step 5 failed")
            return False

        log.info("Step 6: Challenge Review (challenge-reviewer agent)")
        if not agent_caller('step6', batch_num):
            log.error(f"Batch {batch_num}: Step 6 failed")
            return False

        log.info("Step 7: Rebuttal Review (rebuttal-reviewer agent)")
        if not agent_caller('step7', batch_num):
            log.error(f"Batch {batch_num}: Step 7 failed")
            return False

    # Step 3: Consensus Phase (Steps 8-10) - Python scripts
    log.info("Step 8-10: Consensus Phase (voting & export)")
    if not finalize_batch():
        log.error(f"Batch {batch_num}: Consensus phase failed")
        return False

    elapsed = (datetime.now() - start_time).total_seconds()
    log.info(f"Batch {batch_num} completed in {elapsed:.0f} seconds ({elapsed/60:.1f} minutes)")

    # Mark complete
    mark_batch_complete(batch_num, start_line)

    return True


def get_processing_plan() -> Dict[str, Any]:
    """Get the complete processing plan."""
    state = load_progress_state()

    return {
        'total_batches': state['total_batches'],
        'completed_batches': len(state['completed_batches']),
        'current_batch': state['current_batch'] + 1,
        'next_start_line': state['last_start_line'],
        'total_lines': state['total_lines'],
        'status': state['status']
    }


def print_next_instructions():
    """Print instructions for next processing step."""
    plan = get_processing_plan()

    log.info("")
    log.info("=" * 70)
    log.info("PROCESSING PLAN")
    log.info("=" * 70)
    log.info(f"Total batches: {plan['total_batches']}")
    log.info(f"Completed: {plan['completed_batches']}")
    log.info(f"Current batch: {plan['current_batch']}")
    log.info(f"Next start line: {plan['next_start_line']:,}")
    log.info(f"Status: {plan['status']}")

    if plan['status'] != 'completed':
        log.info("")
        log.info("To continue processing, the main Claude Code session should:")
        log.info("1. Call orchestrate_single_batch() with appropriate agent_caller function")
        log.info("2. Repeat until all batches complete")

    log.info("=" * 70)


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true", help="Show processing plan")
    parser.add_argument("--reset", action="store_true", help="Reset progress")
    args = parser.parse_args()

    if args.reset:
        reset_progress_state()
        cleanup_intermediate_files()
        print_batch_summary(load_progress_state())
    elif args.plan:
        print_next_instructions()
    else:
        print_next_instructions()


if __name__ == "__main__":
    main()
