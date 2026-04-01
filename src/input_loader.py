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

def run(file_descriptors: list[dict], resume: bool = False) -> list[dict]:
    """
    Load all supported input files, write a LOADED intermediate JSONL,
    and return the list of token records.
    If resume=True and the intermediate file exists, skip loading.
    """
    if resume and INTER_LOADED.exists():
        log.info("Resuming from %s", INTER_LOADED)
        return read_jsonl(INTER_LOADED)

    # Clear file in case we're re-running
    if INTER_LOADED.exists():
        INTER_LOADED.unlink()

    supported = [f for f in file_descriptors if f.get("supported")]
    if not supported:
        raise ValueError("No supported files to load")

    records = []
    total_lines = 0

    for fd in supported:
        path = Path(fd["path"])
        filename = fd["filename"]
        log.info("Loading: %s", filename)
        file_count = 0

        try:
            for raw_token, lineno in _iter_file(path):
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
        except Exception as exc:
            log.error("Failed to load %s: %s (skipping)", filename, exc)
            continue

        total_lines += file_count
        log.info("  → %d lines loaded from %s", file_count, filename)

    log.info("Total loaded: %d tokens → %s", total_lines, INTER_LOADED)
    return records
