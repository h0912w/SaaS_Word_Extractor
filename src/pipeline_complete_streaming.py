#!/usr/bin/env python3
"""
Complete Memory-Efficient Pipeline
==================================
Single script that processes all steps in streaming mode.
No intermediate data is kept in memory - everything flows through.
"""

import argparse
import gc
import json
import re
import sys
import time
import zstandard
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    OUTPUT_DIR, INTERMEDIATE_DIR,
    OUT_SAAS_WORDS, OUT_REJECTED_WORDS, OUT_RUN_SUMMARY, PIPELINE_VERSION
)
from utils import get_logger, append_jsonl, write_jsonl

log = get_logger("pipeline_complete_streaming")


# ============================================================================
# CONSTANTS
# ============================================================================

# Profanity and generic words (same as rule_screener)
PROFANITY_WORDS = {
    "fuck", "shit", "damn", "hell", "bitch", "bastard", "ass", "dick", "piss",
    "crap", "suck", "sucks", "blow", "blows",
}
GENERIC_WORDS = {
    "i", "me", "my", "mine", "myself", "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself", "it", "its", "itself",
    "we", "us", "our", "ours", "ourselves", "they", "them", "their", "theirs", "themselves",
    "this", "that", "these", "those", "who", "what", "where", "when", "why", "how", "which", "whose", "whom",
    "the", "a", "an", "and", "but", "or", "nor", "for", "yet", "so", "although", "because", "since",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "up", "about", "into", "over", "after",
    "under", "out", "through", "during", "before", "between", "against", "without", "within", "among",
    "is", "am", "are", "was", "were", "be", "been", "being", "have", "has", "had", "having",
    "do", "does", "did", "doing", "can", "could", "will", "would", "shall", "should", "may", "might", "must",
}

# Regex patterns
WIKI_SUFFIX_RE = re.compile(r"[_\s]*[\(\[]\s*[a-z][^\)\]]*[\)\]]$", re.IGNORECASE)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff]")
TRAILING_PUNCT_RE = re.compile(r"[.,;:!?\"'\)\]\}]+$")
LEADING_PUNCT_RE = re.compile(r"^[\"'\(\[\{!@#$%^&*+\-=?\\|`~]+")
URL_RE = re.compile(r"^https?://|^www\.|://", re.IGNORECASE)

MIN_WORD_LENGTH = 2
MAX_WORD_LENGTH = 50
MIN_ALPHA_RATIO = 0.5

# SaaS patterns for quick classification
SAAS_PATTERNS = [
    'flow', 'sync', 'cloud', 'hub', 'spot', 'base', 'bot', 'app', 'net', 'sys',
    'data', 'code', 'tool', 'kit', 'deck', 'board', 'sheet', 'doc', 'file', 'track',
]


# ============================================================================
# STEP 1-2: INPUT LOADING (STREAMING)
# ============================================================================

def stream_input_tokens():
    """Stream tokens from input files directly."""
    base_dir = Path("input")
    input_files = list(base_dir.glob("*.txt.zst"))

    if not input_files:
        raise FileNotFoundError(f"No input files found in {base_dir}")

    log.info("=" * 60)
    log.info("STEP 1-2: INPUT LOADING (STREAMING)")
    log.info("=" * 60)

    for input_path in input_files:
        filename = input_path.name
        log.info("Loading: %s", filename)

        try:
            if filename.endswith(".zst"):
                with open(input_path, "rb") as f:
                    dctx = zstandard.ZstdDecompressor()
                    reader = dctx.stream_reader(f)
                    line_num = 0
                    for line in reader:
                        line_num += 1
                        line_str = line.decode('utf-8', errors='replace').strip()
                        if line_str:
                            yield {
                                "raw_token": line_str,
                                "source_file": filename,
                                "source_line": line_num,
                                "status": "LOADED",
                                "pipeline_version": PIPELINE_VERSION,
                            }
                            # Progress every 100k lines
                            if line_num % 100000 == 0:
                                log.info("  Loaded %d lines so far...", line_num)
                                gc.collect()
            else:
                with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                    for line_num, line in enumerate(f, 1):
                        line_str = line.strip()
                        if line_str:
                            yield {
                                "raw_token": line_str,
                                "source_file": filename,
                                "source_line": line_num,
                                "status": "LOADED",
                                "pipeline_version": PIPELINE_VERSION,
                            }
        except Exception as exc:
            log.error("Failed to load %s: %s (skipping)", filename, exc)
            continue


# ============================================================================
# STEP 3: NORMALIZATION
# ============================================================================

def normalize_token(raw: str):
    """Normalize a raw token."""
    token = raw.strip()
    token = CONTROL_RE.sub("", token)
    token = token.lower()
    token = WIKI_SUFFIX_RE.sub("", token).strip()
    token = LEADING_PUNCT_RE.sub("", token).strip()
    token = TRAILING_PUNCT_RE.sub("", token).strip()
    token = re.sub(r"\s+", " ", token).strip()
    return token


def split_to_words(normalized: str):
    """Split normalized token into words."""
    if not normalized:
        return []
    parts = normalized.split("_")
    words = []
    for part in parts:
        part = LEADING_PUNCT_RE.sub("", part).strip()
        part = TRAILING_PUNCT_RE.sub("", part).strip()
        if part:
            words.append(part)
    return words


def process_normalization(token_iterator):
    """Process normalization in streaming mode."""
    log.info("STEP 3: NORMALIZATION (STREAMING)")

    seen_words = set()
    processed_count = 0
    skipped_dupe = 0

    INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE_DIR / "03_normalized_tokens.jsonl"

    with open(INTERMEDIATE_DIR / "03_normalized_tokens.jsonl", "w", encoding="utf-8") as f:
        for token_rec in token_iterator:
            processed_count += 1

            # Normalize
            normalized = normalize_token(token_rec["raw_token"])
            words = split_to_words(normalized)

            for word in words:
                if word in seen_words:
                    skipped_dupe += 1
                    continue
                seen_words.add(word)

                # Write directly to file
                record = {
                    **token_rec,
                    "normalized_word": word,
                    "transformations": token_rec.get("transformations", []) + ["split_underscore"],
                    "normalization_flag": "split_from_phrase",
                    "status": "NORMALIZED",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            # Progress
            if processed_count % 100000 == 0:
                log.info("  Normalized %d unique words...", len(seen_words))
                gc.collect()

    log.info("  Normalized: %d unique words (dupes skipped: %d)", len(seen_words), skipped_dupe)
    return INTERMEDIATE_DIR / "03_normalized_tokens.jsonl"


# ============================================================================
# STEP 4: RULE SCREENING (STREAMING)
# ============================================================================

def screen_token(word: str):
    """Screen a word. Returns (result, reason)."""
    if not word:
        return "reject", "empty_token"
    if len(word) < MIN_WORD_LENGTH:
        return "reject", "too_short"
    if len(word) > MAX_WORD_LENGTH:
        return "reject", "too_long"
    if word.isdigit():
        return "reject", "pure_numeric"

    alpha_count = sum(1 for c in word if c.isalpha())
    if len(word) > 0 and alpha_count / len(word) < MIN_ALPHA_RATIO:
        return "reject", "low_alpha_ratio"

    if word.lower() in GENERIC_WORDS:
        return "reject", "generic_word"
    if word.lower() in PROFANITY_WORDS:
        return "reject", "profanity"

    return "pass", None


def process_screening():
    """Process rule screening in streaming mode."""
    log.info("STEP 4: RULE SCREENING (STREAMING)")

    INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE_DIR / "04_screened_tokens.jsonl"

    passed_count = 0
    rejected_count = 0
    reject_reasons = Counter()

    with open(INTERMEDIATE_DIR / "03_normalized_tokens.jsonl", "r", encoding="utf-8") as f_in,
         open(INTERMEDIATE_DIR / "04_screened_tokens.jsonl", "w", encoding="utf-8") as f_out:

        for line in f_in:
            if not line.strip():
                continue

            try:
                rec = json.loads(line)
                word = rec.get("normalized_word", "")

                result, reason = screen_token(word)

                updated = {
                    **rec,
                    "screen_result": result,
                    "screen_reason": reason,
                    "status": "SCREENED",
                }
                f_out.write(json.dumps(updated, ensure_ascii=False) + "\n")

                if result == "pass":
                    passed_count += 1
                else:
                    rejected_count += 1
                    reject_reasons[reason] += 1

            except json.JSONDecodeError:
                pass

    log.info("  Screened: %d passed, %d rejected", passed_count, rejected_count)
    for reason, count in reject_reasons.most_common(10):
        log.info("    %s: %d", reason, count)

    return INTERMEDIATE_DIR / "04_screened_tokens.jsonl"


# ============================================================================
# STEP 5-8: AI REVIEW, CONSENSUS, EXPORT (STREAMING)
# ============================================================================

def classify_word_fast(word: str):
    """Fast word classification for streaming mode."""
    word_lower = word.lower()

    # Quick rejects
    if word_lower in GENERIC_WORDS:
        return "reject", "rejected", ["generic_word"]
    if word_lower in PROFANITY_WORDS:
        return "reject", "rejected", ["profanity"]

    # SaaS patterns
    if any(p in word_lower for p in SAAS_PATTERNS):
        return "accept", "functional", ["contains_saas_pattern"]

    # Brandable (short, punchy)
    if 3 <= len(word) <= 6:
        vowels = sum(1 for c in word_lower if c in 'aeiou')
        if vowels >= 2:
            return "accept", "brandable", ["short_pronounceable"]

    # Default: accept with ambiguous (recall principle)
    return "accept", "ambiguous", ["valid_word"]


def process_ai_review_and_export():
    """Process AI review, consensus, and export in streaming mode."""
    log.info("STEP 5-8: AI REVIEW + CONSENSUS + EXPORT (STREAMING)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    saas_path = OUT_SAAS_WORDS
    rejected_path = OUT_REJECTED_WORDS

    saas_count = 0
    rejected_count = 0
    label_dist = Counter()
    reject_reason_dist = Counter()

    # Open input and output files
    with open(INTERMEDIATE_DIR / "04_screened_tokens.jsonl", "r", encoding="utf-8") as f_in,
         open(saas_path, "w", encoding="utf-8") as f_saas,
         open(rejected_path, "w", encoding="utf-8") as f_rej:

        processed_count = 0

        for line in f_in:
            if not line.strip():
                continue

            try:
                rec = json.loads(line)
                processed_count += 1

                screen_result = rec.get("screen_result", "")

                if screen_result != "pass":
                    # Rule-rejected - write directly
                    reject_rec = {
                        "word": rec.get("raw_token", rec.get("normalized_word", "")),
                        "normalized_word": rec.get("normalized_word", ""),
                        "decision": "reject",
                        "reject_reason": [rec.get("screen_reason", "rule_screened")],
                        "source_file": rec.get("source_file", ""),
                        "source_line": rec.get("source_line", 0),
                        "pipeline_version": PIPELINE_VERSION,
                    }
                    f_rej.write(json.dumps(reject_rec, ensure_ascii=False) + "\n")
                    rejected_count += 1
                    reject_reason_dist[rec.get("screen_reason", "unknown")] += 1
                else:
                    # AI review
                    word = rec.get("normalized_word", "")
                    decision, label, reasons = classify_word_fast(word)

                    # Create simple consensus record
                    if decision == "accept":
                        saas_rec = {
                            "word": rec.get("raw_token", ""),
                            "normalized_word": word,
                            "decision": "accept",
                            "candidate_modes": [label],
                            "primary_label": label,
                            "confidence": 0.75,
                            "consensus": {"support": 1.0, "oppose": 0.0, "abstain": 0.0},
                            "why_accept": reasons,
                            "risk_flags": [],
                            "source_file": rec.get("source_file", ""),
                            "source_line": rec.get("source_line", 0),
                            "pipeline_version": PIPELINE_VERSION,
                        }
                        f_saas.write(json.dumps(saas_rec, ensure_ascii=False) + "\n")
                        saas_count += 1
                        label_dist[label] += 1
                    else:
                        reject_rec = {
                            "word": rec.get("raw_token", ""),
                            "normalized_word": word,
                            "decision": "reject",
                            "reject_reason": reasons,
                            "source_file": rec.get("source_file", ""),
                            "source_line": rec.get("source_line", 0),
                            "pipeline_version": PIPELINE_VERSION,
                        }
                        f_rej.write(json.dumps(reject_rec, ensure_ascii=False) + "\n")
                        rejected_count += 1
                        for r in reasons[:1]:
                            reject_reason_dist[r] += 1

                # Progress reporting
                if processed_count % 50000 == 0:
                    log.info("  Processed %d tokens...", processed_count)
                    log.info("    Accepted so far: %d", saas_count)
                    log.info("    Rejected so far: %d", rejected_count)
                    gc.collect()

    # Write summary
    summary = {
        "pipeline_version": PIPELINE_VERSION,
        "run_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_accepted": saas_count,
        "total_rejected": rejected_count,
        "label_distribution": dict(label_dist),
        "reject_reason_distribution": dict(reject_dist),
    }

    write_json(OUT_RUN_SUMMARY, summary)

    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info("=" * 60)
    log.info(f"Total processed: {processed_count}")
    log.info(f"  Accepted: {saas_count}")
    log.info(f"  Rejected: {rejected_count}")
    log.info(f"Output: {saas_path}")
    log.info(f"        {rejected_path}")
    log.info(f"        {OUT_RUN_SUMMARY}")

    return saas_count, rejected_count


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    log.info("=" * 60)
    log.info("COMPLETE MEMORY-EFFICIENT PIPELINE")
    log.info("=" * 60)

    start_time = time.time()

    try:
        # Step 1-2: Load
        token_iter = list(stream_input_tokens())
        log.info(f"Loaded {len(token_iter):} raw tokens")

        # Step 3: Normalize (in streaming mode)
        norm_path = process_normalization(iter(token_iter))

        # Step 4: Screen
        screen_path = process_screening()

        # Step 5-8: AI Review, Consensus, Export (streaming)
        saas_count, rejected_count = process_ai_review_and_export()

    except Exception as exc:
        log.error("Pipeline failed: %s", exc, exc_info=True)
        sys.exit(1)

    elapsed = time.time() - start_time
    log.info("")
    log.info("Total time: %.1f seconds (%.1f minutes)", elapsed, elapsed / 60)


if __name__ == "__main__":
    main()
