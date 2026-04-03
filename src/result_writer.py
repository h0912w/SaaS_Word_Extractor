"""
Step 9 — Result writer.
Splits consensus records into accepted and rejected sets,
validates JSONL schema, and writes:
  /output/saas_words.jsonl
  /output/rejected_words.jsonl
  /output/run_summary.json

Also writes rejected rule-screened tokens into rejected_words.jsonl
so the final file is comprehensive.
"""

import csv
import datetime
import json
from collections import Counter
from pathlib import Path

from config import (
    INTER_CONSENSUS,
    INTER_SCREENED,
    OUT_REJECTED_WORDS,
    OUT_RUN_SUMMARY,
    OUT_SAAS_WORDS,
    PIPELINE_VERSION,
)
from utils import get_logger, iter_jsonl, iter_jsonl_filter, write_json

log = get_logger("result_writer")

REQUIRED_SAAS_FIELDS = {
    "word", "normalized_word", "decision", "candidate_modes",
    "confidence", "consensus", "source_file", "source_line", "pipeline_version",
}
REQUIRED_REJECT_FIELDS = {
    "word", "normalized_word", "decision",
    "source_file", "source_line", "pipeline_version",
}


def _validate_schema(record: dict, required_fields: set[str], label: str) -> bool:
    missing = required_fields - set(record.keys())
    if missing:
        log.warning("Schema warning [%s] word=%r missing fields: %s",
                    label, record.get("normalized_word", "?"), missing)
        return False
    return True


def _build_saas_record(rec: dict) -> dict:
    """Produce a clean saas_words.jsonl record from a consensus record.

    Supports both Python-generated and agent-generated field structures:
    - Python: decision, confidence, why_accept, risk_flags, consensus (dict)
    - Agent: consensus_decision, consensus_confidence, consensus_reasons, primary_summary
    """
    # Get decision from either field structure
    decision = rec.get("decision") or rec.get("consensus_decision", "accept")

    # Get confidence from either field structure
    confidence = rec.get("confidence") or rec.get("consensus_confidence", 0.5)

    # Get primary label from either field structure
    primary_label = rec.get("primary_label") or rec.get("consensus_label", "ambiguous")

    # Get why_accept from either field structure
    why_accept = rec.get("why_accept", [])
    if not why_accept:
        # Try agent-generated field
        consensus_reasons = rec.get("consensus_reasons", [])
        if decision == "accept" and consensus_reasons:
            why_accept = consensus_reasons

    # Get risk_flags from either field structure
    risk_flags = rec.get("risk_flags", [])

    # Build consensus dict from either field structure
    consensus = rec.get("consensus", {"support": 0, "oppose": 0, "abstain": 0})
    if consensus.get("support") == 0 and consensus.get("oppose") == 0:
        # Try agent-generated primary_summary
        primary_summary = rec.get("primary_summary", {})
        if primary_summary:
            accept_count = primary_summary.get("accept", 0)
            reject_count = primary_summary.get("reject", 0)
            consensus = {
                "support": float(accept_count),
                "oppose": float(reject_count),
                "abstain": float(primary_summary.get("borderline", 0))
            }

    return {
        "word": rec.get("raw_token", rec.get("normalized_word", "")),
        "normalized_word": rec.get("normalized_word", ""),
        "decision": decision,
        "candidate_modes": rec.get("candidate_modes", [primary_label] if primary_label else []),
        "primary_label": primary_label,
        "confidence": confidence,
        "consensus": consensus,
        "why_accept": why_accept,
        "risk_flags": risk_flags,
        "source_file": rec.get("source_file", ""),
        "source_line": rec.get("source_line", 0),
        "pipeline_version": PIPELINE_VERSION,
    }


def _build_reject_record(rec: dict, reject_reason: list[str] | None = None) -> dict:
    """Produce a clean rejected_words.jsonl record.

    Supports both Python-generated and agent-generated field structures.
    """
    # Get reject reason from multiple possible sources
    if reject_reason:
        reasons = reject_reason
    elif rec.get("reject_reason"):
        reasons = rec.get("reject_reason", [])
    elif rec.get("screen_reason"):
        reasons = [rec.get("screen_reason", "")]
    else:
        # Try to extract from primary_votes or consensus_reasons
        reasons = []
        if rec.get("consensus_reasons"):
            reasons = rec.get("consensus_reasons", [])
        elif rec.get("primary_votes"):
            # Extract from judge reasons
            for vote in rec.get("primary_votes", []):
                if vote.get("decision") == "reject":
                    why = vote.get("why", [])
                    if why:
                        reasons.extend(why[:2])
        if not reasons:
            reasons = ["unknown"]

    # Build consensus dict from either field structure
    consensus = rec.get("consensus", {"support": 0, "oppose": 0, "abstain": 0})
    if consensus.get("support") == 0 and consensus.get("oppose") == 0:
        # Try agent-generated primary_summary
        primary_summary = rec.get("primary_summary", {})
        if primary_summary:
            accept_count = primary_summary.get("accept", 0)
            reject_count = primary_summary.get("reject", 0)
            consensus = {
                "support": float(accept_count),
                "oppose": float(reject_count),
                "abstain": float(primary_summary.get("borderline", 0))
            }

    return {
        "word": rec.get("raw_token", rec.get("normalized_word", "")),
        "normalized_word": rec.get("normalized_word", ""),
        "decision": "reject",
        "reject_reason": reasons,
        "consensus": consensus,
        "source_file": rec.get("source_file", ""),
        "source_line": rec.get("source_line", 0),
        "pipeline_version": PIPELINE_VERSION,
    }


def run(
    consensus_records: list[dict],
    rule_rejected_records: list[dict],
    run_meta: dict | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Write saas_words.jsonl, rejected_words.jsonl, and run_summary.json.
    Returns (saas_records, rejected_records).
    """
    saas_records: list[dict] = []
    ai_rejected: list[dict] = []

    for rec in consensus_records:
        # Support both 'decision' and 'consensus_decision' fields
        decision = rec.get("decision") or rec.get("consensus_decision", "reject")
        if decision == "accept":
            sr = _build_saas_record(rec)
            _validate_schema(sr, REQUIRED_SAAS_FIELDS, "saas")
            saas_records.append(sr)
        else:
            rr = _build_reject_record(rec)
            _validate_schema(rr, REQUIRED_REJECT_FIELDS, "rejected")
            ai_rejected.append(rr)

    # Rule-rejected records (from step 4)
    rule_rejected = [_build_reject_record(r, [r.get("screen_reason", "rule_screened")])
                     for r in rule_rejected_records]

    all_rejected = ai_rejected + rule_rejected

    # Write JSONL files
    write_jsonl(OUT_SAAS_WORDS, saas_records)
    write_jsonl(OUT_REJECTED_WORDS, all_rejected)
    log.info("Wrote %d SaaS words → %s", len(saas_records), OUT_SAAS_WORDS)
    log.info("Wrote %d rejected words → %s", len(all_rejected), OUT_REJECTED_WORDS)

    # --- Build run_summary.json ---
    label_dist = Counter(r.get("primary_label", "unknown") for r in saas_records)
    risk_dist = Counter(
        flag
        for r in saas_records
        for flag in r.get("risk_flags", [])
    )
    reject_reason_dist = Counter(
        (r.get("reject_reason") or ["unknown"])[0]
        for r in all_rejected
    )

    summary = {
        "pipeline_version": PIPELINE_VERSION,
        "run_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "input_stats": run_meta or {},
        "total_accepted": len(saas_records),
        "total_rejected": len(all_rejected),
        "ai_rejected": len(ai_rejected),
        "rule_rejected": len(rule_rejected),
        "label_distribution": dict(label_dist),
        "risk_flag_distribution": dict(risk_dist),
        "reject_reason_distribution": dict(reject_reason_dist),
    }
    write_json(OUT_RUN_SUMMARY, summary)
    log.info("Wrote run summary → %s", OUT_RUN_SUMMARY)

    return saas_records, all_rejected


# ---------------------------------------------------------------------------
# Streaming variants (memory-efficient)
# ---------------------------------------------------------------------------

def run_streaming(run_meta: dict | None = None) -> tuple[Path, Path]:
    """
    Streaming version: Write saas_words.jsonl and rejected_words.jsonl
    by streaming through consensus records.
    Returns (saas_path, rejected_path).

    Uses two-pass approach:
    Pass 1: Write individual record files
    Pass 2: Collect statistics and write summary
    """
    saas_path = OUT_SAAS_WORDS
    rejected_path = OUT_REJECTED_WORDS

    saas_count = 0
    ai_reject_count = 0

    # Pass 1: Write JSONL files (streaming)
    saas_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_path.parent.mkdir(parents=True, exist_ok=True)

    with open(saas_path, "w", encoding="utf-8") as saas_f, \
         open(rejected_path, "w", encoding="utf-8") as rej_f:

        for rec in iter_jsonl(INTER_CONSENSUS):
            decision = rec.get("decision") or rec.get("consensus_decision", "reject")

            if decision == "accept":
                saas_rec = _build_saas_record(rec)
                _validate_schema(saas_rec, REQUIRED_SAAS_FIELDS, "saas")
                saas_f.write(json.dumps(saas_rec, ensure_ascii=False) + "\n")
                saas_count += 1
            else:
                rej_rec = _build_reject_record(rec)
                _validate_schema(rej_rec, REQUIRED_REJECT_FIELDS, "rejected")
                rej_f.write(json.dumps(rej_rec, ensure_ascii=False) + "\n")
                ai_reject_count += 1

    # Note: Rule-rejected records are already included in INTER_CONSENSUS
    # They were processed through primary review with reject votes
    # No need to separately process from INTER_SCREENED (which may be deleted)

    log.info("Wrote %d SaaS words → %s", saas_count, saas_path)
    log.info("Wrote %d rejected words → %s", ai_reject_count, rejected_path)

    # Pass 2: Collect statistics (streaming through output files we just wrote)
    # rule_reject_count is now 0 since rule-rejected are included in ai_reject_count
    _write_run_summary_streaming(saas_path, rejected_path, run_meta,
                                saas_count, ai_reject_count, 0)

    return saas_path, rejected_path


def _write_run_summary_streaming(saas_path: Path, rejected_path: Path,
                                 run_meta: dict, saas_count: int,
                                 ai_reject_count: int, rule_reject_count: int):
    """Write run_summary.json by streaming through output files for statistics."""
    label_dist = Counter()
    risk_dist = Counter()
    reject_reason_dist = Counter()

    # Stream saas_words for label/risk distribution
    for rec in iter_jsonl(saas_path):
        label_dist[rec.get("primary_label", "unknown")] += 1
        for flag in rec.get("risk_flags", []):
            risk_dist[flag] += 1

    # Stream rejected_words for reason distribution
    for rec in iter_jsonl(rejected_path):
        reasons = rec.get("reject_reason", [])
        if reasons:
            reject_reason_dist[reasons[0]] += 1

    summary = {
        "pipeline_version": PIPELINE_VERSION,
        "run_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "input_stats": run_meta or {},
        "total_accepted": saas_count,
        "total_rejected": ai_reject_count + rule_reject_count,
        "ai_rejected": ai_reject_count,
        "rule_rejected": rule_reject_count,
        "label_distribution": dict(label_dist),
        "risk_flag_distribution": dict(risk_dist),
        "reject_reason_distribution": dict(reject_reason_dist),
    }
    write_json(OUT_RUN_SUMMARY, summary)
    log.info("Wrote run summary → %s", OUT_RUN_SUMMARY)
