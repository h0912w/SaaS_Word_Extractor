"""
Shared utilities: logging setup, JSONL I/O helpers, JSON parsing with fallback.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Iterator


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                              datefmt="%H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, records: list[dict], mode: str = "w") -> None:
    """Write a list of dicts to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, mode, encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, record: dict) -> None:
    """Append a single record to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    """Read all records from a JSONL file."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def iter_jsonl(path: Path) -> Iterator[dict]:
    """Iterate over records in a JSONL file (streaming)."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    pass


def write_json(path: Path, data: Any) -> None:
    """Write a dict/list to a pretty-printed JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Robust JSON extraction from LLM response text
# ---------------------------------------------------------------------------

def extract_json(text: str) -> Any:
    """
    Try to parse JSON from LLM response text.
    Handles code-fenced JSON blocks and bare JSON objects/arrays.
    Raises ValueError if no valid JSON found.
    """
    # 1. Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Extract from ```json ... ``` block
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Find first { ... } or [ ... ] span
    for opener, closer in [('{', '}'), ('[', ']')]:
        start = text.find(opener)
        if start == -1:
            continue
        # Walk backwards from end to find matching closer
        end = text.rfind(closer)
        if end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No valid JSON found in response:\n{text[:500]}")


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

def with_retry(fn, attempts: int = 3, base_delay: float = 2.0, logger=None):
    """
    Call fn() with exponential-backoff retry on any exception.
    Returns the result on success, re-raises on final failure.
    """
    log = logger or get_logger("retry")
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == attempts:
                log.error("All %d attempts failed: %s", attempts, exc)
                raise
            delay = base_delay * (2 ** (attempt - 1))
            log.warning("Attempt %d/%d failed (%s). Retrying in %.1fs …",
                        attempt, attempts, exc, delay)
            time.sleep(delay)


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------

def batched(items: list, size: int) -> Iterator[list]:
    """Yield successive slices of `items` each of length `size`."""
    for i in range(0, len(items), size):
        yield items[i:i + size]
