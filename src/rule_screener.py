"""
Step 4 — Rule-based 1st-pass screening.

Design principle: RECALL OVER PRECISION.
Only tokens that are clearly, unambiguously noise are rejected here.
When in doubt, the token is preserved as "review_needed" for the AI stages.

Reject criteria (applied in order; first match wins):
  R1  Empty / whitespace only after normalization
  R2  Length < MIN_WORD_LENGTH or > MAX_WORD_LENGTH
  R3  Alphabetic character ratio < MIN_ALPHA_RATIO
  R4  Starts with http/www/ or contains :// (URL fragment)
  R5  Looks like a file path (contains / or \\ with extension)
  R6  Looks like a code token (__dunder__, camelCase with digits, hex literal)
  R7  Pure numeric string
  R8  Repeating single character (aaaa, !!!!!)

Pre-accept criteria (fast-path into AI review with pass_reason noted):
  P1  Matches a known SaaS-friendly word pattern (purely optional hint)

All remaining tokens pass with status "pass" for AI semantic review.
LLM agents (recall-guardian-a, noise-guardian-b, edgecase-guardian-c)
review the reject distribution; this module only does deterministic filtering.
"""

import re
from pathlib import Path

from config import (
    INTER_SCREENED,
    MIN_ALPHA_RATIO,
    MIN_WORD_LENGTH,
    MAX_WORD_LENGTH,
    PIPELINE_VERSION,
)
from utils import get_logger, append_jsonl, read_jsonl

log = get_logger("rule_screener")

# Regex helpers
URL_RE = re.compile(r"^https?://|^www\.|://", re.IGNORECASE)
PATH_RE = re.compile(r"[/\\]")
CODE_DUNDER_RE = re.compile(r"^__\w+__$")
CODE_HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$")
CODE_CAMEL_DIGIT_RE = re.compile(r"[a-z][A-Z].*\d|\d.*[a-z][A-Z]")
REPEAT_CHAR_RE = re.compile(r"^(.)\1{3,}$")  # same char repeated 4+ times


def _alpha_ratio(s: str) -> float:
    if not s:
        return 0.0
    return sum(1 for c in s if c.isalpha()) / len(s)


def screen_token(word: str) -> tuple[str, str | None]:
    """
    Returns (result, reason) where result is 'pass' or 'reject'.
    reason is None for 'pass', or a short label for 'reject'.
    """
    # R1 – empty
    if not word:
        return "reject", "empty_token"

    # R2 – length
    if len(word) < MIN_WORD_LENGTH:
        return "reject", "too_short"
    if len(word) > MAX_WORD_LENGTH:
        return "reject", "too_long"

    # R7 – pure numeric
    if word.isdigit():
        return "reject", "pure_numeric"

    # R3 – alpha ratio
    if _alpha_ratio(word) < MIN_ALPHA_RATIO:
        return "reject", "low_alpha_ratio"

    # R4 – URL fragment
    if URL_RE.search(word):
        return "reject", "url_fragment"

    # R5 – file path fragment (contains path separator AND a dot-extension)
    if PATH_RE.search(word) and re.search(r"\.\w{1,5}$", word):
        return "reject", "filepath_fragment"

    # R6 – code tokens
    if CODE_DUNDER_RE.match(word):
        return "reject", "code_dunder"
    if CODE_HEX_RE.match(word):
        return "reject", "hex_literal"

    # R8 – repeating single char
    if REPEAT_CHAR_RE.match(word):
        return "reject", "repeat_char"

    return "pass", None


def run(normalized_records: list[dict], resume: bool = False) -> tuple[list[dict], list[dict]]:
    """
    Step 4: screen every normalized token.
    Returns (passed_records, rejected_records).
    Both are written to INTER_SCREENED (with screen_result field).
    """
    if resume and INTER_SCREENED.exists():
        log.info("Resuming from %s", INTER_SCREENED)
        all_records = read_jsonl(INTER_SCREENED)
        passed = [r for r in all_records if r.get("screen_result") == "pass"]
        rejected = [r for r in all_records if r.get("screen_result") == "reject"]
        log.info("Resumed: %d passed, %d rejected", len(passed), len(rejected))
        return passed, rejected

    if INTER_SCREENED.exists():
        INTER_SCREENED.unlink()

    passed = []
    rejected = []
    reject_reason_counts: dict[str, int] = {}

    for rec in normalized_records:
        word = rec.get("normalized_word", "")
        result, reason = screen_token(word)

        updated = {
            **rec,
            "screen_result": result,
            "screen_reason": reason,
            "status": "SCREENED",
        }
        append_jsonl(INTER_SCREENED, updated)

        if result == "pass":
            passed.append(updated)
        else:
            rejected.append(updated)
            reject_reason_counts[reason] = reject_reason_counts.get(reason, 0) + 1

    total = len(passed) + len(rejected)
    log.info(
        "Screened %d tokens: %d passed (%.1f%%), %d rejected",
        total, len(passed), 100 * len(passed) / max(total, 1), len(rejected),
    )
    for reason, count in sorted(reject_reason_counts.items(), key=lambda x: -x[1]):
        log.info("  reject reason %-25s: %d", reason, count)

    return passed, rejected
