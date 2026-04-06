"""
Batch Orchestrator — 자동 배치 처리 오케스트레이터

이 모듈은 대규모 데이터를 처리할 때 자동으로 배치 단위로 나누어
전체 파이프라인을 실행하는 오케스트레이터입니다.

사용 방법:
  # 메인 Claude Code 세션에서
  from src.batch_orchestrator import run_batch_pipeline
  from src.agent_executor import call_step5_agents, call_step6_agents, call_step7_agents, call_qa_agents

  # 에이전트 호출 함수 정의
  def agent_caller(step, input_path, output_path, *args):
      if step == "step5":
          call_step5_agents(input_path, output_path)
      elif step == "step6":
          call_step6_agents(input_path, output_path)
      elif step == "step7":
          call_step7_agents(input_path, output_path)
      elif step == "qa":
          call_qa_agents(input_path, output_path)

  # 30만개 처리 → 자동으로 10만개씩 3배치 처리
  result = run_batch_pipeline(agent_caller=agent_caller, max_words=300000)

작동 방식:
  - 30만개 요청 → 자동으로 3개 배치로 분할 (각 10만개)
  - 각 배치마다 전체 파이프라인(Steps 1-12) 실행
  - 배치별 결과를 output/batch_XXX/에 별도 저장
"""

import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from config import (
    BATCH_SIZE,
    INTER_SCREENED,
    QA_DIR,
)
from utils import get_logger

log = get_logger("batch_orchestrator")


def run_batch_pipeline(
    agent_caller: Optional[Callable] = None,
    max_words: int = 0,
    start_line: int = 1,
    skip_qa: bool = False,
    auto_merge: bool = False
) -> dict:
    """
    배치 단위로 전체 파이프라인을 자동 실행합니다.

    대규모 데이터(30만개 등)를 처리할 때 자동으로 10만개씩 나누어
    각 배치마다 전체 파이프라인을 실행합니다.

    agent_caller를 제공하지 않으면 자동으로 agent_executor를 사용합니다.
    이렇게 하면 사용자 개입 없이 완전 자동화가 가능합니다.

    Args:
        agent_caller: 에이전트 호출 함수 (None이면 자동으로 agent_executor 사용)
        max_words: 처리할 최대 단어 수 (0=입력 파일 전체)
        start_line: 시작 라인 번호
        skip_qa: QA 단계 건너뛰기
        auto_merge: 완료 후 자동 병합

    Returns:
        실행 결과 딕셔너리
    """
    result = {
        "success": False,
        "batches_completed": [],
        "batches_failed": [],
        "total_words_processed": 0,
        "error": None
    }

    log.info("=" * 70)
    log.info("BATCH PIPELINE ORCHESTRATOR — Starting Batch Processing")
    log.info("=" * 70)
    log.info("Target words: %s", "Unlimited" if max_words == 0 else max_words)
    log.info("Batch size: %d", BATCH_SIZE)

    # 먼저 입력 파일의 전체 라인 수 확인
    total_lines = _get_input_file_line_count()

    if max_words == 0:
        max_words = total_lines
    elif max_words > total_lines:
        max_words = total_lines

    log.info("Total lines to process: %d", max_words)

    # 배치 수 계산
    num_batches = (max_words + BATCH_SIZE - 1) // BATCH_SIZE
    log.info("Will process in %d batch(es)", num_batches)

    # 각 배치 처리
    current_line = start_line
    remaining_words = max_words

    for batch_num in range(1, num_batches + 1):
        batch_words = min(BATCH_SIZE, remaining_words)

        log.info("")
        log.info("=" * 70)
        log.info("BATCH %d/%d — Processing %d words (line %d)",
                 batch_num, num_batches, batch_words, current_line)
        log.info("=" * 70)

        batch_result = _run_single_batch(
            batch_num=batch_num,
            start_line=current_line,
            max_words=batch_words,
            agent_caller=agent_caller,
            skip_qa=skip_qa
        )

        if batch_result["success"]:
            result["batches_completed"].append(batch_num)
            result["total_words_processed"] += batch_words
            log.info("BATCH %d COMPLETED — %d words processed",
                     batch_num, batch_words)
        else:
            result["batches_failed"].append(batch_num)
            result["error"] = f"Batch {batch_num} failed: {batch_result.get('error')}"
            log.error("BATCH %d FAILED — %s", batch_num, batch_result.get('error'))
            return result

        current_line += batch_words
        remaining_words -= batch_words

    # 모든 배치 완료
    result["success"] = True

    log.info("")
    log.info("=" * 70)
    log.info("ALL BATCHES COMPLETED")
    log.info("=" * 70)
    log.info("Batches completed: %d/%s",
             len(result["batches_completed"]), num_batches)
    log.info("Total words processed: %d", result["total_words_processed"])

    # 자동 병합 (요청 시)
    if auto_merge and result["success"]:
        log.info("")
        log.info("Auto-merging all batches...")
        _merge_all_batches()
        log.info("Merge complete")

    return result


def _get_input_file_line_count() -> int:
    """입력 파일의 전체 라인 수를 반환합니다."""
    import input_loader
    import input_discovery

    files = input_discovery.run(resume=True)
    supported = [f for f in files if f.get("supported")]

    if not supported:
        return 0

    input_path = Path(supported[0]["path"])

    try:
        count = input_loader.count_lines(input_path)
        log.info("Input file total lines: %d", count)
        return count
    except Exception as exc:
        log.warning("Could not count lines: %s", exc)
        return 0


def _run_single_batch(
    batch_num: int,
    start_line: int,
    max_words: int,
    agent_caller: Callable,
    skip_qa: bool = False
) -> dict:
    """
    단일 배치에 대한 전체 파이프라인을 실행합니다.

    Returns:
        배치 실행 결과 딕셔너리
    """
    result = {
        "batch_number": batch_num,
        "success": False,
        "error": None
    }

    try:
        # Step 1-4: Prep
        log.info("[Batch %d] Phase 1: Steps 1-4 (Prep)", batch_num)

        cmd = [sys.executable, "src/pipeline.py", "--phase", "prep",
               "--batch-start", str(start_line), "--max-words", str(max_words)]

        log.info("Running: %s", " ".join(cmd))
        proc_result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        if proc_result.returncode != 0:
            result["error"] = f"Prep phase failed: {proc_result.stderr[:200]}"
            return result

        if not INTER_SCREENED.exists():
            result["error"] = "Screened tokens not generated"
            return result

        log.info("[Batch %d] Step 4 complete", batch_num)

        # Step 5: Primary Review
        log.info("[Batch %d] Phase 2: Step 5 (Primary Review)", batch_num)
        try:
            if agent_caller:
                agent_caller("step5", INTER_SCREENED, Path("output/intermediate/05_primary_reviewed.jsonl"))
            else:
                # 자동으로 agent_executor 사용 (사용자 개입 없음)
                from agent_executor import call_step5_agents
                call_step5_agents()
        except Exception as exc:
            result["error"] = f"Step 5 failed: {exc}"
            return result

        log.info("[Batch %d] Step 5 complete", batch_num)

        # Step 6: Challenge Review
        log.info("[Batch %d] Phase 3: Step 6 (Challenge Review)", batch_num)
        try:
            if agent_caller:
                agent_caller("step6", Path("output/intermediate/05_primary_reviewed.jsonl"), Path("output/intermediate/06_challenged.jsonl"))
            else:
                # 자동으로 agent_executor 사용 (사용자 개입 없음)
                from agent_executor import call_step6_agents
                call_step6_agents()
        except Exception as exc:
            result["error"] = f"Step 6 failed: {exc}"
            return result

        log.info("[Batch %d] Step 6 complete", batch_num)

        # Step 7: Rebuttal Review
        log.info("[Batch %d] Phase 4: Step 7 (Rebuttal Review)", batch_num)
        try:
            if agent_caller:
                agent_caller("step7", Path("output/intermediate/06_challenged.jsonl"), Path("output/intermediate/07_rebutted.jsonl"))
            else:
                # 자동으로 agent_executor 사용 (사용자 개입 없음)
                from agent_executor import call_step7_agents
                call_step7_agents()
        except Exception as exc:
            result["error"] = f"Step 7 failed: {exc}"
            return result

        log.info("[Batch %d] Step 7 complete", batch_num)

        # Step 8: Consensus
        log.info("[Batch %d] Phase 5: Step 8 (Consensus)", batch_num)

        cmd = [sys.executable, "src/pipeline.py", "--phase", "consensus"]
        proc_result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        if proc_result.returncode != 0:
            result["error"] = f"Consensus phase failed: {proc_result.stderr[:200]}"
            return result

        log.info("[Batch %d] Step 8 complete", batch_num)

        # Steps 9-10: Export
        log.info("[Batch %d] Phase 6: Steps 9-10 (Export)", batch_num)

        cmd = [sys.executable, "src/pipeline.py", "--phase", "export"]
        proc_result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        if proc_result.returncode != 0:
            result["error"] = f"Export phase failed: {proc_result.stderr[:200]}"
            return result

        log.info("[Batch %d] Steps 9-10 complete", batch_num)

        # 배치 결과를 batch_XXX 디렉토리로 이동
        _move_batch_results(batch_num)

        # Steps 11-12: QA (선택 사항)
        if not skip_qa:
            log.info("[Batch %d] Phase 7: Steps 11-12 (QA)", batch_num)
            try:
                if agent_caller:
                    agent_caller("qa", Path("output/saas_words.jsonl"), Path("output/rejected_words.jsonl"), QA_DIR / "qa_report.json")
                else:
                    # 자동으로 agent_executor 사용 (사용자 개입 없음)
                    from agent_executor import call_qa_agents
                    call_qa_agents()
            except Exception as exc:
                log.warning("[Batch %d] QA failed (non-critical): %s", batch_num, exc)

            log.info("[Batch %d] Steps 11-12 complete", batch_num)

        result["success"] = True

    except Exception as exc:
        result["error"] = f"Batch processing failed: {exc}"
        log.error("Batch %d error: %s", batch_num, exc, exc_info=True)

    return result


def _move_batch_results(batch_num: int):
    """배치 결과를 batch_XXX 디렉토리로 이동합니다."""
    import shutil

    batch_dir = Path(f"output/batch_{batch_num:03d}")
    batch_dir.mkdir(parents=True, exist_ok=True)

    # 이동할 파일들
    files_to_move = [
        "output/saas_words.jsonl",
        "output/rejected_words.jsonl",
        "output/run_summary.json",
        "output/human_review/saas_words_review.xlsx",
        "output/human_review/saas_words_review.csv",
        "output/human_review/rejected_words_review.xlsx",
    ]

    for file_pattern in files_to_move:
        src = Path(file_pattern)
        if src.exists():
            dst = batch_dir / src.name
            shutil.move(str(src), str(dst))
            log.info("Moved %s → %s", src, dst)


def _merge_all_batches():
    """모든 배치 결과를 병합합니다."""
    import subprocess

    cmd = [sys.executable, "src/pipeline.py", "--phase", "merge"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    if result.returncode != 0:
        log.warning("Merge failed: %s", result.stderr)
    else:
        log.info("Merge completed successfully")


# =============================================================================
# Standalone Execution
# =============================================================================

def main():
    """테스트용 단독 실행 함수."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch Pipeline Orchestrator — 자동 배치 처리"
    )
    parser.add_argument("--max-words", type=int, default=0,
                        help="처리할 최대 단어 수 (0=입력 파일 전체)")
    parser.add_argument("--start-line", type=int, default=1,
                        help="시작 라인 번호")
    parser.add_argument("--skip-qa", action="store_true",
                        help="QA 단계 건너뛰기")
    parser.add_argument("--auto-merge", action="store_true",
                        help="완료 후 자동 병합")

    args = parser.parse_args()

    # agent_caller 없이 자동 실행 (사용자 개입 없음)
    result = run_batch_pipeline(
        agent_caller=None,  # None이면 자동으로 agent_executor 사용
        max_words=args.max_words,
        start_line=args.start_line,
        skip_qa=args.skip_qa,
        auto_merge=args.auto_merge
    )

    if result["success"]:
        print(f"\n=== 배치 파이프라인 완료 ===")
        print(f"완료된 배치: {', '.join(map(str, result['batches_completed']))}")
        print(f"총 처리 단어: {result['total_words_processed']:,}")
        return 0
    else:
        print(f"\n=== 배치 파이프라인 실패 ===")
        print(f"오류: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
