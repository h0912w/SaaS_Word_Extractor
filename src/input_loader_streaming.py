#!/usr/bin/env python3
"""
Step 1-2: Input Discovery and Loading (Memory-Efficient Pipeline)
Streams from input files directly to loaded tokens, with chunking.
"""

import zstandard
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INTER_LOADED, PIPELINE_VERSION
from utils import get_logger, append_jsonl

log = get_logger("input_loader_streaming")


def discover_and_load(max_lines: int = 0):
    """
    Discover and load input files in streaming mode.
    Returns the path to the loaded file for next stage.
    """
    log.info("=" * 60)
    log.info("INPUT LOADING (STREAMING MODE)")
    log.info("=" * 60)

    base_dir = Path("input")
    input_files = list(base_dir.glob("*.txt.zst")) + list(base_dir.glob("*.txt")) + list(base_dir.glob("*.jsonl"))

    if not input_files:
        log.error("No input files found in %s", base_dir)
        sys.exit(1)

    log.info("Found %d input file(s)", len(input_files))

    # Clear output file
    if INTER_LOADED.exists():
        INTER_LOADED.unlink()

    total_loaded = 0

    for input_path in input_files:
        filename = input_path.name
        log.info("Loading: %s", filename)

        try:
            if filename.endswith(".zst"):
                # Decompressed streaming
                with open(input_path, "rb") as f:
                    dctx = zstandard.ZstdDecompressor()
                    reader = zstandard.ZstdDecompressor(f).readall().decode('utf-8', errors='replace').split('\n')
            else:
                with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                    reader = f

            for line_num, line in enumerate(reader, 1):
                if not line.strip():
                    continue

                record = {
                    "raw_token": line.strip(),
                    "source_file": filename,
                    "source_line": line_num,
                    "status": "LOADED",
                    "pipeline_version": PIPELINE_VERSION,
                }
                append_jsonl(INTER_LOADED, record)
                total_loaded += 1

                if max_lines and total_loaded >= max_lines:
                    log.info("  max_lines=%d reached, stopping early", max_lines)
                    break

        except Exception as exc:
            log.error("Failed to load %s: %s (skipping)", filename, exc)
            continue

    log.info("Total tokens loaded: %d → %s", total_loaded, INTER_LOADED)
    return INTER_LOADED


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-lines", type=int, default=0, help="Max lines to load (0=unlimited)")
    args = parser.parse_args()

    discover_and_load(args.max_lines)
