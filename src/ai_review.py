"""
AI Review — Data utilities and vote aggregation.

Steps 5–8 (primary review, challenge, rebuttal, consensus) are performed
by the Claude Code session directly, NOT by this Python module.
This module provides:
  - File I/O helpers (load / save intermediate JSONL for each AI step)
  - Vote aggregation algorithm (Step 8, purely deterministic)
  - Consensus record builder (Step 8 output)

Execution model:
  Claude Code session reads INTER_SCREENED, performs AI judgment,
  and writes results using write_step_results() or its own Write tool.
  After Steps 5–7 are complete, call build_consensus() here to finalize.
"""

import json
from pathlib import Path
from typing import Iterator

from config import (
    ACCEPT_SCORE_THRESHOLD,
    BORDERLINE_SCORE_THRESHOLD,
    INTER_CHALLENGED,
    INTER_CONSENSUS,
    INTER_PRIMARY,
    INTER_REBUTTED,
    INTER_SCREENED,
    PIPELINE_VERSION,
    RISK_FLAG_THRESHOLD,
)
from utils import append_jsonl, get_logger, iter_jsonl, read_jsonl, write_jsonl

log = get_logger("ai_review")


# ---------------------------------------------------------------------------
# Agent IDs (reference — used in intermediate file records)
# ---------------------------------------------------------------------------

PRIMARY_JUDGE_IDS = [f"saas-title-judge-{i:02d}" for i in range(1, 6)]
CHALLENGE_REVIEWER_IDS = [f"challenge-reviewer-{i:02d}" for i in range(1, 6)]
REBUTTAL_REVIEWER_IDS = [f"rebuttal-reviewer-{i:02d}" for i in range(1, 4)]


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def load_screened_words() -> list[dict]:
    """Load words that passed rule screening (Step 4 output)."""
    if not INTER_SCREENED.exists():
        raise FileNotFoundError(f"Step 4 output not found: {INTER_SCREENED}")
    records = [r for r in read_jsonl(INTER_SCREENED) if r.get("screen_result") == "pass"]
    log.info("Loaded %d screened words from %s", len(records), INTER_SCREENED)
    return records


def load_primary_reviewed() -> list[dict]:
    """Load Step 5 output (primary AI review results)."""
    if not INTER_PRIMARY.exists():
        raise FileNotFoundError(f"Step 5 output not found: {INTER_PRIMARY}")
    return read_jsonl(INTER_PRIMARY)


def load_challenged() -> list[dict]:
    """Load Step 6 output (challenge review results)."""
    if not INTER_CHALLENGED.exists():
        raise FileNotFoundError(f"Step 6 output not found: {INTER_CHALLENGED}")
    return read_jsonl(INTER_CHALLENGED)


def load_rebutted() -> list[dict]:
    """Load Step 7 output (rebuttal review results)."""
    if not INTER_REBUTTED.exists():
        raise FileNotFoundError(f"Step 7 output not found: {INTER_REBUTTED}")
    return read_jsonl(INTER_REBUTTED)


# ---------------------------------------------------------------------------
# Save helpers (Claude Code can also write directly with its Write tool)
# ---------------------------------------------------------------------------

def save_primary_judgments(records: list[dict]) -> None:
    """Save Step 5 results to INTER_PRIMARY."""
    write_jsonl(INTER_PRIMARY, records)
    log.info("Saved %d primary-reviewed records → %s", len(records), INTER_PRIMARY)


def save_challenge_results(records: list[dict]) -> None:
    """Save Step 6 results to INTER_CHALLENGED."""
    write_jsonl(INTER_CHALLENGED, records)
    log.info("Saved %d challenge-reviewed records → %s", len(records), INTER_CHALLENGED)


def save_rebuttal_results(records: list[dict]) -> None:
    """Save Step 7 results to INTER_REBUTTED."""
    write_jsonl(INTER_REBUTTED, records)
    log.info("Saved %d rebuttal-reviewed records → %s", len(records), INTER_REBUTTED)


# ---------------------------------------------------------------------------
# Step 8 — Vote aggregation (pure Python, no LLM)
# ---------------------------------------------------------------------------

def _aggregate_votes(rebutted_records: list[dict]) -> list[dict]:
    """
    For each record, count effective votes from Steps 5–7 and compute vote_ratio.
    Returns one aggregation dict per record.
    """
    aggregated = []

    for rec in rebutted_records:
        accept_v = 0.0
        reject_v = 0.0
        abstain_v = 0.0
        why_accept_hints: list[str] = []
        reject_reason_hints: list[str] = []
        risk_flags: list[str] = []

        # Primary votes (Step 5): each judge casts 1 vote
        for vote in rec.get("primary_votes", []):
            d = vote.get("decision", "borderline")
            if d == "accept":
                accept_v += 1
                why_accept_hints.extend(vote.get("why", [])[:2])
            elif d == "reject":
                reject_v += 1
                reject_reason_hints.extend(vote.get("why", [])[:2])
            else:  # borderline
                accept_v += 0.5
                reject_v += 0.5
                abstain_v += 1

        # Challenges (Step 6): each challenge casts 0.5 votes
        for ch in rec.get("challenges", []):
            ct = ch.get("challenge_type", "")
            sd = ch.get("suggested_decision", "")
            if ct == "over_reject" or sd == "accept":
                accept_v += 0.5
            elif ct == "over_accept" or sd == "reject":
                reject_v += 0.5
            else:
                abstain_v += 1

        # Rebuttals (Step 7): each rebuttal casts 0.5 votes
        for rb in rec.get("rebuttals", []):
            rf = rb.get("recommended_final", "borderline")
            if rf == "accept":
                accept_v += 0.5
            elif rf == "reject":
                reject_v += 0.5
            else:
                abstain_v += 1

        total_decisive = accept_v + reject_v
        if total_decisive == 0:
            vote_ratio = 0.5
        else:
            vote_ratio = accept_v / total_decisive

        # Base decision from vote ratio
        if vote_ratio >= ACCEPT_SCORE_THRESHOLD:
            base_decision = "accept"
        elif vote_ratio >= BORDERLINE_SCORE_THRESHOLD:
            base_decision = "borderline"
        else:
            base_decision = "reject"

        # Primary label from plurality of accept votes
        label_counts: dict[str, int] = {}
        for vote in rec.get("primary_votes", []):
            lb = vote.get("label")
            if lb and vote.get("decision") in ("accept", "borderline"):
                label_counts[lb] = label_counts.get(lb, 0) + 1
        primary_label = (
            max(label_counts, key=label_counts.get) if label_counts else "ambiguous"
        )

        aggregated.append({
            "normalized_word": rec.get("normalized_word", ""),
            "source_record": rec,
            "accept_votes": round(accept_v, 2),
            "reject_votes": round(reject_v, 2),
            "abstain_votes": round(abstain_v, 2),
            "vote_ratio": round(vote_ratio, 4),
            "base_decision": base_decision,
            "primary_label": primary_label,
            "why_accept_hints": list(dict.fromkeys(why_accept_hints))[:5],
            "reject_reason_hints": list(dict.fromkeys(reject_reason_hints))[:5],
            "risk_flags": risk_flags,
        })

    return aggregated


def build_consensus(rebutted_records: list[dict]) -> list[dict]:
    """
    Step 8 (algorithmic part): aggregate all votes and produce final
    consensus records. Writes INTER_CONSENSUS.

    Borderline → promoted to accept_with_risk (recall principle).
    Low consensus accept → low_consensus risk flag.
    """
    aggregated = _aggregate_votes(rebutted_records)
    results = []

    for agg in aggregated:
        final_decision = agg["base_decision"]
        risk_flags = list(agg.get("risk_flags", []))

        # Recall principle: borderline → accept with flag
        if final_decision == "borderline":
            final_decision = "accept"
            risk_flags.append("borderline_promoted")

        # Low-confidence accept
        if final_decision == "accept" and agg["vote_ratio"] < RISK_FLAG_THRESHOLD:
            risk_flags.append("low_consensus")

        label = agg.get("primary_label", "ambiguous")

        consensus_record = {
            **agg["source_record"],
            "decision": final_decision,
            "primary_label": label,
            "candidate_modes": [label] if label else [],
            "confidence": round(agg["vote_ratio"], 3),
            "consensus": {
                "support": agg["accept_votes"],
                "oppose": agg["reject_votes"],
                "abstain": agg["abstain_votes"],
            },
            "why_accept": agg.get("why_accept_hints", []) if final_decision == "accept" else [],
            "reject_reason": agg.get("reject_reason_hints", []) if final_decision == "reject" else [],
            "risk_flags": risk_flags,
            "status": "CONSENSUS_DECIDED",
        }
        results.append(consensus_record)

    write_jsonl(INTER_CONSENSUS, results)

    accept_n = sum(1 for r in results if r["decision"] == "accept")
    reject_n = sum(1 for r in results if r["decision"] == "reject")
    log.info(
        "Consensus built: %d accept, %d reject → %s",
        accept_n, reject_n, INTER_CONSENSUS,
    )
    return results


# ---------------------------------------------------------------------------
# Streaming variants (memory-efficient)
# ---------------------------------------------------------------------------

def iter_rebutted() -> Iterator[dict]:
    """Stream rebutted records (memory-efficient variant of load_rebutted)."""
    if not INTER_REBUTTED.exists():
        raise FileNotFoundError(f"Step 7 output not found: {INTER_REBUTTED}")
    return iter_jsonl(INTER_REBUTTED)


def build_consensus_streaming(rebutted_iterator: Iterator[dict]) -> Path:
    """
    Step 8 streaming version: aggregate votes and write directly to file.
    Returns path to written file (INTER_CONSENSUS).

    Memory-efficient: processes one record at a time instead of loading all.
    """
    INTER_CONSENSUS.parent.mkdir(parents=True, exist_ok=True)

    accept_count = 0
    reject_count = 0

    with open(INTER_CONSENSUS, "w", encoding="utf-8") as f:
        for rec in rebutted_iterator:
            # Per-record aggregation (extracted from _aggregate_votes loop)
            accept_v = 0.0
            reject_v = 0.0
            abstain_v = 0.0
            why_accept_hints: list[str] = []
            reject_reason_hints: list[str] = []

            # Primary votes (Step 5)
            for vote in rec.get("primary_votes", []):
                d = vote.get("decision", "borderline")
                if d == "accept":
                    accept_v += 1
                    why_accept_hints.extend(vote.get("why", [])[:2])
                elif d == "reject":
                    reject_v += 1
                    reject_reason_hints.extend(vote.get("why", [])[:2])
                else:  # borderline
                    accept_v += 0.5
                    reject_v += 0.5
                    abstain_v += 1

            # Challenges (Step 6)
            for ch in rec.get("challenges", []):
                ct = ch.get("challenge_type", "")
                sd = ch.get("suggested_decision", "")
                if ct == "over_reject" or sd == "accept":
                    accept_v += 0.5
                elif ct == "over_accept" or sd == "reject":
                    reject_v += 0.5
                else:
                    abstain_v += 1

            # Rebuttals (Step 7)
            for rb in rec.get("rebuttals", []):
                rf = rb.get("recommended_final", "borderline")
                if rf == "accept":
                    accept_v += 0.5
                elif rf == "reject":
                    reject_v += 0.5
                else:
                    abstain_v += 1

            total_decisive = accept_v + reject_v
            if total_decisive == 0:
                vote_ratio = 0.5
            else:
                vote_ratio = accept_v / total_decisive

            # Base decision from vote ratio
            if vote_ratio >= ACCEPT_SCORE_THRESHOLD:
                base_decision = "accept"
            elif vote_ratio >= BORDERLINE_SCORE_THRESHOLD:
                base_decision = "borderline"
            else:
                base_decision = "reject"

            # Primary label from plurality
            label_counts: dict[str, int] = {}
            for vote in rec.get("primary_votes", []):
                lb = vote.get("label")
                if lb and vote.get("decision") in ("accept", "borderline"):
                    label_counts[lb] = label_counts.get(lb, 0) + 1
            primary_label = (
                max(label_counts, key=label_counts.get) if label_counts else "ambiguous"
            )

            # Risk flags
            risk_flags: list[str] = []
            if base_decision == "borderline":
                base_decision = "accept"
                risk_flags.append("borderline_promoted")
            if base_decision == "accept" and vote_ratio < RISK_FLAG_THRESHOLD:
                risk_flags.append("low_consensus")

            # Build consensus record
            consensus_record = {
                **rec,
                "decision": base_decision,
                "primary_label": primary_label,
                "candidate_modes": [primary_label] if primary_label else [],
                "confidence": round(vote_ratio, 3),
                "consensus": {
                    "support": round(accept_v, 2),
                    "oppose": round(reject_v, 2),
                    "abstain": round(abstain_v, 2),
                },
                "why_accept": list(dict.fromkeys(why_accept_hints))[:5] if base_decision == "accept" else [],
                "reject_reason": list(dict.fromkeys(reject_reason_hints))[:5] if base_decision == "reject" else [],
                "risk_flags": risk_flags,
                "status": "CONSENSUS_DECIDED",
            }

            f.write(json.dumps(consensus_record, ensure_ascii=False) + "\n")

            if base_decision == "accept":
                accept_count += 1
            else:
                reject_count += 1

    log.info(
        "Consensus built (streaming): %d accept, %d reject → %s",
        accept_count, reject_count, INTER_CONSENSUS,
    )
    return INTER_CONSENSUS
