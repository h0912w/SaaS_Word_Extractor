"""
Pipeline Orchestrator — 메인 Claude Code 세션용 오케스트레이터

이 모듈은 메인 Claude Code 세션이 전체 파이프라인(Steps 1-12)을
자동으로 실행할 때 사용하는 오케스트레이터입니다.

사용 방법:
  # 메인 Claude Code 세션에서
  from src.orchestrator import run_full_pipeline_orchestrated
  run_full_pipeline_orchestrated()

이 오케스트레이터는:
1. Steps 1-4: Python 스크립트 실행
2. Steps 5-7: Agent tool을 사용한 AI 판정 (메인 세션에서 수행)
3. Step 8: Python 스크립트 실행
4. Steps 9-10: Python 스크립트 실행
5. Steps 11-12: Agent tool을 사용한 QA 판정 (메인 세션에서 수행)
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, Callable

from config import (
    INTER_CHALLENGED,
    INTER_PRIMARY,
    INTER_REBUTTED,
    INTER_SCREENED,
    OUT_SAAS_WORDS,
    OUT_REJECTED_WORDS,
    QA_DIR,
)
from utils import get_logger, iter_jsonl, append_jsonl

log = get_logger("orchestrator")


# =============================================================================
# Orchestrator — Main Entry Point
# =============================================================================

def run_full_pipeline_orchestrated(
    max_words: int = 0,
    start_line: int = 1,
    resume: bool = False,
    skip_qa: bool = False,
    agent_caller: Optional[Callable] = None
) -> dict:
    """
    전체 파이프라인을 오케스트레이션합니다.

    이 함수는 메인 Claude Code 세션에서 호출되어야 합니다.
    AI 판정 단계(Steps 5-7, 12)는 agent_caller를 통해 에이전트를 호출합니다.

    Args:
        max_words: 처리할 최대 단어 수 (0=무제한)
        start_line: 시작 라인 번호
        resume: 중간 파일이 있으면 재개
        skip_qa: QA 단계 건너뛰기
        agent_caller: AI 판정을 위한 에이전트 호출 함수
                     (없으면 기본 Agent tool 사용)

    Returns:
        실행 결과 딕셔너리
    """
    result = {
        "success": False,
        "steps_completed": [],
        "steps_failed": [],
        "error": None
    }

    log.info("=" * 70)
    log.info("PIPELINE ORCHESTRATOR — Starting Full Pipeline")
    log.info("=" * 70)

    # ========================================================================
    # PHASE 1: Steps 1-4 (Prep)
    # ========================================================================
    log.info("[PHASE 1] Running Steps 1-4: Input → Load → Normalize → Screen")

    if not _run_python_phase("prep", resume, max_words, start_line):
        result["steps_failed"].append("Steps 1-4")
        result["error"] = "Prep phase failed"
        return result

    result["steps_completed"].append("Steps 1-4")

    if not INTER_SCREENED.exists():
        result["steps_failed"].append("Steps 1-4")
        result["error"] = f"Screened tokens not found: {INTER_SCREENED}"
        return result

    log.info("Step 4 complete: %s", INTER_SCREENED)

    # ========================================================================
    # PHASE 2: Step 5 — AI Primary Review
    # ========================================================================
    log.info("[PHASE 2] Running Step 5: AI Primary Review")

    if not _run_ai_step5(agent_caller):
        result["steps_failed"].append("Step 5")
        result["error"] = "Primary review failed"
        return result

    result["steps_completed"].append("Step 5")

    if not INTER_PRIMARY.exists():
        result["steps_failed"].append("Step 5")
        result["error"] = f"Primary review output not found: {INTER_PRIMARY}"
        return result

    log.info("Step 5 complete: %s", INTER_PRIMARY)

    # ========================================================================
    # PHASE 3: Step 6 — AI Challenge Review
    # ========================================================================
    log.info("[PHASE 3] Running Step 6: AI Challenge Review")

    if not _run_ai_step6(agent_caller):
        result["steps_failed"].append("Step 6")
        result["error"] = "Challenge review failed"
        return result

    result["steps_completed"].append("Step 6")

    if not INTER_CHALLENGED.exists():
        result["steps_failed"].append("Step 6")
        result["error"] = f"Challenge review output not found: {INTER_CHALLENGED}"
        return result

    log.info("Step 6 complete: %s", INTER_CHALLENGED)

    # ========================================================================
    # PHASE 4: Step 7 — AI Rebuttal Review
    # ========================================================================
    log.info("[PHASE 4] Running Step 7: AI Rebuttal Review")

    if not _run_ai_step7(agent_caller):
        result["steps_failed"].append("Step 7")
        result["error"] = "Rebuttal review failed"
        return result

    result["steps_completed"].append("Step 7")

    if not INTER_REBUTTED.exists():
        result["steps_failed"].append("Step 7")
        result["error"] = f"Rebuttal review output not found: {INTER_REBUTTED}"
        return result

    log.info("Step 7 complete: %s", INTER_REBUTTED)

    # ========================================================================
    # PHASE 5: Step 8 — Consensus
    # ========================================================================
    log.info("[PHASE 5] Running Step 8: Consensus Aggregation")

    if not _run_python_phase("consensus", resume):
        result["steps_failed"].append("Step 8")
        result["error"] = "Consensus phase failed"
        return result

    result["steps_completed"].append("Step 8")

    log.info("Step 8 complete")

    # ========================================================================
    # PHASE 6: Steps 9-10 — Export
    # ========================================================================
    log.info("[PHASE 6] Running Steps 9-10: JSONL/JSON + XLSX/CSV Export")

    if not _run_python_phase("export", resume):
        result["steps_failed"].append("Steps 9-10")
        result["error"] = "Export phase failed"
        return result

    result["steps_completed"].append("Steps 9-10")

    if not OUT_SAAS_WORDS.exists():
        result["steps_failed"].append("Steps 9-10")
        result["error"] = f"Output files not found: {OUT_SAAS_WORDS}"
        return result

    log.info("Steps 9-10 complete: %s", OUT_SAAS_WORDS)

    # ========================================================================
    # PHASE 7: Steps 11-12 — QA (Optional)
    # ========================================================================
    if not skip_qa:
        log.info("[PHASE 7] Running Steps 11-12: QA Analysis")

        if not _run_ai_steps_11_12(agent_caller):
            result["steps_failed"].append("Steps 11-12")
            result["error"] = "QA phase failed"
            return result

        result["steps_completed"].append("Steps 11-12")
        log.info("Steps 11-12 complete")
    else:
        log.info("[PHASE 7] Skipping QA (as requested)")

    # ========================================================================
    # COMPLETE
    # ========================================================================
    result["success"] = True

    log.info("=" * 70)
    log.info("PIPELINE COMPLETE")
    log.info("=" * 70)
    log.info("Steps completed: %s", ", ".join(result["steps_completed"]))

    return result


# =============================================================================
# Python Phase Runners
# =============================================================================

def _run_python_phase(
    phase: str,
    resume: bool = False,
    max_words: int = 0,
    start_line: int = 1
) -> bool:
    """Python 스크립트 단계를 실행합니다."""

    cmd = [sys.executable, "src/pipeline.py", "--phase", phase]

    if resume:
        cmd.append("--resume")
    if max_words > 0:
        cmd.extend(["--max-words", str(max_words)])
    if start_line > 1:
        cmd.extend(["--batch-start", str(start_line)])

    log.info("Running: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    if result.returncode != 0:
        log.error("Phase %s failed with return code %d", phase, result.returncode)
        if result.stderr:
            log.error("Error output: %s", result.stderr[:500])
        return False

    log.info("Phase %s completed successfully", phase)
    return True


# =============================================================================
# AI Step Runners (Agent Tool Callers)
# =============================================================================

def _run_ai_step5(agent_caller: Optional[Callable] = None) -> bool:
    """
    Step 5: AI Primary Review 실행

    이 함수는 메인 Claude Code 세션에서 Agent tool을 사용하여
    saas-title-judge 에이전트를 호출합니다.

    실제 AI 판정은 메인 세션에서 수행되므로, 이 함수는
    호출을 준비하고 결과를 검증하는 역할만 합니다.
    """
    log.info("Preparing Step 5: AI Primary Review")
    log.info("Input: %s", INTER_SCREENED)
    log.info("Output: %s", INTER_PRIMARY)
    log.info("")
    log.info("IMPORTANT: This step requires the main Claude Code session")
    log.info("to invoke the saas-title-judge agent using the Agent tool.")
    log.info("")
    log.info("The agent should:")
    log.info("  1. Read %s", INTER_SCREENED)
    log.info("  2. Process each word through saas-title-judge agents")
    log.info("  3. Write results to %s", INTER_PRIMARY)
    log.info("")

    # 실제 AI 판정은 메인 세션에서 Agent tool로 수행
    # 이 함수는 호출을 준비하고 결과 파일이 생성되었는지 확인만 함

    if agent_caller:
        # agent_caller가 제공되면 호출
        try:
            agent_caller("step5", INTER_SCREENED, INTER_PRIMARY)
        except Exception as exc:
            log.error("Agent caller failed for Step 5: %s", exc)
            return False
    else:
        # agent_caller가 없으면 메뉴얼 실행 가정
        log.warning("No agent_caller provided - assuming manual execution")
        log.warning("Please ensure saas-title-judge agent runs and produces %s", INTER_PRIMARY)

    # 결과 파일 검증
    if not INTER_PRIMARY.exists():
        log.error("Step 5 output not found: %s", INTER_PRIMARY)
        return False

    # 결과 파일이 비어있지 않은지 확인
    try:
        count = sum(1 for _ in iter_jsonl(INTER_PRIMARY))
        if count == 0:
            log.error("Step 5 output is empty: %s", INTER_PRIMARY)
            return False
        log.info("Step 5 output validated: %d records", count)
    except Exception as exc:
        log.error("Failed to validate Step 5 output: %s", exc)
        return False

    return True


def _run_ai_step6(agent_caller: Optional[Callable] = None) -> bool:
    """
    Step 6: AI Challenge Review 실행

    이 함수는 메인 Claude Code 세션에서 Agent tool을 사용하여
    challenge-reviewer 에이전트를 호출합니다.
    """
    log.info("Preparing Step 6: AI Challenge Review")
    log.info("Input: %s", INTER_PRIMARY)
    log.info("Output: %s", INTER_CHALLENGED)
    log.info("")
    log.info("IMPORTANT: This step requires the main Claude Code session")
    log.info("to invoke the challenge-reviewer agent using the Agent tool.")
    log.info("")

    if agent_caller:
        try:
            agent_caller("step6", INTER_PRIMARY, INTER_CHALLENGED)
        except Exception as exc:
            log.error("Agent caller failed for Step 6: %s", exc)
            return False
    else:
        log.warning("No agent_caller provided - assuming manual execution")

    if not INTER_CHALLENGED.exists():
        log.error("Step 6 output not found: %s", INTER_CHALLENGED)
        return False

    try:
        count = sum(1 for _ in iter_jsonl(INTER_CHALLENGED))
        if count == 0:
            log.error("Step 6 output is empty: %s", INTER_CHALLENGED)
            return False
        log.info("Step 6 output validated: %d records", count)
    except Exception as exc:
        log.error("Failed to validate Step 6 output: %s", exc)
        return False

    return True


def _run_ai_step7(agent_caller: Optional[Callable] = None) -> bool:
    """
    Step 7: AI Rebuttal Review 실행

    이 함수는 메인 Claude Code 세션에서 Agent tool을 사용하여
    rebuttal-reviewer 에이전트를 호출합니다.
    """
    log.info("Preparing Step 7: AI Rebuttal Review")
    log.info("Input: %s", INTER_CHALLENGED)
    log.info("Output: %s", INTER_REBUTTED)
    log.info("")
    log.info("IMPORTANT: This step requires the main Claude Code session")
    log.info("to invoke the rebuttal-reviewer agent using the Agent tool.")
    log.info("")

    if agent_caller:
        try:
            agent_caller("step7", INTER_CHALLENGED, INTER_REBUTTED)
        except Exception as exc:
            log.error("Agent caller failed for Step 7: %s", exc)
            return False
    else:
        log.warning("No agent_caller provided - assuming manual execution")

    if not INTER_REBUTTED.exists():
        log.error("Step 7 output not found: %s", INTER_REBUTTED)
        return False

    try:
        count = sum(1 for _ in iter_jsonl(INTER_REBUTTED))
        if count == 0:
            log.error("Step 7 output is empty: %s", INTER_REBUTTED)
            return False
        log.info("Step 7 output validated: %d records", count)
    except Exception as exc:
        log.error("Failed to validate Step 7 output: %s", exc)
        return False

    return True


def _run_ai_steps_11_12(agent_caller: Optional[Callable] = None) -> bool:
    """
    Steps 11-12: QA Analysis 실행

    이 함수는 메인 Claude Code 세션에서 Agent tool을 사용하여
    qa-reviewer 에이전트를 호출합니다.
    """
    log.info("Preparing Steps 11-12: QA Analysis")
    log.info("Input: %s and %s", OUT_SAAS_WORDS, OUT_REJECTED_WORDS)
    log.info("Output: %s", QA_DIR / "qa_report.json")
    log.info("")
    log.info("IMPORTANT: This step requires the main Claude Code session")
    log.info("to invoke the qa-reviewer agent using the Agent tool.")
    log.info("")

    if agent_caller:
        try:
            agent_caller("qa", OUT_SAAS_WORDS, OUT_REJECTED_WORDS, QA_DIR / "qa_report.json")
        except Exception as exc:
            log.error("Agent caller failed for QA: %s", exc)
            return False
    else:
        log.warning("No agent_caller provided - assuming manual execution")

    qa_report_path = QA_DIR / "qa_report.json"
    if not qa_report_path.exists():
        log.error("QA report not found: %s", qa_report_path)
        return False

    log.info("QA report validated: %s", qa_report_path)
    return True


# =============================================================================
# Standalone Execution (for testing)
# =============================================================================

def main():
    """테스트용 단독 실행 함수."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline Orchestrator — Test execution"
    )
    parser.add_argument("--max-words", type=int, default=0)
    parser.add_argument("--start-line", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-qa", action="store_true")

    args = parser.parse_args()

    result = run_full_pipeline_orchestrated(
        max_words=args.max_words,
        start_line=args.start_line,
        resume=args.resume,
        skip_qa=args.skip_qa
    )

    if result["success"]:
        print("\nPipeline completed successfully!")
        print(f"Steps completed: {', '.join(result['steps_completed'])}")
        return 0
    else:
        print(f"\nPipeline failed: {result.get('error', 'Unknown error')}")
        print(f"Failed steps: {', '.join(result['steps_failed'])}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
