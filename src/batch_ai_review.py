#!/usr/bin/env python3
"""
Batch AI Review Coordinator
============================
Helper script to coordinate batch AI review for large token sets.
This creates batch files that can be processed by the Claude Code session.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from utils import get_logger, read_jsonl, write_jsonl

log = get_logger("batch_ai_review")

INTER_SCREENED = Path("output/intermediate/04_screened_tokens.jsonl")
BATCH_DIR = Path("output/intermediate/batches")
BATCH_SIZE = 100  # Process 100 tokens per batch

def create_batches():
    """Create batch files for AI review."""
    log.info("Creating batch files for AI review")

    # Load screened tokens
    tokens = read_jsonl(INTER_SCREENED)
    passed = [t for t in tokens if t.get("screen_result") == "pass"]
    log.info("Found %d tokens needing AI review", len(passed))

    # Create batch directory
    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    # Split into batches
    batches = []
    for i in range(0, len(passed), BATCH_SIZE):
        batch = passed[i:i+BATCH_SIZE]
        batch_file = BATCH_DIR / f"batch_{i//BATCH_SIZE:03d}.jsonl"
        write_jsonl(batch_file, batch)
        batches.append({
            "batch_num": i//BATCH_SIZE,
            "file": str(batch_file),
            "count": len(batch)
        })
        log.info("Created batch %d: %s (%d tokens)", i//BATCH_SIZE, batch_file.name, len(batch))

    # Save batch manifest
    manifest_file = BATCH_DIR / "manifest.json"
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(batches, f, indent=2)

    log.info("Created %d batches", len(batches))
    log.info("Manifest saved to: %s", manifest_file)
    log.info("")
    log.info("Next steps:")
    log.info("  1. Process each batch through AI review")
    log.info("  2. Save results to output/intermediate/batches/primary_batch_XXX.jsonl")
    log.info("  3. Run: python src/batch_ai_review.py --merge primary")
    log.info("")

def merge_results(phase: str):
    """Merge batch results into single file."""
    log.info("Merging %s batch results", phase)

    batch_files = sorted(BATCH_DIR.glob(f"{phase}_batch_*.jsonl"))
    if not batch_files:
        log.error("No %s batch files found in %s", phase, BATCH_DIR)
        sys.exit(1)

    all_records = []
    for bf in batch_files:
        records = read_jsonl(bf)
        all_records.extend(records)
        log.info("Loaded %d records from %s", len(records), bf.name)

    # Save merged file
    output_file = Path(f"output/intermediate/0{5 if phase == 'primary' else 6 if phase == 'challenged' else 7}_{phase}_reviewed.jsonl")
    write_jsonl(output_file, all_records)
    log.info("Merged %d records to %s", len(all_records), output_file)

def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Batch AI Review Coordinator")
    parser.add_argument("--create", action="store_true", help="Create batch files")
    parser.add_argument("--merge", metavar="PHASE", help="Merge batch results (primary/challenged/rebutted)")
    args = parser.parse_args()

    if args.create:
        create_batches()
    elif args.merge:
        merge_results(args.merge)
    else:
        print("Usage: python src/batch_ai_review.py --create")
        print("       python src/batch_ai_review.py --merge primary")
        sys.exit(1)

if __name__ == "__main__":
    main()
