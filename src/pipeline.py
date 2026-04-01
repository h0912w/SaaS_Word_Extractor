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

def phase_prep(resume: bool = False, max_words: int = 0):
    log.info("=" * 60)
    log.info("Phase: PREP  (Steps 1-4)")
    log.info("=" * 60)
    _ensure_dirs()

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
    log.info("[Step 2] Loading files")
    loaded = input_loader.run(file_descriptors, resume=resume, max_lines=max_words)
    log.info("  %d raw tokens loaded", len(loaded))

    # Step 3
    log.info("[Step 3] Token normalization + underscore splitting")
    normalized = token_normalizer.run(loaded, resume=resume)
    log.info("  %d unique normalized words", len(normalized))

    # Step 4
    log.info("[Step 4] Rule-based screening")
    passed, rule_rejected = rule_screener.run(normalized, resume=resume)
    log.info("  %d passed  |  %d rule-rejected", len(passed), len(rule_rejected))

    log.info("")
    log.info("Prep phase complete.")
    log.info("Next: Claude Code 세션이 Steps 5-7 AI 판정을 수행해야 합니다.")
    log.info("  Input  : %s", INTER_SCREENED)
    log.info("  Output : output/intermediate/05_primary_reviewed.jsonl")
    log.info("           output/intermediate/06_challenged.jsonl")
    log.info("           output/intermediate/07_rebutted.jsonl")
    log.info("After Steps 5-7: python src/pipeline.py --phase consensus")

    return passed, rule_rejected


# ---------------------------------------------------------------------------
# Phase: consensus  (Step 8 — algorithmic vote aggregation)
# ---------------------------------------------------------------------------

def phase_consensus(resume: bool = False):
    log.info("=" * 60)
    log.info("Phase: CONSENSUS  (Step 8)")
    log.info("=" * 60)

    if resume and INTER_CONSENSUS.exists():
        log.info("Resuming — %s already exists, skipping.", INTER_CONSENSUS)
        from utils import read_jsonl
        return read_jsonl(INTER_CONSENSUS)

    import ai_review

    log.info("[Step 8] Vote aggregation")
    rebutted = ai_review.load_rebutted()
    consensus = ai_review.build_consensus(rebutted)

    accept_n = sum(1 for r in consensus if r["decision"] == "accept")
    reject_n = sum(1 for r in consensus if r["decision"] == "reject")
    log.info("  %d accept  |  %d reject", accept_n, reject_n)
    log.info("Next: python src/pipeline.py --phase export")
    return consensus


# ---------------------------------------------------------------------------
# Phase: export  (Steps 9-10)
# ---------------------------------------------------------------------------

def phase_export(resume: bool = False):
    log.info("=" * 60)
    log.info("Phase: EXPORT  (Steps 9-10)")
    log.info("=" * 60)
    _ensure_dirs()

    import ai_review
    import result_writer
    import human_review_exporter
    from config import INTER_SCREENED
    from utils import read_jsonl

    # Load consensus records
    consensus = ai_review.load_rebutted()  # loads from INTER_REBUTTED
    # Build/load consensus if not yet built
    if not INTER_CONSENSUS.exists():
        consensus_records = ai_review.build_consensus(consensus)
    else:
        consensus_records = read_jsonl(INTER_CONSENSUS)

    # Load rule-rejected records (from screened file)
    all_screened = read_jsonl(INTER_SCREENED)
    rule_rejected = [r for r in all_screened if r.get("screen_result") == "reject"]

    # Step 9
    log.info("[Step 9] Writing JSONL/JSON results")
    run_meta = {
        "pipeline_version": PIPELINE_VERSION,
        "export_time": datetime.datetime.utcnow().isoformat() + "Z",
    }
    saas_records, all_rejected = result_writer.run(
        consensus_records, rule_rejected, run_meta
    )

    # Step 10
    log.info("[Step 10] Human review XLSX/CSV export")
    human_review_exporter.run(saas_records, all_rejected)

    log.info("")
    log.info("Export phase complete.")
    log.info("Next (optional): Claude Code 세션이 Step 12 QA 판정을 수행합니다.")
    log.info("After QA judgment: python src/pipeline.py --phase qa")
    return saas_records, all_rejected


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
    args = parser.parse_args()

    start = datetime.datetime.utcnow()

    try:
        if args.phase == "prep":
            phase_prep(resume=args.resume, max_words=args.max_words)
        elif args.phase == "consensus":
            phase_consensus(resume=args.resume)
        elif args.phase == "export":
            phase_export(resume=args.resume)
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
