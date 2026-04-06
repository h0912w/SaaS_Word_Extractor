#!/usr/bin/env python3
"""
Progress Tracker for Batched Processing
=========================================
Tracks processing progress across multiple 100K-word batches.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from config import PROGRESS_DIR


class ProgressTracker:
    """Track processing progress for batched processing."""

    def __init__(self, progress_file: Optional[Path] = None):
        """Initialize progress tracker.

        Args:
            progress_file: Path to progress file. Defaults to PROGRESS_DIR/batch_progress.json
        """
        if progress_file is None:
            PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
            progress_file = PROGRESS_DIR / "batch_progress.json"

        self.progress_file = progress_file
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load progress from file."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Default progress structure
        return {
            "last_processed_line": 0,
            "last_batch_number": 0,
            "total_processed": 0,
            "total_words": 0,
            "next_start_line": 1,
            "status": "not_started",
            "batches_completed": [],
            "last_updated": None
        }

    def save(self):
        """Save progress to file."""
        self.data["last_updated"] = datetime.utcnow().isoformat() + "Z"
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_next_chunk_range(self, total_words: int, chunk_size: int = 100000) -> Optional[tuple[int, int, int]]:
        """Get the next batch range to process.

        Args:
            total_words: Total number of words to process
            chunk_size: Size of each batch (default: 100K)

        Returns:
            Tuple of (batch_number, start_line, end_line) or None if all batches are done
        """
        if self.data["status"] == "completed" or self.data["next_start_line"] > total_words:
            return None

        batch_number = self.data["last_batch_number"] + 1
        start_line = self.data["next_start_line"]
        end_line = min(start_line + chunk_size - 1, total_words)

        return (batch_number, start_line, end_line)

    def start_chunk(self, batch_number: int, start_line: int, end_line: int):
        """Mark a batch as started."""
        self.data["current_batch"] = {
            "batch_number": batch_number,
            "start_line": start_line,
            "end_line": end_line,
            "status": "in_progress",
            "started_at": datetime.utcnow().isoformat() + "Z"
        }
        self.save()

    def complete_chunk(self, batch_number: int, words_processed: int,
                      start_line: int, end_line: int, output_dir: str):
        """Mark a batch as completed."""
        batch_info = {
            "batch_number": batch_number,
            "start_line": start_line,
            "end_line": end_line,
            "words_processed": words_processed,
            "output_dir": output_dir,
            "completed_at": datetime.utcnow().isoformat() + "Z"
        }

        self.data["batches_completed"].append(batch_info)
        self.data["last_batch_number"] = batch_number
        self.data["last_processed_line"] = end_line
        self.data["total_processed"] += words_processed
        self.data["next_start_line"] = end_line + 1

        # Remove current batch marker
        if "current_batch" in self.data:
            del self.data["current_batch"]

        # Check if all batches are completed
        if self.data["next_start_line"] > self.data.get("total_words", 0):
            self.data["status"] = "completed"
        else:
            self.data["status"] = "ready_for_next_batch"

        self.save()

    def set_total_words(self, total_words: int):
        """Set the total number of words to process."""
        self.data["total_words"] = total_words
        self.save()

    def get_status(self) -> Dict[str, Any]:
        """Get current progress status."""
        return {
            "batch_number": self.data.get("current_batch", {}).get("batch_number", self.data["last_batch_number"]),
            "last_processed_line": self.data["last_processed_line"],
            "total_processed": self.data["total_processed"],
            "total_words": self.data["total_words"],
            "next_start_line": self.data["next_start_line"],
            "status": self.data["status"],
            "batches_completed": len(self.data["batches_completed"]),
            "progress_percent": (self.data["total_processed"] / self.data["total_words"] * 100) if self.data["total_words"] > 0 else 0
        }

    def reset(self):
        """Reset progress to start over."""
        self.data = {
            "last_processed_line": 0,
            "last_batch_number": 0,
            "total_processed": 0,
            "total_words": self.data.get("total_words", 0),
            "next_start_line": 1,
            "status": "not_started",
            "batches_completed": [],
            "last_updated": None
        }
        self.save()


def main():
    """Test progress tracker."""
    tracker = ProgressTracker()
    tracker.set_total_words(28108856)

    print("Initial Status:")
    print(json.dumps(tracker.get_status(), indent=2))

    # Simulate processing first batch
    batch_range = tracker.get_next_chunk_range(28108856)
    if batch_range:
        batch_num, start, end = batch_range
        print(f"\nNext batch: #{batch_num}, lines {start}-{end}")

        tracker.start_chunk(batch_num, start, end)
        tracker.complete_chunk(batch_num, 100000, start, end, "output/batch_001")

        print("\nAfter completing batch 1:")
        print(json.dumps(tracker.get_status(), indent=2))

        # Get next batch
        batch_range = tracker.get_next_chunk_range(28108856)
        if batch_range:
            batch_num, start, end = batch_range
            print(f"\nNext batch: #{batch_num}, lines {start}-{end}")


if __name__ == "__main__":
    main()
