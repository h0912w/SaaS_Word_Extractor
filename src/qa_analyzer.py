#!/usr/bin/env python3
"""
QA Analyzer
===========
Performs quality assurance analysis on the pipeline output.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import Counter
from utils import get_logger, read_jsonl, write_jsonl

log = get_logger("qa_analyzer")

# File paths
OUTPUT_SAAS = Path("output/saas_words.jsonl")
OUTPUT_REJECTED = Path("output/rejected_words.jsonl")
OUTPUT_SUMMARY = Path("output/run_summary.json")
QA_DIR = Path("output/qa")
QA_REPORT = QA_DIR / "qa_report.json"
QA_FINDINGS = QA_DIR / "qa_findings.jsonl"
QA_DISAGREEMENTS = QA_DIR / "qa_disagreements.jsonl"
QA_CHIEF_VERDICT = QA_DIR / "qa_chief_verdict.json"

# Profanity list for verification
PROFANITY_LIST = {
    'fuck', 'shit', 'damn', 'hell', 'bitch', 'bastard', 'ass',
    'dick', 'piss', 'crap', 'suck', 'cock', 'pussy', 'whore',
    'slut', 'fag', 'nigga', 'nigger'
}

# Generic words that should be rejected
GENERIC_WORDS = {
    'me', 'you', 'he', 'she', 'it', 'we', 'they', 'this', 'that',
    'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
    'and', 'but', 'or', 'is', 'are', 'was', 'were', 'be', 'been',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'can',
}

def load_outputs() -> Tuple[List[Dict], List[Dict], Dict]:
    """Load output files."""
    log.info("Loading output files...")

    saas_words = read_jsonl(OUTPUT_SAAS)
    rejected_words = read_jsonl(OUTPUT_REJECTED)

    with open(OUTPUT_SUMMARY, 'r', encoding='utf-8') as f:
        summary = json.load(f)

    log.info("  Loaded %d SaaS words", len(saas_words))
    log.info("  Loaded %d rejected words", len(rejected_words))

    return saas_words, rejected_words, summary

def check_profanity_filtering(saas_words: List[Dict], rejected_words: List[Dict]) -> Dict[str, Any]:
    """Check if profanity was properly filtered."""
    log.info("Checking profanity filtering...")

    findings = []
    profanity_in_saas = []
    profanity_in_rejected = []

    # Check SaaS words for profanity
    for word_record in saas_words:
        word = word_record.get("normalized_word", "").lower()
        for profanity in PROFANITY_LIST:
            if profanity in word:
                profanity_in_saas.append({
                    "word": word,
                    "profanity_found": profanity,
                    "severity": "HIGH",
                    "issue": "Profanity should be rejected"
                })
                break

    # Check rejected words for profanity
    for word_record in rejected_words:
        word = word_record.get("normalized_word", "").lower()
        for profanity in PROFANITY_LIST:
            if profanity in word:
                profanity_in_rejected.append({
                    "word": word,
                    "profanity_found": profanity,
                    "correctly_rejected": True
                })
                break

    result = {
        "check_name": "profanity_filtering",
        "status": "FAIL" if profanity_in_saas else "PASS",
        "profanity_in_saas_count": len(profanity_in_saas),
        "profanity_in_rejected_count": len(profanity_in_rejected),
        "profanity_in_saas": profanity_in_saas[:10],  # First 10
        "profanity_in_rejected": profanity_in_rejected[:10],
        "details": f"Found {len(profanity_in_saas)} profanity words in SaaS output, {len(profanity_in_rejected)} in rejected"
    }

    findings.append(result)
    log.info("  Status: %s - %s", result["status"], result["details"])
    return result

def check_generic_words_filtering(saas_words: List[Dict], rejected_words: List[Dict]) -> Dict[str, Any]:
    """Check if generic words were properly filtered."""
    log.info("Checking generic words filtering...")

    generic_in_saas = []

    # Check SaaS words for generic words
    for word_record in saas_words:
        word = word_record.get("normalized_word", "").lower()
        if word in GENERIC_WORDS:
            generic_in_saas.append({
                "word": word,
                "severity": "MEDIUM",
                "issue": "Generic word should be rejected"
            })

    result = {
        "check_name": "generic_words_filtering",
        "status": "FAIL" if generic_in_saas else "PASS",
        "generic_in_saas_count": len(generic_in_saas),
        "generic_in_saas": generic_in_saas[:20],
        "details": f"Found {len(generic_in_saas)} generic words in SaaS output"
    }

    log.info("  Status: %s - %s", result["status"], result["details"])
    return result

def check_label_distribution(saas_words: List[Dict]) -> Dict[str, Any]:
    """Check label distribution for balance."""
    log.info("Checking label distribution...")

    label_counts = Counter()
    for word_record in saas_words:
        labels = word_record.get("candidate_modes", [])
        if labels:
            primary_label = labels[0]
            label_counts[primary_label] += 1

    total = sum(label_counts.values())
    distribution = {
        label: {
            "count": count,
            "percentage": round(count / total * 100, 2) if total > 0 else 0
        }
        for label, count in label_counts.items()
    }

    # Check if distribution is reasonable (not too skewed)
    max_percentage = max(d["percentage"] for d in distribution.values()) if distribution else 0
    status = "PASS" if max_percentage < 90 else "WARN"  # No single category should dominate > 90%

    result = {
        "check_name": "label_distribution",
        "status": status,
        "total_words": total,
        "distribution": dict(distribution),
        "max_percentage": max_percentage,
        "details": f"Label distribution: functional, brandable, ambiguous"
    }

    log.info("  Status: %s", result["status"])
    for label, stats in distribution.items():
        log.info("    %s: %d (%.1f%%)", label, stats["count"], stats["percentage"])

    return result

def check_data_consistency(saas_words: List[Dict], rejected_words: List[Dict]) -> Dict[str, Any]:
    """Check data consistency between outputs."""
    log.info("Checking data consistency...")

    issues = []

    # Check for duplicate normalized words in accepted
    accepted_words = [w.get("normalized_word") for w in saas_words]
    duplicates = [word for word, count in Counter(accepted_words).items() if count > 1]

    if duplicates:
        issues.append({
            "type": "duplicate_accepted_words",
            "count": len(duplicates),
            "examples": duplicates[:5]
        })

    # Check for required fields
    required_fields_saas = ["word", "normalized_word", "decision", "candidate_modes", "consensus"]
    required_fields_rejected = ["word", "normalized_word", "decision", "consensus"]

    missing_fields_saas = []
    for i, record in enumerate(saas_words):
        for field in required_fields_saas:
            if field not in record:
                missing_fields_saas.append(f"Record {i} missing field: {field}")

    missing_fields_rejected = []
    for i, record in enumerate(rejected_words):
        for field in required_fields_rejected:
            if field not in record:
                missing_fields_rejected.append(f"Record {i} missing field: {field}")

    if missing_fields_saas:
        issues.append({
            "type": "missing_fields_in_saas",
            "count": len(missing_fields_saas),
            "examples": missing_fields_saas[:5]
        })

    if missing_fields_rejected:
        issues.append({
            "type": "missing_fields_in_rejected",
            "count": len(missing_fields_rejected),
            "examples": missing_fields_rejected[:5]
        })

    status = "PASS" if not issues else "FAIL"

    result = {
        "check_name": "data_consistency",
        "status": status,
        "issues_count": len(issues),
        "issues": issues,
        "details": f"Found {len(issues)} consistency issues"
    }

    log.info("  Status: %s - %s", result["status"], result["details"])
    return result

def check_pipeline_summary(saas_words: List[Dict], rejected_words: List[Dict], summary: Dict) -> Dict[str, Any]:
    """Check if pipeline summary is accurate."""
    log.info("Checking pipeline summary...")

    actual_saas_count = len(saas_words)
    actual_rejected_count = len(rejected_words)
    # Use the correct field names from run_summary.json
    summary_saas_count = summary.get("total_accepted", summary.get("total_saas_words", 0))
    summary_rejected_count = summary.get("total_rejected", summary.get("total_rejected_words", 0))

    mismatches = []
    if actual_saas_count != summary_saas_count:
        mismatches.append(f"SaaS count mismatch: actual={actual_saas_count}, summary={summary_saas_count}")

    if actual_rejected_count != summary_rejected_count:
        mismatches.append(f"Rejected count mismatch: actual={actual_rejected_count}, summary={summary_rejected_count}")

    status = "PASS" if not mismatches else "FAIL"

    result = {
        "check_name": "pipeline_summary",
        "status": status,
        "actual_saas_count": actual_saas_count,
        "summary_saas_count": summary_saas_count,
        "actual_rejected_count": actual_rejected_count,
        "summary_rejected_count": summary_rejected_count,
        "mismatches": mismatches,
        "details": f"Summary verification: {len(mismatches)} mismatches found"
    }

    log.info("  Status: %s", result["status"])
    if mismatches:
        for mismatch in mismatches:
            log.warning("    %s", mismatch)

    return result

def calculate_final_verdict(checks: List[Dict[str, Any]]) -> str:
    """Calculate final QA verdict."""
    # Count status
    status_counts = Counter(check["status"] for check in checks)

    # FAIL if any critical check fails
    critical_checks = ["profanity_filtering", "data_consistency"]
    for check in checks:
        if check["check_name"] in critical_checks and check["status"] == "FAIL":
            return "FAIL"

    # WARN if any check warns
    if status_counts.get("WARN", 0) > 0:
        return "WARN"

    # PASS if all checks pass
    if status_counts.get("PASS", 0) == len(checks):
        return "PASS"

    return "WARN"

def generate_qa_report(saas_words: List[Dict], rejected_words: List[Dict], summary: Dict) -> Dict[str, Any]:
    """Generate comprehensive QA report."""
    log.info("=" * 60)
    log.info("GENERATING QA REPORT")
    log.info("=" * 60)

    checks = []

    # Run all checks
    checks.append(check_profanity_filtering(saas_words, rejected_words))
    checks.append(check_generic_words_filtering(saas_words, rejected_words))
    checks.append(check_label_distribution(saas_words))
    checks.append(check_data_consistency(saas_words, rejected_words))
    checks.append(check_pipeline_summary(saas_words, rejected_words, summary))

    # Calculate final verdict
    final_verdict = calculate_final_verdict(checks)

    # Generate report
    report = {
        "qa_timestamp": summary.get("export_time", "unknown"),
        "pipeline_version": summary.get("pipeline_version", "unknown"),
        "final_verdict": final_verdict,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c["status"] == "PASS"),
        "failed_checks": sum(1 for c in checks if c["status"] == "FAIL"),
        "warned_checks": sum(1 for c in checks if c["status"] == "WARN"),
        "checks": checks,
        "summary": {
            "total_saas_words": len(saas_words),
            "total_rejected_words": len(rejected_words),
            "profanity_in_saas": checks[0]["profanity_in_saas_count"],
            "profanity_correctly_rejected": checks[0]["profanity_in_rejected_count"],
            "label_distribution": checks[2]["distribution"]
        }
    }

    # Save report
    QA_DIR.mkdir(parents=True, exist_ok=True)

    with open(QA_REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    # Save findings as JSONL
    findings = []
    for check in checks:
        if check["status"] in ["FAIL", "WARN"]:
            findings.append({
                "check_name": check["check_name"],
                "status": check["status"],
                "details": check["details"]
            })

    if findings:
        write_jsonl(QA_FINDINGS, findings)

    # Save chief verdict
    chief_verdict = {
        "verdict": final_verdict,
        "timestamp": report["qa_timestamp"],
        "total_saas_words": len(saas_words),
        "total_rejected_words": len(rejected_words),
        "profanity_filtering": checks[0]["status"],
        "profanity_correctly_rejected": checks[0]["profanity_in_rejected_count"],
        "generic_words_filtering": checks[1]["status"],
        "data_consistency": checks[3]["status"],
        "recommendation": (
            "Pipeline output is acceptable for production use." if final_verdict == "PASS" else
            "Pipeline output needs review before use." if final_verdict == "WARN" else
            "Pipeline output has critical issues that must be resolved."
        )
    }

    with open(QA_CHIEF_VERDICT, 'w', encoding='utf-8') as f:
        json.dump(chief_verdict, f, indent=2)

    # Print summary
    log.info("")
    log.info("QA REPORT SUMMARY")
    log.info("-" * 60)
    log.info("Final Verdict: %s", final_verdict)
    log.info("Total Checks: %d", len(checks))
    log.info("Passed: %d", report["passed_checks"])
    log.info("Failed: %d", report["failed_checks"])
    log.info("Warned: %d", report["warned_checks"])
    log.info("")
    log.info("Key Findings:")
    log.info("  - SaaS words: %d", len(saas_words))
    log.info("  - Rejected words: %d", len(rejected_words))
    log.info("  - Profanity correctly rejected: %d", checks[0]["profanity_in_rejected_count"])
    log.info("  - Profanity in SaaS output: %d", checks[0]["profanity_in_saas_count"])
    log.info("  - Generic words in SaaS output: %d", checks[1]["generic_in_saas_count"])
    log.info("")
    log.info("Files saved:")
    log.info("  - %s", QA_REPORT)
    log.info("  - %s", QA_CHIEF_VERDICT)
    if findings:
        log.info("  - %s", QA_FINDINGS)

    return report

def main():
    """Main entry point."""
    log.info("=" * 60)
    log.info("QA ANALYZER")
    log.info("=" * 60)

    # Load outputs
    saas_words, rejected_words, summary = load_outputs()

    # Generate QA report
    report = generate_qa_report(saas_words, rejected_words, summary)

    log.info("")
    log.info("QA analysis complete!")

if __name__ == "__main__":
    main()
