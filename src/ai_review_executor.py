#!/usr/bin/env python3
"""
AI Review Executor
==================
Executes the AI review phases (primary, challenge, rebuttal) using the current Claude Code session.
This script coordinates the LLM judgment process while maintaining the separation between
script and AI responsibilities as defined in CLAUDE.md.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from utils import get_logger, read_jsonl, write_jsonl

log = get_logger("ai_review_executor")

# File paths
INTER_SCREENED = Path("output/intermediate/04_screened_tokens.jsonl")
INTER_PRIMARY = Path("output/intermediate/05_primary_reviewed.jsonl")
INTER_CHALLENGED = Path("output/intermediate/06_challenged.jsonl")
INTER_REBUTTED = Path("output/intermediate/07_rebutted.jsonl")

def load_screened_tokens() -> List[Dict[str, Any]]:
    """Load screened tokens from Step 4."""
    log.info("Loading screened tokens from %s", INTER_SCREENED)
    tokens = read_jsonl(INTER_SCREENED)
    log.info("Loaded %d tokens", len(tokens))
    return tokens

def save_primary_reviewed(records: List[Dict[str, Any]]) -> None:
    """Save primary review results."""
    log.info("Saving %d records to %s", len(records), INTER_PRIMARY)
    write_jsonl(INTER_PRIMARY, records)
    log.info("Primary review complete")

def save_challenged(records: List[Dict[str, Any]]) -> None:
    """Save challenge review results."""
    log.info("Saving %d records to %s", len(records), INTER_CHALLENGED)
    write_jsonl(INTER_CHALLENGED, records)
    log.info("Challenge review complete")

def save_rebutted(records: List[Dict[str, Any]]) -> None:
    """Save rebuttal review results."""
    log.info("Saving %d records to %s", len(records), INTER_REBUTTED)
    write_jsonl(INTER_REBUTTED, records)
    log.info("Rebuttal review complete")

def print_instructions():
    """Print instructions for manual AI review execution."""
    log.info("=" * 60)
    log.info("AI REVIEW EXECUTION INSTRUCTIONS")
    log.info("=" * 60)
    log.info("")
    log.info("This script prepares the data for AI review but cannot execute")
    log.info("the LLM judgments directly. The AI review must be performed by")
    log.info("the Claude Code session using the agent specifications in:")
    log.info("  .claude/agents/saas-title-judge.md")
    log.info("  .claude/agents/challenge-reviewer.md")
    log.info("  .claude/agents/rebuttal-reviewer.md")
    log.info("")
    log.info("Expected workflow:")
    log.info("  1. Load screened tokens from: %s", INTER_SCREENED)
    log.info("  2. Execute saas-title-judge agent → %s", INTER_PRIMARY)
    log.info("  3. Execute challenge-reviewer agent → %s", INTER_CHALLENGED)
    log.info("  4. Execute rebuttal-reviewer agent → %s", INTER_REBUTTED)
    log.info("  5. Run: python src/pipeline.py --phase consensus")
    log.info("")

def main():
    """Main entry point."""
    print_instructions()

    # Check if input exists
    if not INTER_SCREENED.exists():
        log.error("Input file not found: %s", INTER_SCREENED)
        log.error("Please run: python src/pipeline.py --phase prep")
        sys.exit(1)

    # Load tokens to verify
    tokens = load_screened_tokens()
    passed_tokens = [t for t in tokens if t.get("screen_result") == "pass"]
    log.info("  %d tokens passed screening", len(passed_tokens))

    log.info("")
    log.info("Ready for AI review. Please use the Claude Code session")
    log.info("to execute the agent specifications in .claude/agents/")
    log.info("")

if __name__ == "__main__":
    main()
