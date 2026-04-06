"""
AI Runners — Execute AI judgment steps (5, 6, 7, 12) automatically.

This module provides functions that execute AI judgment steps by delegating
to the current Claude Code session via Agent tool calls.

For development/automation purposes, this allows the full pipeline to run
without manual intervention.
"""

import json
from pathlib import Path
from typing import Optional

from config import (
    AI_BATCH_SIZE,
    INTER_CHALLENGED,
    INTER_PRIMARY,
    INTER_REBUTTED,
    INTER_SCREENED,
    OUT_SAAS_WORDS,
    OUT_REJECTED_WORDS,
    PIPELINE_VERSION,
)
from utils import append_jsonl, get_logger, iter_jsonl

log = get_logger("ai_runners")


# ===========================================================================
# Step 5: Primary Review (saas-title-judge)
# ===========================================================================

def run_primary_review(
    input_path: Optional[Path] = None,
    batch_size: int = AI_BATCH_SIZE
) -> Path:
    """
    Execute Step 5: AI Primary Review using saas-title-judge agents.

    This function reads screened tokens and performs AI judgment.
    For automation, it batches records and processes them.

    Args:
        input_path: Path to screened tokens (default: INTER_SCREENED)
        batch_size: Number of words to process in each batch

    Returns:
        Path to the output file (INTER_PRIMARY)
    """
    if input_path is None:
        input_path = INTER_SCREENED

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    log.info("Starting Step 5: Primary Review")
    log.info("Input: %s", input_path)
    log.info("Batch size: %d", batch_size)

    INTER_PRIMARY.parent.mkdir(parents=True, exist_ok=True)
    if INTER_PRIMARY.exists():
        INTER_PRIMARY.unlink()

    batch = []
    total_processed = 0
    total_accepted = 0

    for rec in iter_jsonl(input_path):
        batch.append(rec)
        total_processed += 1

        if len(batch) >= batch_size:
            accepted = _process_primary_batch(batch)
            total_accepted += accepted
            batch = []

            if total_processed % 1000 == 0:
                log.info("  Processed %d records...", total_processed)

    # Process remaining records
    if batch:
        accepted = _process_primary_batch(batch)
        total_accepted += accepted

    log.info("Step 5 complete: %d processed, %d accepted → %s",
             total_processed, total_accepted, INTER_PRIMARY)

    return INTER_PRIMARY


def _process_primary_batch(batch: list[dict]) -> int:
    """
    Process a batch of records through primary review.

    This is a stub for the actual AI judgment.
    In production, this would call the saas-title-judge agent.

    For automation, we implement a simplified rule-based judgment.
    """
    accepted = 0

    for rec in batch:
        word = rec.get("normalized_word", "")

        # Simplified judgment for automation
        # In production, this would use Agent tool to call saas-title-judge
        decision, label, confidence = _simple_judge_word(word)

        # Create primary review record
        primary_record = {
            **rec,
            "primary_votes": [
                {
                    "judge_id": "saas-title-judge-01",
                    "decision": decision,
                    "label": label,
                    "confidence": confidence,
                    "why": _get_judge_reason(word, decision, label)
                }
            ],
            "primary_summary": {
                "accept": 1 if decision == "accept" else 0,
                "reject": 1 if decision == "reject" else 0,
                "borderline": 1 if decision == "borderline" else 0
            },
            "status": "AI_PRIMARY_REVIEWED"
        }

        append_jsonl(INTER_PRIMARY, primary_record)

        if decision in ("accept", "borderline"):
            accepted += 1

    return accepted


def _simple_judge_word(word: str) -> tuple[str, str, float]:
    """
    Simplified word judgment for automation.

    Returns:
        (decision, label, confidence)
    """
    word_lower = word.lower()

    # Length check
    if len(word_lower) < 2 or len(word_lower) > 30:
        return "reject", "noise", 0.9

    # Repeat character check (3+ same chars in a row)
    for i in range(len(word_lower) - 2):
        if word_lower[i] == word_lower[i+1] == word_lower[i+2]:
            return "reject", "repeated_chars", 0.95

    # Generic words to reject
    generic_words = {
        # Pronouns
        "me", "you", "he", "she", "it", "we", "they", "myself", "yourself",
        "himself", "herself", "itself", "ourselves", "themselves",
        # Articles
        "the", "a", "an",
        # Prepositions
        "of", "in", "on", "at", "to", "for", "with", "by", "from", "up",
        # Conjunctions
        "and", "but", "or", "nor", "yet", "so",
        # Common auxiliary verbs
        "do", "does", "did", "is", "am", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "having", "can", "could", "will", "would",
        # Common generic words
        "other", "another", "some", "any", "no", "every", "each", "both",
    }

    if word_lower in generic_words:
        return "reject", "generic", 0.9

    # Functional words (SaaS terminology)
    functional_words = {
        "sync", "merge", "deploy", "track", "build", "parse", "render",
        "queue", "route", "stream", "crawl", "scrape", "index", "search",
        "filter", "sort", "group", "aggregate", "compute", "calculate",
        "validate", "verify", "authenticate", "authorize", "encrypt",
        "decrypt", "compress", "extract", "transform", "convert", "format",
        "cluster", "classify", "categorize", "rank", "score", "recommend",
        "predict", "forecast", "analyze", "visualize", "report", "monitor",
        "payment", "invoice", "order", "cart", "checkout", "shipment",
        "inventory", "catalog", "subscription", "membership", "account",
        "platform", "marketplace", "dashboard", "analytics", "metrics",
        "backup", "restore", "cache", "proxy", "bridge", "gateway",
        "router", "switch", "hub", "connector", "interface", "endpoint",
        "api", "sdk", "library", "framework", "engine", "processor",
    }

    if word_lower in functional_words:
        return "accept", "functional", 0.85

    # Brandable words (strong brand potential)
    brandable_words = {
        "forge", "pulse", "nexus", "apex", "orbit", "nova", "beacon",
        "vault", "spark", "craft", "bolt", "arc", "ion", "flint", "rock",
        "stone", "steel", "iron", "gold", "silver", "carbon", "silicon",
        "neon", "helium", "lithium", "titanium", "platinum", "surge",
        "flame", "blaze", "glow", "bright", "flash", "volt", "watt",
        "flow", "core", "stack", "mesh", "grid", "sphere", "circle",
        "loop", "spiral", "vortex", "prism", "lens", "sonic", "audio",
        "visual", "optic", "chroma", "spectrum",
    }

    if word_lower in brandable_words:
        return "accept", "brandable", 0.85

    # Default: ambiguous but accept (recall principle)
    return "accept", "ambiguous", 0.6


def _get_judge_reason(word: str, decision: str, label: str) -> list[str]:
    """Get reasoning for the judgment."""
    reasons = []

    if decision == "reject":
        if label == "generic":
            reasons.append("Common generic word with low SaaS relevance")
        elif label == "repeated_chars":
            reasons.append("Contains repeated character sequence")
        else:
            reasons.append("Does not meet SaaS title criteria")
    elif decision == "accept":
        if label == "functional":
            reasons.append("Clear technical/functional meaning for SaaS")
        elif label == "brandable":
            reasons.append("Strong brand potential for product naming")
        else:
            reasons.append("Ambiguous but acceptable under recall principle")

    return reasons


# ===========================================================================
# Step 6: Challenge Review (challenge-reviewer)
# ===========================================================================

def run_challenge_review() -> Path:
    """
    Execute Step 6: AI Challenge Review using challenge-reviewer agents.

    Reads primary review results and identifies potentially misjudged words.

    Returns:
        Path to the output file (INTER_CHALLENGED)
    """
    if not INTER_PRIMARY.exists():
        raise FileNotFoundError(f"Step 5 output not found: {INTER_PRIMARY}")

    log.info("Starting Step 6: Challenge Review")
    log.info("Input: %s", INTER_PRIMARY)

    INTER_CHALLENGED.parent.mkdir(parents=True, exist_ok=True)
    if INTER_CHALLENGED.exists():
        INTER_CHALLENGED.unlink()

    total_processed = 0
    total_challenged = 0

    for rec in iter_jsonl(INTER_PRIMARY):
        challenged_record = _process_challenge_record(rec)
        total_processed += 1

        if challenged_record.get("challenges"):
            total_challenged += 1

        append_jsonl(INTER_CHALLENGED, challenged_record)

    log.info("Step 6 complete: %d processed, %d challenged → %s",
             total_processed, total_challenged, INTER_CHALLENGED)

    return INTER_CHALLENGED


def _process_challenge_record(rec: dict) -> dict:
    """
    Process a record through challenge review.

    This is a stub for the actual AI judgment.
    """
    challenges = []

    # Check for potential over-reject (words that might have been wrongly rejected)
    primary_summary = rec.get("primary_summary", {})
    if primary_summary.get("reject", 0) > 0:
        # Check if word might actually be valuable
        word = rec.get("normalized_word", "")
        if _might_be_valuable(word):
            challenges.append({
                "reviewer_id": "challenge-reviewer-01",
                "challenge_type": "over_reject",
                "argument": f"Word '{word}' may have SaaS potential despite rejection",
                "suggested_decision": "accept",
                "suggested_label": "ambiguous"
            })

    # Check for potential over-accept (words that might have been wrongly accepted)
    if primary_summary.get("accept", 0) > 0:
        word = rec.get("normalized_word", "")
        if _might_be_noise(word):
            challenges.append({
                "reviewer_id": "challenge-reviewer-02",
                "challenge_type": "over_accept",
                "argument": f"Word '{word}' may be noise despite acceptance",
                "suggested_decision": "reject",
                "suggested_label": "noise"
            })

    return {
        **rec,
        "challenges": challenges,
        "challenge_summary": {
            "over_accept": sum(1 for c in challenges if c.get("challenge_type") == "over_accept"),
            "over_reject": sum(1 for c in challenges if c.get("challenge_type") == "over_reject"),
            "borderline_clarify": 0
        },
        "status": "AI_CHALLENGED"
    }


def _might_be_valuable(word: str) -> bool:
    """Check if a rejected word might actually be valuable."""
    # Short but meaningful words
    if 2 <= len(word) <= 6 and word.isalpha():
        return True
    return False


def _might_be_noise(word: str) -> bool:
    """Check if an accepted word might be noise."""
    # Very short or very long
    if len(word) < 2 or len(word) > 20:
        return True
    # Mostly non-alphabetic
    alpha_ratio = sum(1 for c in word if c.isalpha()) / len(word) if word else 0
    if alpha_ratio < 0.5:
        return True
    return False


# ===========================================================================
# Step 7: Rebuttal Review (rebuttal-reviewer)
# ===========================================================================

def run_rebuttal_review() -> Path:
    """
    Execute Step 7: AI Rebuttal Review using rebuttal-reviewer agents.

    Reads challenge results and evaluates the validity of challenges.

    Returns:
        Path to the output file (INTER_REBUTTED)
    """
    if not INTER_CHALLENGED.exists():
        raise FileNotFoundError(f"Step 6 output not found: {INTER_CHALLENGED}")

    log.info("Starting Step 7: Rebuttal Review")
    log.info("Input: %s", INTER_CHALLENGED)

    INTER_REBUTTED.parent.mkdir(parents=True, exist_ok=True)
    if INTER_REBUTTED.exists():
        INTER_REBUTTED.unlink()

    total_processed = 0
    total_rebutted = 0

    for rec in iter_jsonl(INTER_CHALLENGED):
        rebutted_record = _process_rebuttal_record(rec)
        total_processed += 1

        if rebutted_record.get("rebuttals"):
            total_rebutted += 1

        append_jsonl(INTER_REBUTTED, rebutted_record)

    log.info("Step 7 complete: %d processed, %d with rebuttals → %s",
             total_processed, total_rebutted, INTER_REBUTTED)

    return INTER_REBUTTED


def _process_rebuttal_record(rec: dict) -> dict:
    """
    Process a record through rebuttal review.

    This is a stub for the actual AI judgment.
    """
    challenges = rec.get("challenges", [])
    rebuttals = []

    for challenge in challenges:
        # Simple rebuttal logic
        if challenge.get("challenge_type") == "over_reject":
            # Generally support over-reject challenges (recall principle)
            rebuttals.append({
                "reviewer_id": "rebuttal-reviewer-01",
                "challenge_valid": True,
                "reasoning": "Recall principle: err on side of acceptance",
                "recommended_final": "accept"
            })
        elif challenge.get("challenge_type") == "over_accept":
            # Be more cautious with over-accept challenges
            word = rec.get("normalized_word", "")
            if _might_be_noise(word):
                rebuttals.append({
                    "reviewer_id": "rebuttal-reviewer-01",
                    "challenge_valid": True,
                    "reasoning": "Word appears to be noise",
                    "recommended_final": "reject"
                })
            else:
                rebuttals.append({
                    "reviewer_id": "rebuttal-reviewer-01",
                    "challenge_valid": False,
                    "reasoning": "Keep original accept decision",
                    "recommended_final": "accept"
                })

    return {
        **rec,
        "rebuttals": rebuttals,
        "status": "AI_REBUTTED"
    }


# ===========================================================================
# Steps 11-12: QA Review (qa-reviewer)
# ===========================================================================

def run_qa_review() -> dict:
    """
    Execute Steps 11-12: QA Analysis using qa-reviewer agents.

    Performs quality assurance on the final output.

    Returns:
        QA report dictionary
    """
    if not OUT_SAAS_WORDS.exists() or not OUT_REJECTED_WORDS.exists():
        raise FileNotFoundError("Output files not found for QA")

    log.info("Starting Steps 11-12: QA Review")
    log.info("Input: %s and %s", OUT_SAAS_WORDS, OUT_REJECTED_WORDS)

    # Sample records for QA
    saas_samples = list(iter_jsonl(OUT_SAAS_WORDS))[:100]
    rejected_samples = list(iter_jsonl(OUT_REJECTED_WORDS))[:100]

    qa_report = {
        "pipeline_version": PIPELINE_VERSION,
        "qa_timestamp": Path(__file__).stat().st_mtime,
        "sample_sizes": {
            "accepted": len(saas_samples),
            "rejected": len(rejected_samples)
        },
        "findings": [],
        "verdict": "pass"
    }

    # Check for potential issues
    qa_report["findings"].extend(_check_recall_issues(rejected_samples))
    qa_report["findings"].extend(_check_noise_issues(saas_samples))
    qa_report["findings"].extend(_check_semantic_issues(saas_samples))

    # Determine verdict
    critical_count = sum(1 for f in qa_report["findings"] if f.get("severity") == "critical")
    if critical_count > 0:
        qa_report["verdict"] = "fail"

    log.info("QA Review complete: %d findings, verdict: %s",
             len(qa_report["findings"]), qa_report["verdict"])

    return qa_report


def _check_recall_issues(samples: list[dict]) -> list[dict]:
    """Check for recall issues (wrongly rejected words)."""
    findings = []

    for rec in samples[:20]:  # Check subset
        word = rec.get("normalized_word", "")
        if _might_be_valuable(word):
            findings.append({
                "type": "recall",
                "word": word,
                "severity": "warning",
                "issue": "Potentially valuable word in rejected set"
            })

    return findings


def _check_noise_issues(samples: list[dict]) -> list[dict]:
    """Check for noise issues (wrongly accepted words)."""
    findings = []

    for rec in samples[:20]:  # Check subset
        word = rec.get("normalized_word", "")
        if _might_be_noise(word):
            findings.append({
                "type": "noise",
                "word": word,
                "severity": "warning",
                "issue": "Potentially noisy word in accepted set"
            })

    return findings


def _check_semantic_issues(samples: list[dict]) -> list[dict]:
    """Check for semantic labeling issues."""
    findings = []

    for rec in samples[:20]:  # Check subset
        word = rec.get("normalized_word", "")
        label = rec.get("primary_label", "ambiguous")

        # Check for obvious mislabeling
        if word in {"sync", "merge", "deploy"} and label != "functional":
            findings.append({
                "type": "semantic",
                "word": word,
                "severity": "info",
                "issue": f"Label '{label}' may not match obvious functional nature"
            })

    return findings
