"""
Step 3 — Token normalization.
Applies lightweight, deterministic transformations so that downstream
stages work on clean, lowercase tokens.

Rules applied (in order):
  1. Strip leading/trailing whitespace
  2. Lowercase
  3. Remove zero-width / control characters (except ordinary whitespace)
  4. Collapse internal whitespace to single space
  5. Strip common wiki/encyclopedic suffixes like _(band), _(disambiguation)
  6. Strip trailing punctuation that is clearly not part of the word
  7. Record the transformation so auditors can verify it

This module does NOT make semantic decisions — it only applies deterministic
string transformations.  Borderline cases are preserved and flagged
so LLM auditors (normalization-auditor-a/b/c) can review them.
"""

import re
import unicodedata
from pathlib import Path

from config import INTER_NORMALIZED, PIPELINE_VERSION
from utils import get_logger, append_jsonl, read_jsonl

log = get_logger("token_normalizer")

# Patterns that indicate an encyclopedic/wiki artifact suffix
# Handles: " (band)", "_(disambiguation)", " [music]", etc.
WIKI_SUFFIX_RE = re.compile(r"[_\s]*[\(\[]\s*[a-z][^\)\]]*[\)\]]$", re.IGNORECASE)

# Control characters to strip (everything < 0x20 except tab/newline, plus surrogates)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff]")

# Trailing punctuation that is never part of a word token
TRAILING_PUNCT_RE = re.compile(r"[.,;:!?\"'\)\]\}]+$")
# Leading punctuation
LEADING_PUNCT_RE = re.compile(r"^[\"'\(\[\{]+")


def normalize_token(raw: str) -> dict:
    """
    Normalize a single raw token.
    Returns a dict with keys: normalized_word, transformations, flag.
    """
    transformations = []
    token = raw

    # 1. Strip outer whitespace
    stripped = token.strip()
    if stripped != token:
        transformations.append("strip_whitespace")
    token = stripped

    # 2. Remove control characters
    cleaned = CONTROL_RE.sub("", token)
    if cleaned != token:
        transformations.append("remove_control_chars")
    token = cleaned

    # 3. Lowercase
    lower = token.lower()
    if lower != token:
        transformations.append("lowercase")
    token = lower

    # 4. Strip wiki suffixes like _(band), (disambiguation)
    wiki_stripped = WIKI_SUFFIX_RE.sub("", token).strip()
    if wiki_stripped != token:
        transformations.append("strip_wiki_suffix")
    token = wiki_stripped

    # 5. Strip leading/trailing non-word punctuation
    lead_stripped = LEADING_PUNCT_RE.sub("", token).strip()
    trail_stripped = TRAILING_PUNCT_RE.sub("", lead_stripped).strip()
    if trail_stripped != token:
        transformations.append("strip_boundary_punct")
    token = trail_stripped

    # 6. Collapse internal whitespace
    collapsed = re.sub(r"\s+", " ", token).strip()
    if collapsed != token:
        transformations.append("collapse_whitespace")
    token = collapsed

    # Flag if result looks multi-token (contains space after normalization)
    flag = "multi_token" if " " in token else None

    return {
        "normalized_word": token,
        "transformations": transformations,
        "normalization_flag": flag,
    }


def run(loaded_records: list[dict], resume: bool = False) -> list[dict]:
    """
    Step 3: normalize every loaded token and write to INTER_NORMALIZED.
    If resume=True and the file exists, reload from cache.
    """
    if resume and INTER_NORMALIZED.exists():
        log.info("Resuming from %s", INTER_NORMALIZED)
        return read_jsonl(INTER_NORMALIZED)

    if INTER_NORMALIZED.exists():
        INTER_NORMALIZED.unlink()

    records = []
    for rec in loaded_records:
        norm = normalize_token(rec["raw_token"])
        updated = {
            **rec,
            **norm,
            "status": "NORMALIZED",
        }
        append_jsonl(INTER_NORMALIZED, updated)
        records.append(updated)

    log.info("Normalized %d tokens → %s", len(records), INTER_NORMALIZED)
    return records
