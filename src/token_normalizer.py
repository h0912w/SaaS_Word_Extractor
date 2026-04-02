"""
Step 3 — Token normalization + word extraction.

Input entries are Wikipedia article titles (e.g. forge_welding, pulse_(band)).
This module:
  1. Strips wiki suffixes  (_(band), _(disambiguation), …)
  2. Lowercases
  3. Splits on underscores → extracts individual component words
  4. Strips boundary punctuation from each component
  5. Globally deduplicates by normalized_word
  6. Flags multi-word entries for auditor review

Result: one JSONL record per unique normalized single word.
"""

import re
from pathlib import Path

from config import INTER_NORMALIZED, PIPELINE_VERSION
from utils import get_logger, append_jsonl, read_jsonl

log = get_logger("token_normalizer")

# Wiki suffix: _(band), _(disambiguation), [music], etc.
WIKI_SUFFIX_RE = re.compile(r"[_\s]*[\(\[]\s*[a-z][^\)\]]*[\)\]]$", re.IGNORECASE)

# Control characters
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff]")

# Boundary punctuation (expanded to include common leading punctuation)
TRAILING_PUNCT_RE = re.compile(r"[.,;:!?\"'\)\]\}]+$")
LEADING_PUNCT_RE = re.compile(r"^[\"'\(\[\{!@#$%^&*+\-=?\\|`~]+")


# ---------------------------------------------------------------------------
# Core normalization (single string → single string)
# ---------------------------------------------------------------------------

def normalize_raw(raw: str) -> tuple[str, list[str]]:
    """
    Apply deterministic string transforms to a raw line.
    Returns (normalized_string, list_of_transforms_applied).
    Does NOT split on underscores yet.
    """
    transforms = []
    token = raw

    s = token.strip()
    if s != token:
        transforms.append("strip_whitespace")
    token = s

    c = CONTROL_RE.sub("", token)
    if c != token:
        transforms.append("remove_control_chars")
    token = c

    lo = token.lower()
    if lo != token:
        transforms.append("lowercase")
    token = lo

    ws = WIKI_SUFFIX_RE.sub("", token).strip()
    if ws != token:
        transforms.append("strip_wiki_suffix")
    token = ws

    lp = LEADING_PUNCT_RE.sub("", token).strip()
    tp = TRAILING_PUNCT_RE.sub("", lp).strip()
    if tp != token:
        transforms.append("strip_boundary_punct")
    token = tp

    col = re.sub(r"\s+", " ", token).strip()
    if col != token:
        transforms.append("collapse_whitespace")
    token = col

    return token, transforms


# ---------------------------------------------------------------------------
# Underscore splitting → list of component words
# ---------------------------------------------------------------------------

def split_to_words(normalized: str) -> list[str]:
    """
    Split an underscore-delimited Wikipedia title into component words.
    Each component has boundary punctuation stripped again.
    Empty parts are discarded.

    Examples:
      "forge_welding"   → ["forge", "welding"]
      "pulse"           → ["pulse"]
      "nexus"           → ["nexus"]
      ""                → []
    """
    if not normalized:
        return []

    parts = normalized.split("_")
    words = []
    for part in parts:
        part = LEADING_PUNCT_RE.sub("", part).strip()
        part = TRAILING_PUNCT_RE.sub("", part).strip()
        if part:
            words.append(part)

    return words if words else []


# ---------------------------------------------------------------------------
# Step runner
# ---------------------------------------------------------------------------

def run(loaded_records: list[dict], resume: bool = False) -> list[dict]:
    """
    Step 3: normalize every loaded token, split on underscores,
    deduplicate globally, and write to INTER_NORMALIZED.

    Returns a list of unique-word records.
    """
    if resume and INTER_NORMALIZED.exists():
        log.info("Resuming from %s", INTER_NORMALIZED)
        return read_jsonl(INTER_NORMALIZED)

    if INTER_NORMALIZED.exists():
        INTER_NORMALIZED.unlink()

    seen_words: set[str] = set()
    records: list[dict] = []
    skipped_dupe = 0
    skipped_empty = 0

    for rec in loaded_records:
        normalized_line, transforms = normalize_raw(rec["raw_token"])

        component_words = split_to_words(normalized_line)

        if not component_words:
            skipped_empty += 1
            continue

        multi = len(component_words) > 1

        for word in component_words:
            if word in seen_words:
                skipped_dupe += 1
                continue
            seen_words.add(word)

            word_transforms = list(transforms)
            if multi:
                word_transforms.append("split_underscore")

            new_rec = {
                **rec,
                "normalized_word": word,
                "transformations": word_transforms,
                "normalization_flag": "split_from_phrase" if multi else None,
                "status": "NORMALIZED",
            }
            append_jsonl(INTER_NORMALIZED, new_rec)
            records.append(new_rec)

    log.info(
        "Normalized: %d unique words  (dupes skipped: %d, empty skipped: %d) → %s",
        len(records), skipped_dupe, skipped_empty, INTER_NORMALIZED,
    )
    return records
