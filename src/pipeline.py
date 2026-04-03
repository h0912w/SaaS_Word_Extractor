"""
SaaS Word Extractor — Pipeline Script
======================================
Python script 담당 단계만 실행한다. AI 판정(Steps 5-8)은
Claude Code 세션이 직접 수행한다.

사용법:
  python src/pipeline.py --phase prep    # Steps 1-4: 파일 탐색·로드·정규화·규칙 스크리닝
  python src/pipeline.py --phase consensus  # Step 8 투표 집계 (Steps 5-7 완료 후)
  python src/pipeline.py --phase export  # Steps 9-10: JSONL/JSON·XLSX/CSV 저장
  python src/pipeline.py --phase qa      # Step 12: QA 리포트 조립

전체 파이프라인 실행 순서:
  1. python src/pipeline.py --phase prep
  2. Claude Code 세션이 Steps 5-7 수행
       (output/intermediate/04 → 05 → 06 → 07)
  3. python src/pipeline.py --phase consensus
  4. python src/pipeline.py --phase export
  5. Claude Code 세션이 Step 12 QA 판정 수행
  6. python src/pipeline.py --phase qa

옵션:
  --resume      이미 존재하는 중간 파일이 있으면 해당 단계 건너뜀
  --max-words N prep 단계에서 처리할 최대 단어 수 (테스트용)
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
)
from utils import get_logger

log = get_logger("pipeline")


def _ensure_dirs():
    for d in [OUTPUT_DIR, INTERMEDIATE_DIR, HUMAN_REVIEW_DIR, QA_DIR]:
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Phase: prep  (Steps 1-4)
# ---------------------------------------------------------------------------

def phase_prep(resume: bool = False, max_words: int = 0, enable_memory_monitor: bool = True):
    log.info("=" * 60)
    log.info("Phase: PREP  (Steps 1-4)")
    log.info("=" * 60)
    _ensure_dirs()

    # Start memory monitoring
    monitor = None
    if enable_memory_monitor:
        try:
            from memory_monitor import MemoryMonitor
            monitor = MemoryMonitor(threshold_mb=2048, phase_name="PREP (Steps 1-4)")
            monitor.start()
        except ImportError:
            log.warning("memory_monitor module not available, skipping memory monitoring")

    try:
        import input_discovery
        import input_loader
        import token_normalizer
        import rule_screener

        # Step 1
        log.info("[Step 1] Input file discovery")
        file_descriptors = input_discovery.run(resume=resume)
        supported = [f for f in file_descriptors if f.get("supported")]
        log.info("  %d supported file(s) found", len(supported))

        # Step 2
        log.info("[Step 2] Loading files (streaming mode)")
        # Don't load into memory - just process to file directly
        input_loader.run(file_descriptors, resume=resume, max_lines=max_words)
        log.info("  Loaded tokens written to file")

        # Step 3+4: Process normalization and screening in streaming mode
        log.info("[Step 3-4] Normalization and screening (streaming mode)")
        _normalize_and_screen_streaming(monitor)

        # Clean up loaded tokens file to save disk space
        if INTER_LOADED.exists():
            try:
                INTER_LOADED.unlink()
                log.info("  Cleaned up loaded tokens (freed disk space)")
            except PermissionError:
                log.warning("  Cannot clean up loaded tokens file (locked)")

        log.info("")
        log.info("Prep phase complete (streaming mode).")
        log.info("Next: Run AI review phase")

        return INTER_SCREENED  # Return path instead of data
    finally:
        if monitor:
            monitor.stop()


def _normalize_and_screen_streaming(monitor=None):
    """Process normalization and screening in streaming mode to avoid memory spike."""
    import token_normalizer
    import rule_screener

    INTER_SCREENED.parent.mkdir(parents=True, exist_ok=True)
    if INTER_SCREENED.exists():
        INTER_SCREENED.unlink()

    seen_words = set()
    passed_count = 0
    rejected_count = 0

    # Stream from loaded tokens
    from utils import iter_jsonl
    total_processed = 0

    for rec in iter_jsonl(INTER_LOADED):
        total_processed += 1

        # Check memory if monitor is enabled
        if monitor and total_processed % 10000 == 0:
            if not monitor.check():
                log.warning("Memory threshold reached, halting...")
                break

        # Normalize
        normalized = token_normalizer.normalize_raw(rec["raw_token"])[0]
        words = token_normalizer.split_to_words(normalized)

        for word in words:
            if word in seen_words:
                continue
            seen_words.add(word)

            # Screen
            result, reason = rule_screener.screen_token(word)

            updated = {
                **rec,
                "normalized_word": word,
                "transformations": rec.get("transformations", []) + ["split_underscore"],
                "normalization_flag": "split_from_phrase",
                "screen_result": result,
                "screen_reason": reason,
                "status": "SCREENED",
            }

            from utils import append_jsonl
            append_jsonl(INTER_SCREENED, updated)

            if result == "pass":
                passed_count += 1
            else:
                rejected_count += 1

        # Progress reporting
        if total_processed % 100000 == 0:
            log.info("  Processed %d tokens...", total_processed)
            import gc
            gc.collect()

    log.info("  Total processed: %d", total_processed)
    log.info("  Passed: %d, Rejected: %d", passed_count, rejected_count)


# ---------------------------------------------------------------------------
# Phase: consensus  (Step 8 — algorithmic vote aggregation)
# ---------------------------------------------------------------------------

def phase_consensus(resume: bool = False, enable_memory_monitor: bool = True):
    log.info("=" * 60)
    log.info("Phase: CONSENSUS  (Step 8) - Streaming Mode")
    log.info("=" * 60)

    # Start memory monitoring
    monitor = None
    if enable_memory_monitor:
        try:
            from memory_monitor import MemoryMonitor
            monitor = MemoryMonitor(threshold_mb=2048, phase_name="CONSENSUS (Step 8)")
            monitor.start()
        except ImportError:
            log.warning("memory_monitor module not available, skipping memory monitoring")

    try:
        if resume and INTER_CONSENSUS.exists():
            log.info("Resuming — %s already exists, skipping.", INTER_CONSENSUS)
            from utils import read_jsonl
            return read_jsonl(INTER_CONSENSUS)

        import ai_review

        log.info("[Step 8] Vote aggregation (streaming)")
        rebutted_iter = ai_review.iter_rebutted()
        ai_review.build_consensus_streaming(rebutted_iter)

        # Clean up rebutted file to save disk space
        if INTER_REBUTTED.exists():
            try:
                INTER_REBUTTED.unlink()
                log.info("  Cleaned up rebutted file (freed disk space)")
            except PermissionError:
                log.warning("  Cannot clean up rebutted file (locked)")

        # Count results without loading all into memory
        log.info("  Consensus built (streaming)")
        log.info("Next: python src/pipeline.py --phase export")
        return INTER_CONSENSUS
    finally:
        if monitor:
            monitor.stop()


# ---------------------------------------------------------------------------
# Phase: export  (Steps 9-10)
# ---------------------------------------------------------------------------

def phase_export(resume: bool = False, enable_memory_monitor: bool = True):
    log.info("=" * 60)
    log.info("Phase: EXPORT  (Steps 9-10) - Streaming Mode")
    log.info("=" * 60)
    _ensure_dirs()

    # Start memory monitoring
    monitor = None
    if enable_memory_monitor:
        try:
            from memory_monitor import MemoryMonitor
            monitor = MemoryMonitor(threshold_mb=2048, phase_name="EXPORT (Steps 9-10)")
            monitor.start()
        except ImportError:
            log.warning("memory_monitor module not available, skipping memory monitoring")

    try:
        import ai_review
        import result_writer
        import human_review_exporter

        # Step 8: Build consensus if needed (streaming)
        if not INTER_CONSENSUS.exists():
            log.info("[Step 8] Building consensus (streaming)")
            rebutted_iter = ai_review.iter_rebutted()
            ai_review.build_consensus_streaming(rebutted_iter)
        else:
            log.info("[Step 8] Consensus already exists, skipping")

        # Step 9: Write JSONL results (streaming)
        log.info("[Step 9] Writing JSONL/JSON results (streaming)")
        run_meta = {
            "pipeline_version": PIPELINE_VERSION,
            "export_time": datetime.datetime.utcnow().isoformat() + "Z",
        }
        saas_path, rejected_path = result_writer.run_streaming(run_meta)

        # Step 10: Human review export (streaming)
        log.info("[Step 10] Human review XLSX/CSV export (streaming)")
        human_review_exporter.run_streaming()

        # Auto-run QA after export completes
        log.info("")
        log.info("[Auto QA] Running QA analysis after export...")
        _run_auto_qa()

        log.info("")
        log.info("Export phase complete (streaming mode).")
        log.info("Next (optional): Claude Code 세션이 Step 12 QA 판정을 수행합니다.")
        log.info("After QA judgment: python src/pipeline.py --phase qa")
        return saas_path, rejected_path
    finally:
        if monitor:
            monitor.stop()


def _run_auto_qa():
    """Automatically run QA analysis after export completes."""
    try:
        import subprocess
        import sys

        log.info("Executing QA analyzer...")
        result = subprocess.run(
            [sys.executable, "src/qa_analyzer.py"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )

        if result.returncode == 0:
            log.info("Auto QA completed successfully.")
            # Print QA summary
            for line in result.stdout.split("\n"):
                if "Final Verdict" in line or "Total Checks" in line or "Passed" in line or "Failed" in line:
                    log.info("  QA: %s", line)
        else:
            log.warning("Auto QA failed with return code %d", result.returncode)
            if result.stderr:
                log.warning("QA errors: %s", result.stderr[:500])
    except FileNotFoundError:
        log.warning("QA analyzer not found, skipping auto QA")
    except subprocess.TimeoutExpired:
        log.warning("Auto QA timed out after 5 minutes")
    except Exception as exc:
        log.warning("Auto QA failed: %s", exc)


# ---------------------------------------------------------------------------
# Phase: qa  (Step 12 — QA report collation, script side)
# ---------------------------------------------------------------------------

def phase_qa():
    log.info("=" * 60)
    log.info("Phase: QA  (Step 12 — report collation)")
    log.info("=" * 60)
    _ensure_dirs()

    import qa_report_collator
    qa_report_collator.run()
    log.info("QA collation complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SaaS Word Extractor Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--phase",
        required=True,
        choices=["prep", "consensus", "export", "qa"],
        help="실행할 파이프라인 단계",
    )
    parser.add_argument("--resume", action="store_true",
                        help="중간 파일이 있으면 해당 단계 재사용")
    parser.add_argument("--max-words", type=int, default=0,
                        help="prep 단계 처리 단어 수 제한 (테스트용, 0=무제한)")
    parser.add_argument("--enable-memory-monitor", action="store_true", default=True,
                        help="Enable memory monitoring (default: True)")
    parser.add_argument("--disable-memory-monitor", action="store_true",
                        help="Disable memory monitoring")
    args = parser.parse_args()

    start = datetime.datetime.utcnow()

    # Determine if memory monitoring should be enabled
    enable_memory_monitor = args.enable_memory_monitor and not args.disable_memory_monitor

    try:
        if args.phase == "prep":
            phase_prep(resume=args.resume, max_words=args.max_words, enable_memory_monitor=enable_memory_monitor)
        elif args.phase == "consensus":
            phase_consensus(resume=args.resume, enable_memory_monitor=enable_memory_monitor)
        elif args.phase == "export":
            phase_export(resume=args.resume, enable_memory_monitor=enable_memory_monitor)
        elif args.phase == "qa":
            phase_qa()
    except KeyboardInterrupt:
        log.warning("Interrupted.")
        sys.exit(1)
    except Exception as exc:
        log.error("Pipeline failed: %s", exc, exc_info=True)
        sys.exit(2)

    elapsed = (datetime.datetime.utcnow() - start).total_seconds()
    log.info("Done in %.1f seconds.", elapsed)


if __name__ == "__main__":
    main()
