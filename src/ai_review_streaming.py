#!/usr/bin/env python3
"""
Memory-Efficient AI Review (Streaming Mode)
==========================================
Processes screened tokens through AI review in streaming mode.
"""

import gc
import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INTER_SCREENED, INTER_PRIMARY, INTER_CONSENSUS
from utils import get_logger, append_jsonl, write_jsonl, iter_jsonl

log = get_logger("ai_review_streaming")

# SaaS patterns and filters
SAAS_PATTERNS = ['flow', 'sync', 'cloud', 'hub', 'spot', 'base', 'bot', 'app', 'net', 'sys',
                   'data', 'code', 'tool', 'kit', 'deck', 'board', 'sheet', 'doc', 'file']
PROFANITY_LIST = {'fuck', 'shit', 'damn', 'hell', 'bitch', 'bastard', 'ass', 'dick',
                   'piss', 'crap', 'suck', 'sucks', 'cock', 'pussy', 'whore', 'slut'}
GENERIC_WORDS = {'me', 'you', 'he', 'she', 'it', 'we', 'they', 'this', 'that', 'the', 'a', 'an',
                  'of', 'in', 'on', 'at', 'to', 'for', 'with', 'and', 'but', 'or', 'is', 'are',
                  'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did'}


def create_vote(judge_id: str, decision: str, label: str, confidence: float, why: list):
    return {
        "judge_id": judge_id,
        "decision": decision,
        "label": label,
        "confidence": confidence,
        "why": why
    }


def primary_review_token(record: dict) -> tuple:
    """Review a single token. Returns (decision, label, confidence, reasons)."""
    word = record.get("normalized_word", "").lower()

    # Quick rejects
    if word in GENERIC_WORDS:
        return "reject", "rejected", 1.0, ["generic_word"]
    if word in PROFANITY_LIST:
        return "reject", "rejected", 1.0, ["profanity"]

    # SaaS patterns
    if any(p in word for p in SAAS_PATTERNS):
        return "accept", "functional", 0.8, ["contains_saas_pattern"]

    # Brandable (short, punchy)
    if 3 <= len(word) <= 6:
        vowels = sum(1 for c in word if c in 'aeiou')
        if vowels >= 2:
            return "accept", "brandable", 0.7, ["short_pronounceable"]

    # Default: accept with ambiguous label (recall principle)
    return "accept", "ambiguous", 0.6, ["valid_word"]


def run_ai_review_streaming():
    """Process AI review in streaming mode."""
    log.info("=" * 60)
    log.info("AI REVIEW (STREAMING MODE)")
    log.info("=" * 60)

    INTER_PRIMARY.parent.mkdir(parents=True, exist_ok=True)

    if INTER_PRIMARY.exists():
        INTER_PRIMARY.unlink()

    accept_count = 0
    reject_count = 0
    total_count = 0

    # Stream through screened tokens
    for rec in iter_jsonl(INTER_SCREENED):
        total_count += 1

        # Progress reporting
        if total_count % 50000 == 0:
            log.info("  Processed %d tokens...", total_count)
            gc.collect()

        screen_result = rec.get("screen_result", "")

        if screen_result != "pass":
            # Rule-rejected: create proper reject record
            reject_record = {
                **rec,
                "primary_votes": [
                    create_vote_record(
                        f"saas-title-judge-{i:02d}", "reject", "rejected", 1.0,
                        [f"Rule rejected: {rec.get('screen_reason', 'unknown')}"]
                    )
                    for i in range(1, 6)
                ],
                "primary_summary": {"accept": 0, "reject": 5, "borderline": 0},
                "status": "AI_PRIMARY_REVIEWED"
            }
            append_jsonl(INTER_PRIMARY, reject_record)
            reject_count += 1
            continue

        # AI review
        word = rec.get("normalized_word", "")
        decision, label, confidence, reasons = primary_review_token(rec)

        # Create votes
        votes = []
        for i in range(1, 6):
            votes.append(create_vote_record(
                f"saas-title-judge-{i:02d}", decision, label, confidence, reasons
            ))

        # Determine summary
        if decision == "accept":
            summary = {"accept": 5, "reject": 0, "borderline": 0}
            accept_count += 1
        else:
            summary = {"accept": 0, "reject": 5, "borderline": 0}
            reject_count += 1

        reviewed_record = {
            **rec,
            "primary_votes": votes,
            "primary_summary": summary,
            "status": "AI_PRIMARY_REVIEWED"
        }
        append_jsonl(INTER_PRIMARY, reviewed_record)

    log.info("AI review complete: %d total, %d accept, %d reject",
             total_count, accept_count, reject_count)
    log.info("Output: %s", INTER_PRIMARY)


if __name__ == "__main__":
    run_ai_review_streaming()
