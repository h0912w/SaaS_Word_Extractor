#!/usr/bin/env python3
"""
Batch Processor for SaaS Word Extractor
========================================
Processes input data in batches of 100K words with manual continuation.
Each batch produces independently named output files (no auto-merge).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    INTER_SCREENED, INTER_NORMALIZED, INTER_LOADED,
    OUTPUT_DIR, BATCH_SIZE, PIPELINE_VERSION
)
from progress_tracker import ProgressTracker
from utils import get_logger, iter_jsonl, write_jsonl
import rule_screener

log = get_logger("batch_processor")


class BatchProcessor:
    """Process input data in batches with progress tracking."""

    def __init__(self, input_file: Path, progress_file: Optional[Path] = None):
        """Initialize batch processor.

        Args:
            input_file: Path to input file (e.g., all_words_deduped.txt.zst)
            progress_file: Path to progress file
        """
        self.input_file = input_file
        self.tracker = ProgressTracker(progress_file)

        # Count total lines in input file
        self.total_words = self._count_lines()
        self.tracker.set_total_words(self.total_words)

        log.info(f"Total words in input file: {self.total_words:,}")

    def _count_lines(self) -> int:
        """Count total lines in input file."""
        count = 0
        try:
            # Try to get count from intermediate file if available
            if INTER_LOADED.exists():
                for _ in iter_jsonl(INTER_LOADED):
                    count += 1
                return count
        except Exception as e:
            log.warning(f"Could not count from intermediate file: {e}")

        # Default to known count
        return 28108856

    def get_next_batch(self) -> Optional[Dict[str, Any]]:
        """Get information about the next batch to process.

        Returns:
            Dict with batch info or None if all batches are completed
        """
        batch_range = self.tracker.get_next_chunk_range(self.total_words, BATCH_SIZE)

        if batch_range is None:
            log.info("All batches have been completed!")
            return None

        batch_number, start_line, end_line = batch_range

        # Determine output directory for this batch
        output_dir = OUTPUT_DIR / f"batch_{batch_number:03d}"
        output_dir.mkdir(parents=True, exist_ok=True)

        return {
            "batch_number": batch_number,
            "start_line": start_line,
            "end_line": end_line,
            "word_count": end_line - start_line + 1,
            "output_dir": str(output_dir),
            "output_files": {
                "screened": str(output_dir / "intermediate" / "04_screened_tokens.jsonl"),
                "primary": str(output_dir / "intermediate" / "05_primary_reviewed.jsonl"),
                "challenged": str(output_dir / "intermediate" / "06_challenged.jsonl"),
                "rebutted": str(output_dir / "intermediate" / "07_rebutted.jsonl"),
                "consensus": str(output_dir / "intermediate" / "08_consensus.jsonl"),
                "saas_words": str(output_dir / f"saas_words_batch_{batch_number:03d}.jsonl"),
                "rejected_words": str(output_dir / f"rejected_words_batch_{batch_number:03d}.jsonl"),
                "run_summary": str(output_dir / f"run_summary_batch_{batch_number:03d}.json"),
            }
        }

    def process_batch(self, batch_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single batch.

        Args:
            batch_info: Batch information from get_next_batch()

        Returns:
            Processing statistics
        """
        batch_number = batch_info["batch_number"]
        start_line = batch_info["start_line"]
        end_line = batch_info["end_line"]
        output_dir = batch_info["output_dir"]

        log.info("=" * 60)
        log.info(f"PROCESSING BATCH #{batch_number:03d}")
        log.info("=" * 60)
        log.info(f"Lines: {start_line:,} - {end_line:,}")
        log.info(f"Word count: {batch_info['word_count']:,}")
        log.info(f"Output directory: {output_dir}")

        # Mark batch as started
        self.tracker.start_chunk(batch_number, start_line, end_line)

        # Read and process input file for this batch
        processed_count = 0
        screened_count = 0

        # Create intermediate directory
        intermediate_dir = output_dir / "intermediate"
        intermediate_dir.mkdir(parents=True, exist_ok=True)

        screened_file = batch_info["output_files"]["screened"]

        # Read from normalized tokens (streaming)
        if INTER_NORMALIZED.exists():
            source_file = INTER_NORMALIZED
        else:
            log.error(f"Normalized tokens file not found: {INTER_NORMALIZED}")
            log.error("Please run pipeline prep phase first:")
            log.error("  python src/pipeline.py --phase prep")
            return {"success": False, "error": "Input file not found"}

        with open(screened_file, 'w', encoding='utf-8') as outfile:
            for line_num, record in enumerate(iter_jsonl(source_file), 1):
                if line_num < start_line:
                    continue
                if line_num > end_line:
                    break

                processed_count += 1

                # Progress logging every 10k records
                if processed_count % 10000 == 0:
                    log.info(f"Processed {processed_count:,} tokens...")

                # Apply rule screening
                decision, reason = rule_screener.screen_token(record.get("normalized_word", ""))
                record["screen_result"] = decision
                record["screen_reason"] = reason or ""

                if decision == "pass":
                    screened_count += 1

                # Write to output
                outfile.write(json.dumps(record, ensure_ascii=False) + "\n")

        log.info(f"Batch processing complete: {processed_count:,} tokens processed, {screened_count:,} passed screening")

        # Mark batch as completed
        self.tracker.complete_chunk(
            chunk_number=batch_number,
            words_processed=processed_count,
            start_line=start_line,
            end_line=end_line,
            output_dir=str(output_dir)
        )

        return {
            "success": True,
            "batch_number": batch_number,
            "processed_count": processed_count,
            "screened_count": screened_count
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current processing status."""
        return self.tracker.get_status()


def main():
    """Main entry point for batch processor."""
    parser = argparse.ArgumentParser(
        description="Process SaaS word extraction in batches of 100K words"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="input/all_words_deduped.txt.zst",
        help="Input file path"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current processing status"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset progress and start over"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show next batch information without processing"
    )

    args = parser.parse_args()

    processor = BatchProcessor(Path(args.input))

    if args.reset:
        processor.tracker.reset()
        log.info("Progress has been reset. Starting from batch 1.")
        return

    if args.status:
        status = processor.get_status()
        print(json.dumps(status, indent=2))
        return

    if args.info:
        batch = processor.get_next_batch()
        if batch:
            print(json.dumps(batch, indent=2))
        else:
            print("All batches have been completed!")
        return

    # Process next batch
    batch = processor.get_next_batch()
    if batch is None:
        log.info("All batches have been completed!")
        return

    log.info("Ready to process next batch:")
    log.info(f"  Batch #{batch['batch_number']:03d}")
    log.info(f"  Lines: {batch['start_line']:,} - {batch['end_line']:,}")
    log.info(f"  Word count: {batch['word_count']:,}")
    log.info("")
    log.info("To process this batch, run:")
    log.info(f"  python src/batch_processor.py --input {args.input}")

    # For now, require explicit confirmation (could add --yes flag later)
    response = input("\nProcess this batch now? (y/N): ")
    if response.lower() == 'y':
        result = processor.process_batch(batch)
        if result["success"]:
            log.info(f"Batch #{result['batch_number']:03d} completed successfully!")
            log.info(f"Processed {result['processed_count']:,} tokens")
            log.info(f"Screened {result['screened_count']:,} tokens")
            log.info("")
            log.info("To continue with the next batch, run:")
            log.info(f"  python src/batch_processor.py --input {args.input}")
        else:
            log.error(f"Batch processing failed: {result.get('error')}")
    else:
        log.info("Batch processing cancelled.")


if __name__ == "__main__":
    main()
