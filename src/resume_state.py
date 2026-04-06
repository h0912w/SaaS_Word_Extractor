#!/usr/bin/env python3
"""
Resume State Manager
=====================
Tracks processing progress across Claude Code restarts.

Usage:
    state = ResumeState()
    state.load()

    # Check if we can resume
    if state.can_resume():
        next_line = state.get_next_start_line()
        print(f"Resuming from line {next_line}")

    # Update state after processing
    state.mark_batch_completed(batch_number, start_line, end_line)
    state.save()
"""

import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from config import INPUT_DIR, OUTPUT_DIR


class ResumeState:
    """Manage resume state for batched processing."""

    def __init__(self, state_file: Optional[Path] = None):
        """Initialize resume state manager.

        Args:
            state_file: Path to state file. Defaults to output/progress/resume_state.json
        """
        if state_file is None:
            state_file = OUTPUT_DIR / "progress" / "resume_state.json"

        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.data: Dict[str, Any] = {}

    def load(self) -> bool:
        """Load state from file.

        Returns:
            True if state file exists and was loaded, False otherwise
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                return True
            except (json.JSONDecodeError, IOError):
                pass

        # Initialize empty state
        self.data = self._get_empty_state()
        return False

    def save(self):
        """Save state to file."""
        self.data["last_updated"] = datetime.utcnow().isoformat() + "Z"
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def _get_empty_state(self) -> Dict[str, Any]:
        """Get empty state structure."""
        return {
            "input_file": None,
            "input_file_size": 0,
            "input_file_hash": None,
            "total_lines": 0,
            "last_processed_line": 0,
            "next_start_line": 1,
            "batches_completed": [],
            "status": "not_started",
            "last_updated": None
        }

    def set_input_file(self, input_path: Path) -> bool:
        """Set input file and detect if changed.

        Args:
            input_path: Path to input file

        Returns:
            True if input file is new or changed, False if same as before
        """
        input_path = Path(input_path)

        # Get file info
        file_size = input_path.stat().st_size
        file_hash = self._compute_hash(input_path)

        # Check if file changed
        if self.data.get("input_file") == str(input_path):
            if self.data.get("input_file_size") == file_size:
                if self.data.get("input_file_hash") == file_hash:
                    return False  # Same file

        # New or changed file - reset state
        self.data = self._get_empty_state()
        self.data["input_file"] = str(input_path)
        self.data["input_file_size"] = file_size
        self.data["input_file_hash"] = file_hash
        return True

    def _compute_hash(self, path: Path, sample_size: int = 1024 * 1024) -> str:
        """Compute hash of file (first 1MB for speed).

        Args:
            path: File path
            sample_size: Number of bytes to hash

        Returns:
            Hexadecimal hash string
        """
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            data = f.read(sample_size)
            sha256.update(data)
        return sha256.hexdigest()

    def set_total_lines(self, total_lines: int):
        """Set total lines in input file."""
        self.data["total_lines"] = total_lines
        self.save()

    def get_next_start_line(self) -> int:
        """Get next line to start processing from."""
        return self.data.get("next_start_line", 1)

    def get_last_processed_line(self) -> int:
        """Get last line that was processed."""
        return self.data.get("last_processed_line", 0)

    def get_progress_percent(self) -> float:
        """Get progress percentage."""
        total = self.data.get("total_lines", 0)
        if total == 0:
            return 0.0
        last = self.data.get("last_processed_line", 0)
        return (last / total) * 100

    def mark_chunk_completed(self, batch_number: int, start_line: int, end_line: int,
                             words_processed: int, output_dir: str = None):
        """Mark a batch as completed.

        Args:
            batch_number: Batch number
            start_line: Start line (1-based)
            end_line: End line (1-based)
            words_processed: Number of words processed
            output_dir: Output directory path
        """
        batch_info = {
            "batch_number": batch_number,
            "start_line": start_line,
            "end_line": end_line,
            "words_processed": words_processed,
            "completed_at": datetime.utcnow().isoformat() + "Z"
        }
        if output_dir:
            batch_info["output_dir"] = output_dir

        self.data["batches_completed"].append(batch_info)
        self.data["last_processed_line"] = end_line
        self.data["next_start_line"] = end_line + 1

        # Check if completed
        if self.data["next_start_line"] > self.data.get("total_lines", 0):
            self.data["status"] = "completed"
        else:
            self.data["status"] = "ready_for_next_batch"

        self.save()

    def can_resume(self) -> bool:
        """Check if we can resume from previous state.

        Returns:
            True if resume is possible
        """
        return (
            self.data.get("status") in ["ready_for_next_batch", "processing"] and
            self.data.get("next_start_line", 0) > 1 and
            self.data.get("total_lines", 0) > 0
        )

    def is_completed(self) -> bool:
        """Check if processing is completed.

        Returns:
            True if all batches completed
        """
        return self.data.get("status") == "completed"

    def get_status(self) -> Dict[str, Any]:
        """Get current status summary."""
        return {
            "input_file": self.data.get("input_file"),
            "total_lines": self.data.get("total_lines", 0),
            "last_processed_line": self.data.get("last_processed_line", 0),
            "next_start_line": self.data.get("next_start_line", 1),
            "batches_completed": len(self.data.get("batches_completed", [])),
            "progress_percent": self.get_progress_percent(),
            "status": self.data.get("status", "not_started")
        }

    def reset(self):
        """Reset state to start over."""
        input_file = self.data.get("input_file")
        input_size = self.data.get("input_file_size", 0)
        input_hash = self.data.get("input_file_hash")
        total_lines = self.data.get("total_lines", 0)

        self.data = self._get_empty_state()
        if input_file:
            self.data["input_file"] = input_file
            self.data["input_file_size"] = input_size
            self.data["input_file_hash"] = input_hash
            self.data["total_lines"] = total_lines
        self.save()


def main():
    """Test resume state manager."""
    state = ResumeState()
    state.load()

    print("Current Status:")
    print(json.dumps(state.get_status(), indent=2))


if __name__ == "__main__":
    main()
