"""
Step 2 — File loading and decompression.
Reads each supported input file as a stream of (word, source_file, source_line)
tuples and writes them to the intermediate JSONL.

Supports:
  *.txt       — plain text, one token per line
  *.jsonl     — each line is JSON; first string field is used as the token
  *.txt.zst   — Zstandard-compressed plain text
  *.csv       — single-column CSV (first column used)
"""

import csv
import io
import json
from pathlib import Path
from typing import Iterator

from config import INTER_LOADED, PIPELINE_VERSION
from utils import get_logger, append_jsonl, read_jsonl
from input_noise_filter import is_noise_token

log = get_logger("input_loader")


# ---------------------------------------------------------------------------
# Per-format line iterators
# ---------------------------------------------------------------------------

def _iter_txt(path: Path) -> Iterator[tuple[str, int]]:
    with open(path, encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, start=1):
            yield line.rstrip("\n"), lineno


def _iter_zst(path: Path) -> Iterator[tuple[str, int]]:
    try:
        import zstandard as zstd
    except ImportError:
        raise ImportError(
            "zstandard package is required for .zst files.  "
            "Run: pip install zstandard"
        )
    with open(path, "rb") as fh:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(fh) as reader:
            text_reader = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text_reader, start=1):
                yield line.rstrip("\n"), lineno


def _iter_jsonl(path: Path) -> Iterator[tuple[str, int]]:
    with open(path, encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                yield line, lineno  # treat raw line as token
                continue
            if isinstance(obj, str):
                yield obj, lineno
            elif isinstance(obj, dict):
                # Use first string value found
                for v in obj.values():
                    if isinstance(v, str):
                        yield v, lineno
                        break
            elif isinstance(obj, list) and obj and isinstance(obj[0], str):
                yield obj[0], lineno


def _iter_csv(path: Path) -> Iterator[tuple[str, int]]:
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        for lineno, row in enumerate(reader, start=1):
            if row:
                yield row[0], lineno


def _iter_file(path: Path) -> Iterator[tuple[str, int]]:
    name = path.name
    if name.endswith(".txt.zst"):
        return _iter_zst(path)
    ext = path.suffix.lower()
    if ext == ".txt":
        return _iter_txt(path)
    if ext == ".jsonl":
        return _iter_jsonl(path)
    if ext == ".csv":
        return _iter_csv(path)
    raise ValueError(f"Unsupported file type: {ext}")


# ---------------------------------------------------------------------------
# Step runner
# ---------------------------------------------------------------------------

def count_lines(path: Path) -> int:
    """Count total lines in a file.

    Args:
        path: Path to file

    Returns:
        Number of lines
    """
    count = 0
    name = path.name

    if name.endswith(".txt.zst"):
        import zstandard as zstd
        with open(path, "rb") as fh:
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(fh) as reader:
                import io
                text_reader = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
                for _ in text_reader:
                    count += 1
    else:
        with open(path, encoding="utf-8", errors="replace") as f:
            for _ in f:
                count += 1

    return count


def run(
    file_descriptors: list[dict],
    resume: bool = False,
    start_line: int = 1,
    max_lines: int = 0,
) -> int:
    """
    Load all supported input files, write a LOADED intermediate JSONL,
    and return the last line number processed.
    max_lines: stop loading after this many lines total (0 = no limit).
    start_line: start from this line number (1-based).
    Returns: last line number processed, or 0 if nothing processed.
    """
    if resume and INTER_LOADED.exists():
        log.info("Resuming from %s", INTER_LOADED)
        records = read_jsonl(INTER_LOADED)
        return len(records) if records else 0

    # Clear file in case we're re-running (handle file lock gracefully)
    if INTER_LOADED.exists():
        try:
            INTER_LOADED.unlink()
        except PermissionError:
            # File is locked by another process, just append mode will work
            log.info("File exists and locked, will append new records")

    # Also try to clear the file content if locked
    try:
        if INTER_LOADED.exists():
            # Try to truncate the file
            with open(INTER_LOADED, 'w') as f:
                pass  # Just truncate
    except PermissionError:
        log.info("Could not truncate file, continuing with append mode")

    supported = [f for f in file_descriptors if f.get("supported")]
    if not supported:
        raise ValueError("No supported files to load")

    records = []
    total_lines = 0
    end_line = 0

    for fd in supported:
        path = Path(fd["path"])
        filename = fd["filename"]
        log.info("Loading: %s (starting from line %d)", filename, start_line)
        file_count = 0

        try:
            total_read = 0
            noise_filtered = 0

            for raw_token, lineno in _iter_file(path):
                if lineno < start_line:
                    continue
                if max_lines and file_count >= max_lines:
                    log.info("  max_lines=%d reached, stopping early", max_lines)
                    break

                # 입력 노이즈 필터링 (명백한 노이즈는 사전 제외)
                is_noise, noise_reason = is_noise_token(raw_token)
                total_read += 1

                if is_noise:
                    noise_filtered += 1
                    continue

                record = {
                    "raw_token": raw_token,
                    "source_file": filename,
                    "source_line": lineno,
                    "status": "LOADED",
                    "pipeline_version": PIPELINE_VERSION,
                }
                append_jsonl(INTER_LOADED, record)
                records.append(record)
                file_count += 1
                end_line = lineno  # Track last line processed

            # 노이즈 필터링 통계 로그
            if total_read > 0:
                noise_rate = 100 * noise_filtered / total_read
                log.info("  → Read %d tokens, filtered %d noise (%.1f%%), loaded %d tokens",
                         total_read, noise_filtered, noise_rate, file_count)

        except Exception as exc:
            log.error("Failed to load %s: %s (skipping)", filename, exc)
            continue

        total_lines += file_count
        log.info("  → %d lines loaded from %s (lines %d-%d)",
                file_count, filename, start_line, end_line)

    log.info("Total loaded: %d tokens → %s", total_lines, INTER_LOADED)
    return end_line
