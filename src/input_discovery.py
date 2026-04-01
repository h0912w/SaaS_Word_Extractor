"""
Step 1 — Input file discovery.
Scans INPUT_DIR for supported file types and records metadata.
LLM agents (input-scope-checker-a/b/c + input-consensus-coordinator)
review the discovered list via a separate QA pass; this module only
performs the script-side discovery.
"""

import os
from pathlib import Path
from typing import Any

from config import INPUT_DIR, INTER_DISCOVERED, PIPELINE_VERSION
from utils import get_logger, write_json, read_json

log = get_logger("input_discovery")

SUPPORTED_EXTENSIONS = {".txt", ".jsonl", ".zst", ".csv"}


def discover_input_files(input_dir: Path = INPUT_DIR) -> list[dict]:
    """
    Walk input_dir and return a list of file descriptor dicts.
    Each dict contains: path, size_bytes, extension, status.
    """
    if not input_dir.exists():
        log.warning("Input directory does not exist: %s", input_dir)
        return []

    files = []
    for entry in sorted(input_dir.iterdir()):
        if not entry.is_file():
            continue

        # .txt.zst is a compound extension — treat specially
        name = entry.name
        if name.endswith(".txt.zst"):
            ext = ".txt.zst"
            supported = True
        else:
            ext = entry.suffix.lower()
            supported = ext in SUPPORTED_EXTENSIONS

        descriptor: dict[str, Any] = {
            "path": str(entry),
            "filename": name,
            "extension": ext,
            "size_bytes": entry.stat().st_size,
            "supported": supported,
            "status": "DISCOVERED",
            "pipeline_version": PIPELINE_VERSION,
        }
        files.append(descriptor)

        if supported:
            log.info("Discovered: %s  (%s bytes)", name, descriptor["size_bytes"])
        else:
            log.warning("Unsupported format (will skip): %s", name)

    log.info("Total discovered: %d file(s), %d supported",
             len(files), sum(1 for f in files if f["supported"]))
    return files


def run(resume: bool = False) -> list[dict]:
    """
    Run step 1.  If resume=True and the intermediate file already exists,
    return the cached result without re-scanning.
    """
    if resume and INTER_DISCOVERED.exists():
        log.info("Resuming from %s", INTER_DISCOVERED)
        data = read_json(INTER_DISCOVERED)
        return data["files"]

    files = discover_input_files()

    if not files:
        log.error("No files found in %s. Aborting.", INPUT_DIR)
        raise FileNotFoundError(f"No input files in {INPUT_DIR}")

    supported = [f for f in files if f["supported"]]
    if not supported:
        log.error("No supported files found. Supported: .txt .jsonl .txt.zst .csv")
        raise ValueError("No supported input files")

    write_json(INTER_DISCOVERED, {
        "total": len(files),
        "supported": len(supported),
        "files": files,
    })
    log.info("Saved discovery manifest → %s", INTER_DISCOVERED)
    return files
