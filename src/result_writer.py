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

import datetime
import json
from collections import Counter
from pathlib import Path

from config import (
    INTER_CONSENSUS,
    OUT_REJECTED_WORDS,
    OUT_RUN_SUMMARY,
    OUT_SAAS_WORDS,
    PIPELINE_VERSION,
)
from utils import get_logger, write_jsonl, write_json

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
    """Produce a clean saas_words.jsonl record from a consensus record."""
    return {
        "word": rec.get("raw_token", rec.get("normalized_word", "")),
        "normalized_word": rec.get("normalized_word", ""),
        "decision": rec.get("decision", "accept"),
        "candidate_modes": rec.get("candidate_modes", []),
        "primary_label": rec.get("primary_label", "ambiguous"),
        "confidence": rec.get("confidence", 0.5),
        "consensus": rec.get("consensus", {"support": 0, "oppose": 0, "abstain": 0}),
        "why_accept": rec.get("why_accept", []),
        "risk_flags": rec.get("risk_flags", []),
        "source_file": rec.get("source_file", ""),
        "source_line": rec.get("source_line", 0),
        "pipeline_version": PIPELINE_VERSION,
    }


def _build_reject_record(rec: dict, reject_reason: list[str] | None = None) -> dict:
    """Produce a clean rejected_words.jsonl record."""
    return {
        "word": rec.get("raw_token", rec.get("normalized_word", "")),
        "normalized_word": rec.get("normalized_word", ""),
        "decision": "reject",
        "reject_reason": reject_reason or rec.get("reject_reason", rec.get("screen_reason", [])),
        "consensus": rec.get("consensus", {"support": 0, "oppose": 0, "abstain": 0}),
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
        decision = rec.get("decision", "reject")
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
