#!/usr/bin/env python3
"""
Auto-Fix Pipeline Orchestrator
==============================
크래시 리포트를 분석하고 메모리 문제를 자동으로 수정하며 QA로 검증하는 반복 루프.
Claude Code와 연동하여 자동 수정을 수행합니다.
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import get_logger
from config import OUTPUT_DIR

log = get_logger("auto_fix_pipeline")

MAX_FIX_ATTEMPTS = 5
FIX_COOLDOWN = 10  # seconds between fixes


class AutoFixPipeline:
    """자동 수정 파이프라인"""

    def __init__(self):
        self.crash_dir = OUTPUT_DIR / "crash_reports"
        self.latest_crash = self.crash_dir / "latest_crash.json"

    def run(self) -> bool:
        """자동 수정 루프 실행"""
        log.info("=" * 60)
        log.info("AUTO-FIX PIPELINE STARTED")
        log.info("=" * 60)

        for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
            log.info(f"\nAttempt {attempt}/{MAX_FIX_ATTEMPTS}")

            # 1. 크래시 리포트 확인
            if not self.latest_crash.exists():
                log.error("No crash report found. Run pipeline_safe.py first.")
                return False

            crash_report = self.load_crash_report()
            halt_phase = crash_report['halt_phase']
            log.info(f"Crash phase: {halt_phase}")
            log.info(f"Memory: {crash_report['current_memory_mb']:.1f} MB")

            # 2. 수정 제안 분석 및 Claude Code를 통한 자동 수정
            fixes_applied = self.analyze_and_apply_fixes(crash_report)
            if not fixes_applied:
                log.error("No fixes were applied. Cannot continue.")
                return False

            log.info("Waiting for fixes to be applied...")
            time.sleep(FIX_COOLDOWN)

            # 3. QA 실행
            qa_passed = self.run_qa()

            if qa_passed:
                log.info("=" * 60)
                log.info("QA PASSED - Auto-fix complete!")
                log.info("=" * 60)
                return True
            else:
                log.warning(f"QA failed on attempt {attempt}")
                if attempt < MAX_FIX_ATTEMPTS:
                    log.info("Will retry with additional fixes...")
                else:
                    log.error("Max attempts reached. Auto-fix failed.")
                    return False

        return False

    def load_crash_report(self) -> dict:
        """크래시 리포트 로드"""
        with open(self.latest_crash, 'r', encoding='utf-8') as f:
            return json.load(f)

    def analyze_and_apply_fixes(self, crash_report: dict) -> bool:
        """크래시 분석 및 수정 적용"""
        suggested_fixes = crash_report.get('suggested_fixes', [])
        halt_phase = crash_report['halt_phase']
        current_mem = crash_report['current_memory_mb']

        log.info(f"Analyzing crash in phase: {halt_phase}")
        log.info(f"Suggested fixes: {len(suggested_fixes)}")

        # 수정 제안 출력 (Claude Code가 읽을 수 있도록)
        print("\n" + "=" * 60)
        print("CLAUDE CODE - AUTO FIX REQUEST")
        print("=" * 60)
        print(f"Phase: {halt_phase}")
        print(f"Current Memory: {current_mem:.1f} MB")
        print(f"Threshold: {crash_report['threshold_mb']} MB")
        print("\nSuggested Fixes:")
        for i, fix in enumerate(suggested_fixes, 1):
            print(f"  {i}. Type: {fix.get('type', 'unknown')}")
            print(f"     Issue: {fix.get('issue', 'N/A')}")
            print(f"     Fix: {fix.get('fix', 'N/A')}")
        print("=" * 60 + "\n")

        # 수정 파일 목록 결정
        fix_targets = self.get_fix_targets(halt_phase)

        if fix_targets:
            log.info(f"Target files to fix: {fix_targets}")

            # 실제 수정은 Claude Code Agent를 통해 수행
            # 여기서는 수정 요청을 출력하고 Agent 호출 준비
            return self.request_claude_code_fix(halt_phase, fix_targets, suggested_fixes)

        return False

    def get_fix_targets(self, halt_phase: str) -> list:
        """단계별 수정 대상 파일 반환"""
        fix_targets = {
            "PREP (Steps 1-4)": [
                "src/input_loader.py",
                "src/token_normalizer.py",
                "src/rule_screener.py"
            ],
            "AI_REVIEW (Steps 5-7)": [
                "src/ai_review_batch_processor.py",
                "src/ai_review_executor.py"
            ],
            "CONSENSUS (Step 8)": [
                "src/ai_review.py",
                "src/pipeline.py"
            ],
            "EXPORT (Steps 9-10)": [
                "src/result_writer.py",
                "src/human_review_exporter.py",
                "src/pipeline.py"
            ]
        }

        # 부분 일치 처리
        for key, files in fix_targets.items():
            if key in halt_phase or halt_phase in key:
                return files

        return []

    def request_claude_code_fix(self, phase: str, files: list, fixes: list) -> bool:
        """Claude Code Agent를 통해 수정 요청"""
        log.info("Requesting Claude Code Agent to apply fixes...")

        # Agent 실행 파일 경로
        agent_file = Path(__file__).parent.parent / ".claude" / "agents" / "auto-fix-memory.md"

        if not agent_file.exists():
            log.warning(f"Agent file not found: {agent_file}")
            log.info("Creating agent file...")
            self.create_agent_file(agent_file)

        # Agent 호출 정보 저장 (Claude Code 세션에서 읽도록)
        fix_request = {
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "files": files,
            "fixes": fixes,
            "status": "pending"
        }

        fix_request_file = OUTPUT_DIR / "crash_reports" / "fix_request.json"
        with open(fix_request_file, 'w', encoding='utf-8') as f:
            json.dump(fix_request, f, indent=2, ensure_ascii=False)

        log.info(f"Fix request saved to: {fix_request_file}")
        log.info("Please run the auto-fix-memory agent to apply fixes.")

        return True

    def create_agent_file(self, agent_path: Path):
        """Agent 파일 생성"""
        agent_path.parent.mkdir(parents=True, exist_ok=True)

        agent_content = """---
name: auto-fix-memory
description: 메모리 문제 자동 수정 에이전트
---

## Task

메모리 초과 문제를 자동으로 분석하고 수정합니다.

## Input

`output/crash_reports/latest_crash.json` 파일을 읽어서:
- `halt_phase`: 문제가 발생한 단계
- `suggested_fixes`: 제안된 수정사항
- `intermediate_files`: 중간 파일 크기 정보

## Actions

1. 문제가 있는 단계의 코드 파일 읽기
2. 메모리 누수/과다 사용 원인 식별
3. 스트리밍 모드나 청크 처리로 수정
4. 수정 사항 적용 (Edit tool 사용)

## Common Fixes

- **input_loader.py**: 리스트 반환 대신 스트리밍으로 변경. `return records`를 제거하고 파일에 직접 쓰기
- **token_normalizer.py**: 전체 리스트를 처리하지 않고 제너레이터로 변경
- **ai_review_batch_processor.py**: 배치 사이즈 줄이기 또는 스트리밍 모드 사용
- **pipeline.py consensus**: `build_consensus_streaming` 사용

## Output

수정된 파일들과 수정 로그를 `output/crash_reports/fix_applied.json`에 저장
"""
        with open(agent_path, 'w', encoding='utf-8') as f:
            f.write(agent_content)

        log.info(f"Agent file created: {agent_path}")

    def run_qa(self) -> bool:
        """QA 실행"""
        log.info("Running QA validation...")

        try:
            result = subprocess.run(
                [sys.executable, "src/qa_analyzer.py"],
                capture_output=True,
                text=True,
                timeout=600
            )

            log.info(f"QA return code: {result.returncode}")

            if result.stdout:
                # 첫 20줄만 출력
                for line in result.stdout.split('\n')[:20]:
                    if line.strip():
                        log.info(f"QA: {line}")

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            log.error("QA timed out after 10 minutes")
            return False
        except Exception as e:
            log.error(f"QA failed: {e}")
            return False


class AutoFixOrchestrator:
    """자동 수정 오케스트레이터 - 전체 루프 관리"""

    def __init__(self):
        self.fixer = AutoFixPipeline()

    def run_full_cycle(self) -> bool:
        """전체 사이클 실행: 파이프라인 → 크래시 시 수정 → QA → 반복"""
        log.info("=" * 60)
        log.info("AUTO-FIX ORCHESTRATOR - FULL CYCLE")
        log.info("=" * 60)

        cycle_count = 0
        max_cycles = 10

        while cycle_count < max_cycles:
            cycle_count += 1
            log.info(f"\n{'='*60}")
            log.info(f"Cycle {cycle_count}/{max_cycles}")
            log.info(f"{'='*60}")

            # 1. 파이프라인 실행
            exit_code = self.run_pipeline_safe()

            if exit_code == 0:
                # 성공!
                log.info("=" * 60)
                log.info("PIPELINE COMPLETED SUCCESSFULLY!")
                log.info("=" * 60)
                return True
            elif exit_code == 130:
                # 메모리 HALT - 수정 루프 진입
                log.info("Memory halt detected. Starting auto-fix...")

                if not self.run_fix_loop():
                    log.error("Auto-fix failed. Manual intervention required.")
                    return False

                # 수정 완료 후 다시 파이프라인 시도
                log.info("Fixes applied. Re-running pipeline...")
                continue
            else:
                # 다른 오류
                log.error(f"Pipeline failed with exit code {exit_code}")
                return False

        log.error("Max cycles reached. Auto-fix incomplete.")
        return False

    def run_pipeline_safe(self) -> int:
        """pipeline_safe.py 실행"""
        log.info("Running pipeline with memory monitoring...")
        result = subprocess.run(
            [sys.executable, "src/pipeline_safe.py", "--phase", "all"],
            capture_output=False
        )
        return result.returncode

    def run_fix_loop(self) -> bool:
        """수정 루프 실행"""
        return self.fixer.run()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto-Fix Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/auto_fix_pipeline.py --mode full     # Complete auto-fix cycle
  python src/auto_fix_pipeline.py --mode fix      # Run fix loop only (after crash)
        """
    )
    parser.add_argument(
        "--mode",
        choices=["fix", "full"],
        default="full",
        help="fix: only run fix loop, full: complete pipeline + fix cycle"
    )
    args = parser.parse_args()

    orchestrator = AutoFixOrchestrator()

    if args.mode == "full":
        success = orchestrator.run_full_cycle()
    else:
        success = orchestrator.run_fix_loop()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
