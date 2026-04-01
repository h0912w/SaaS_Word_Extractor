"""
SaaS Word Extractor — Main Pipeline Orchestrator
================================================
Entry point for the full 12-step pipeline.

Usage:
  python src/pipeline.py [options]

Options:
  --resume          Skip steps whose intermediate files already exist.
  --skip-qa         Run steps 1-10 but skip QA (steps 11-12).
  --max-words N     Limit total words entering the AI pipeline (for testing).
  --help            Show this message.

Prerequisites:
  pip install -r requirements.txt
  export ANTHROPIC_API_KEY=<your-key>
  Put word list files in  ./input/  (*.txt / *.jsonl / *.txt.zst / *.csv)
"""

import argparse
import datetime
import sys
import os
from pathlib import Path

# Add src/ to path so imports work when running from project root
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    INPUT_DIR,
    INTERMEDIATE_DIR,
    HUMAN_REVIEW_DIR,
    OUTPUT_DIR,
    QA_DIR,
    PIPELINE_VERSION,
)
from utils import get_logger

log = get_logger("pipeline")


def _ensure_directories():
    for d in [OUTPUT_DIR, INTERMEDIATE_DIR, HUMAN_REVIEW_DIR, QA_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def run_pipeline(resume: bool = False, skip_qa: bool = False, max_words: int = 0):
    _ensure_directories()

    log.info("=" * 60)
    log.info("SaaS Word Extractor  version=%s", PIPELINE_VERSION)
    log.info("resume=%s  skip_qa=%s  max_words=%s",
             resume, skip_qa, max_words or "unlimited")
    log.info("=" * 60)

    start_time = datetime.datetime.utcnow()

    # ------------------------------------------------------------------
    # Step 1 — Input file discovery
    # ------------------------------------------------------------------
    log.info("[Step 1] Input file discovery")
    import input_discovery
    file_descriptors = input_discovery.run(resume=resume)
    supported_files = [f for f in file_descriptors if f.get("supported")]
    log.info("  Found %d supported input file(s)", len(supported_files))

    # ------------------------------------------------------------------
    # Step 2 — File loading & decompression
    # ------------------------------------------------------------------
    log.info("[Step 2] Loading files")
    import input_loader
    loaded_records = input_loader.run(file_descriptors, resume=resume)
    log.info("  Loaded %d raw tokens", len(loaded_records))

    if max_words and len(loaded_records) > max_words:
        log.info("  Limiting to first %d tokens (--max-words)", max_words)
        loaded_records = loaded_records[:max_words]

    # ------------------------------------------------------------------
    # Step 3 — Normalization
    # ------------------------------------------------------------------
    log.info("[Step 3] Token normalization")
    import token_normalizer
    normalized_records = token_normalizer.run(loaded_records, resume=resume)
    log.info("  Normalized %d tokens", len(normalized_records))

    # ------------------------------------------------------------------
    # Step 4 — Rule-based 1st-pass screening
    # ------------------------------------------------------------------
    log.info("[Step 4] Rule-based screening")
    import rule_screener
    passed_records, rule_rejected = rule_screener.run(normalized_records, resume=resume)
    log.info("  Passed: %d  |  Rule-rejected: %d", len(passed_records), len(rule_rejected))

    # ------------------------------------------------------------------
    # Steps 5–8 — AI semantic review (primary → challenge → rebuttal → consensus)
    # ------------------------------------------------------------------
    log.info("[Steps 5-8] AI semantic review pipeline")
    from ai_review import AIReviewer
    reviewer = AIReviewer()

    log.info("[Step 5] Primary AI review (5 judges)")
    primary_results = reviewer.run_primary_review(passed_records, resume=resume)

    log.info("[Step 6] Challenge review (5 challengers)")
    challenged_results = reviewer.run_challenge_review(primary_results, resume=resume)

    log.info("[Step 7] Rebuttal review (3 rebuttal reviewers)")
    rebutted_results = reviewer.run_rebuttal_review(challenged_results, resume=resume)

    log.info("[Step 8] Consensus engine")
    consensus_records = reviewer.run_consensus(rebutted_results, resume=resume)

    accept_n = sum(1 for r in consensus_records if r.get("decision") == "accept")
    reject_n = sum(1 for r in consensus_records if r.get("decision") == "reject")
    log.info("  Consensus: %d accept  |  %d reject", accept_n, reject_n)

    # ------------------------------------------------------------------
    # Step 9 — Result writer (JSONL/JSON)
    # ------------------------------------------------------------------
    log.info("[Step 9] Writing JSONL/JSON results")
    import result_writer
    run_meta = {
        "total_loaded": len(loaded_records),
        "total_normalized": len(normalized_records),
        "total_rule_passed": len(passed_records),
        "total_rule_rejected": len(rule_rejected),
        "total_ai_reviewed": len(consensus_records),
        "start_time": start_time.isoformat() + "Z",
        "end_time": datetime.datetime.utcnow().isoformat() + "Z",
        "input_files": [f["filename"] for f in supported_files],
    }
    saas_records, all_rejected = result_writer.run(consensus_records, rule_rejected, run_meta)
    log.info("  saas_words.jsonl: %d records", len(saas_records))
    log.info("  rejected_words.jsonl: %d records", len(all_rejected))

    # ------------------------------------------------------------------
    # Step 10 — Human review XLSX/CSV
    # ------------------------------------------------------------------
    log.info("[Step 10] Human review export (XLSX/CSV)")
    import human_review_exporter
    human_review_exporter.run(saas_records, all_rejected)

    # ------------------------------------------------------------------
    # Step 11 — QA: same pipeline re-run (entry point reuse)
    # Note: QA uses the final output files, not a separate codebase.
    # ------------------------------------------------------------------
    if skip_qa:
        log.info("[Steps 11-12] QA skipped (--skip-qa)")
    else:
        log.info("[Step 11-12] QA — multi-agent verification of outputs")
        import qa_report_collator
        qa_report_collator.run()

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    elapsed = (datetime.datetime.utcnow() - start_time).total_seconds()
    log.info("=" * 60)
    log.info("Pipeline complete in %.1f seconds", elapsed)
    log.info("Outputs in: %s", OUTPUT_DIR)
    log.info("=" * 60)

    _print_output_summary()


def _print_output_summary():
    from config import (
        OUT_SAAS_WORDS, OUT_REJECTED_WORDS, OUT_RUN_SUMMARY,
        OUT_SAAS_REVIEW_XLSX, OUT_SAAS_REVIEW_CSV, OUT_REJECTED_REVIEW_XLSX,
        OUT_QA_REPORT, OUT_QA_FINDINGS, OUT_QA_DISAGREEMENTS, OUT_QA_HUMAN_REVIEW_XLSX,
    )

    outputs = [
        OUT_SAAS_WORDS, OUT_REJECTED_WORDS, OUT_RUN_SUMMARY,
        OUT_SAAS_REVIEW_XLSX, OUT_SAAS_REVIEW_CSV, OUT_REJECTED_REVIEW_XLSX,
        OUT_QA_REPORT, OUT_QA_FINDINGS, OUT_QA_DISAGREEMENTS, OUT_QA_HUMAN_REVIEW_XLSX,
    ]

    log.info("Output file manifest:")
    for p in outputs:
        status = "OK" if p.exists() else "MISSING"
        size = f"({p.stat().st_size:,} bytes)" if p.exists() else ""
        log.info("  [%s] %s %s", status, p.relative_to(OUTPUT_DIR.parent), size)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SaaS Word Extractor Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last completed step")
    parser.add_argument("--skip-qa", action="store_true",
                        help="Skip QA steps (11-12)")
    parser.add_argument("--max-words", type=int, default=0,
                        help="Limit number of words for testing (0=unlimited)")
    args = parser.parse_args()

    try:
        run_pipeline(
            resume=args.resume,
            skip_qa=args.skip_qa,
            max_words=args.max_words,
        )
    except KeyboardInterrupt:
        log.warning("Pipeline interrupted by user.")
        sys.exit(1)
    except Exception as exc:
        log.error("Pipeline failed: %s", exc, exc_info=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
