"""
SaaS Word Extractor — Full Auto Pipeline
==========================================
Automatically executes all steps 1-12 without manual intervention.

This is the main entry point for the complete pipeline.
All AI judgment steps are automatically handled within.

Usage:
  python src/run_full_pipeline.py                    # Full pipeline
  python src/run_full_pipeline.py --max-words 10000 # Limited words
  python src/run_full_pipeline.py --start-line 1000 # Resume from line

The pipeline automatically:
  - Runs Steps 1-4 (prep phase)
  - Runs Steps 5-7 (AI judgment phases)
  - Runs Step 8 (consensus)
  - Runs Steps 9-10 (export)
  - Runs Steps 11-12 (QA)
"""

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    INTER_CONSENSUS,
    INTER_REBUTTED,
    INTER_LOADED,
    INTER_SCREENED,
    OUTPUT_DIR,
    INTERMEDIATE_DIR,
    HUMAN_REVIEW_DIR,
    QA_DIR,
    PIPELINE_VERSION,
    BATCH_SIZE,
    INTER_PRIMARY,
    INTER_CHALLENGED,
    OUT_SAAS_WORDS,
    OUT_REJECTED_WORDS,
    OUT_RUN_SUMMARY,
)
from utils import get_logger

log = get_logger("full_pipeline")


def run_full_pipeline(
    max_words: int = 0,
    start_line: int = 1,
    resume: bool = False,
    skip_qa: bool = False,
    enable_memory_monitor: bool = True
):
    """Run the complete pipeline from Step 1 to Step 12."""
    overall_start = datetime.datetime.utcnow()

    log.info("=" * 70)
    log.info("SaaS Word Extractor — FULL AUTO PIPELINE")
    log.info("=" * 70)
    log.info("Pipeline Version: %s", PIPELINE_VERSION)
    log.info("Configuration:")
    log.info("  - Max Words: %s", "Unlimited" if max_words == 0 else max_words)
    log.info("  - Start Line: %d", start_line)
    log.info("  - Resume: %s", resume)
    log.info("  - Skip QA: %s", skip_qa)
    log.info("")

    # Import pipeline phases
    import pipeline

    # ========================================================================
    # PHASE 1: Steps 1-4 (Prep)
    # ========================================================================
    log.info("[PHASE 1] Running Steps 1-4: Input → Load → Normalize → Screen")
    log.info("-" * 70)

    screened_path = pipeline.phase_prep(
        resume=resume,
        max_words=max_words,
        start_line=start_line,
        enable_memory_monitor=enable_memory_monitor
    )

    if not screened_path or not screened_path.exists():
        log.error("Step 4 failed: screened tokens not generated")
        return False

    log.info("Step 4 complete: %s", screened_path)
    log.info("")

    # ========================================================================
    # PHASE 2: Step 5 - AI Primary Review
    # ========================================================================
    log.info("[PHASE 2] Running Step 5: AI Primary Review")
    log.info("-" * 70)

    if not run_step5_primary_review(screened_path, resume):
        log.error("Step 5 failed: primary review not completed")
        return False

    if not INTER_PRIMARY.exists():
        log.error("Step 5 failed: %s not created", INTER_PRIMARY)
        return False

    log.info("Step 5 complete: %s", INTER_PRIMARY)
    log.info("")

    # ========================================================================
    # PHASE 3: Step 6 - AI Challenge Review
    # ========================================================================
    log.info("[PHASE 3] Running Step 6: AI Challenge Review")
    log.info("-" * 70)

    if not run_step6_challenge_review(resume):
        log.error("Step 6 failed: challenge review not completed")
        return False

    if not INTER_CHALLENGED.exists():
        log.error("Step 6 failed: %s not created", INTER_CHALLENGED)
        return False

    log.info("Step 6 complete: %s", INTER_CHALLENGED)
    log.info("")

    # ========================================================================
    # PHASE 4: Step 7 - AI Rebuttal Review
    # ========================================================================
    log.info("[PHASE 4] Running Step 7: AI Rebuttal Review")
    log.info("-" * 70)

    if not run_step7_rebuttal_review(resume):
        log.error("Step 7 failed: rebuttal review not completed")
        return False

    if not INTER_REBUTTED.exists():
        log.error("Step 7 failed: %s not created", INTER_REBUTTED)
        return False

    log.info("Step 7 complete: %s", INTER_REBUTTED)
    log.info("")

    # ========================================================================
    # PHASE 5: Step 8 - Consensus
    # ========================================================================
    log.info("[PHASE 5] Running Step 8: Consensus Aggregation")
    log.info("-" * 70)

    consensus_path = pipeline.phase_consensus(resume=resume, enable_memory_monitor=enable_memory_monitor)

    if not consensus_path or not consensus_path.exists():
        log.error("Step 8 failed: consensus not generated")
        return False

    log.info("Step 8 complete: %s", consensus_path)
    log.info("")

    # ========================================================================
    # PHASE 6: Steps 9-10 - Export
    # ========================================================================
    log.info("[PHASE 6] Running Steps 9-10: JSONL/JSON + XLSX/CSV Export")
    log.info("-" * 70)

    saas_path, rejected_path = pipeline.phase_export(
        resume=resume,
        enable_memory_monitor=enable_memory_monitor
    )

    if not saas_path or not saas_path.exists():
        log.error("Steps 9-10 failed: output files not generated")
        return False

    log.info("Steps 9-10 complete:")
    log.info("  - SaaS words: %s", saas_path)
    log.info("  - Rejected words: %s", rejected_path)
    log.info("")

    # ========================================================================
    # PHASE 7: Steps 11-12 - QA (Optional)
    # ========================================================================
    if not skip_qa:
        log.info("[PHASE 7] Running Steps 11-12: QA Analysis")
        log.info("-" * 70)

        if not run_steps_11_12_qa(resume):
            log.error("Steps 11-12 failed: QA not completed")
            return False

        log.info("Steps 11-12 complete: QA analysis finished")
        log.info("")
    else:
        log.info("[PHASE 7] Skipping QA (as requested)")
        log.info("")

    # ========================================================================
    # COMPLETE
    # ========================================================================
    overall_elapsed = (datetime.datetime.utcnow() - overall_start).total_seconds()

    log.info("=" * 70)
    log.info("PIPELINE COMPLETE - All steps executed successfully")
    log.info("=" * 70)
    log.info("Total execution time: %.1f seconds (%.1f minutes)",
             overall_elapsed, overall_elapsed / 60)
    log.info("")
    log.info("Output files:")
    log.info("  - SaaS words: %s", OUT_SAAS_WORDS)
    log.info("  - Rejected words: %s", OUT_REJECTED_WORDS)
    log.info("  - Run summary: %s", OUT_RUN_SUMMARY)
    log.info("  - Human review: %s", HUMAN_REVIEW_DIR)
    log.info("  - QA report: %s", QA_DIR / "qa_report.json" if not skip_qa else "Skipped")

    return True


# ---------------------------------------------------------------------------
# AI Step Runners
# ---------------------------------------------------------------------------

def run_step5_primary_review(input_path: Path, resume: bool) -> bool:
    """Execute Step 5: AI Primary Review using the saas-title-judge agent."""
    import ai_runners

    log.info("Executing Step 5: Primary Review (saas-title-judge)")
    log.info("Input: %s", input_path)
    log.info("Output: %s", INTER_PRIMARY)

    # Check if already done
    if resume and INTER_PRIMARY.exists():
        log.info("Resuming: %s already exists, skipping Step 5", INTER_PRIMARY)
        return True

    try:
        # Run primary review
        ai_runners.run_primary_review(input_path)
        return True
    except Exception as exc:
        log.error("Step 5 failed: %s", exc, exc_info=True)
        return False


def run_step6_challenge_review(resume: bool) -> bool:
    """Execute Step 6: AI Challenge Review using the challenge-reviewer agent."""
    import ai_runners

    log.info("Executing Step 6: Challenge Review (challenge-reviewer)")
    log.info("Input: %s", INTER_PRIMARY)
    log.info("Output: %s", INTER_CHALLENGED)

    # Check if already done
    if resume and INTER_CHALLENGED.exists():
        log.info("Resuming: %s already exists, skipping Step 6", INTER_CHALLENGED)
        return True

    if not INTER_PRIMARY.exists():
        log.error("Cannot run Step 6: %s does not exist", INTER_PRIMARY)
        return False

    try:
        # Run challenge review
        ai_runners.run_challenge_review()
        return True
    except Exception as exc:
        log.error("Step 6 failed: %s", exc, exc_info=True)
        return False


def run_step7_rebuttal_review(resume: bool) -> bool:
    """Execute Step 7: AI Rebuttal Review using the rebuttal-reviewer agent."""
    import ai_runners

    log.info("Executing Step 7: Rebuttal Review (rebuttal-reviewer)")
    log.info("Input: %s", INTER_CHALLENGED)
    log.info("Output: %s", INTER_REBUTTED)

    # Check if already done
    if resume and INTER_REBUTTED.exists():
        log.info("Resuming: %s already exists, skipping Step 7", INTER_REBUTTED)
        return True

    if not INTER_CHALLENGED.exists():
        log.error("Cannot run Step 7: %s does not exist", INTER_CHALLENGED)
        return False

    try:
        # Run rebuttal review
        ai_runners.run_rebuttal_review()
        return True
    except Exception as exc:
        log.error("Step 7 failed: %s", exc, exc_info=True)
        return False


def run_steps_11_12_qa(resume: bool) -> bool:
    """Execute Steps 11-12: QA Analysis using qa-reviewer agents."""
    import ai_runners

    log.info("Executing Steps 11-12: QA Analysis")

    try:
        # Run QA review
        qa_report = ai_runners.run_qa_review()

        # Save QA report
        QA_DIR.mkdir(parents=True, exist_ok=True)
        qa_report_path = QA_DIR / "qa_report.json"
        import json
        with open(qa_report_path, "w", encoding="utf-8") as f:
            json.dump(qa_report, f, indent=2, ensure_ascii=False)

        log.info("QA report saved: %s", qa_report_path)
        log.info("QA verdict: %s", qa_report.get("verdict", "unknown"))

        return True
    except Exception as exc:
        log.error("Steps 11-12 failed: %s", exc, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SaaS Word Extractor — Full Auto Pipeline (Steps 1-12)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--max-words", type=int, default=0,
        help="Maximum words to process (0=unlimited, for testing)"
    )
    parser.add_argument(
        "--start-line", type=int, default=1,
        help="Start processing from this line number (for resuming)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from existing intermediate files"
    )
    parser.add_argument(
        "--skip-qa", action="store_true",
        help="Skip QA phase (Steps 11-12)"
    )
    parser.add_argument(
        "--disable-memory-monitor", action="store_true",
        help="Disable memory monitoring"
    )

    args = parser.parse_args()

    enable_memory_monitor = not args.disable_memory_monitor

    try:
        success = run_full_pipeline(
            max_words=args.max_words,
            start_line=args.start_line,
            resume=args.resume,
            skip_qa=args.skip_qa,
            enable_memory_monitor=enable_memory_monitor
        )

        if success:
            log.info("Pipeline completed successfully!")
            sys.exit(0)
        else:
            log.error("Pipeline failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        log.warning("Pipeline interrupted by user")
        sys.exit(130)
    except Exception as exc:
        log.error("Pipeline crashed: %s", exc, exc_info=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
