#!/usr/bin/env python3
"""
Safe Pipeline with Memory Monitoring
=====================================
메모리 모니터링이 포함된 안전한 파이프라인.
메모리 임계값 초과 시 자동으로 프로세스를 종료하고 크래시 리포트를 생성합니다.
"""

import gc
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import get_logger
from config import OUTPUT_DIR, INTERMEDIATE_DIR

log = get_logger("pipeline_safe")


class MemoryMonitor:
    """메모리 모니터링 클래스"""

    def __init__(self, threshold_mb: float = 7000, check_interval: int = 5):
        self.threshold_mb = threshold_mb
        self.check_interval = check_interval
        self.should_halt = False
        self.halt_occurred = False
        self.halt_phase = "unknown"

    def get_memory_mb(self) -> float:
        """현재 프로세스 메모리 사용량(MB) 반환"""
        try:
            import psutil
            return psutil.Process().memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0

    def monitor_loop(self):
        """메모리 모니터링 루프 (별도 스레드)"""
        while not self.should_halt:
            mem_mb = self.get_memory_mb()

            # 주기적 로그
            if int(time.time()) % 30 == 0 and mem_mb > 100:
                log.info(f"Memory: {mem_mb:.1f} MB / {self.threshold_mb} MB")

            # 임계값 확인
            if mem_mb >= self.threshold_mb:
                self.halt_occurred = True
                log.error(f"=" * 60)
                log.error(f"MEMORY HALT: {mem_mb:.1f} MB >= {self.threshold_mb} MB")
                log.error(f"Phase: {self.halt_phase}")
                log.error(f"=" * 60)

                # 크래시 리포트 생성
                self.create_crash_report(mem_mb)

                # 문제 프로세스 종료
                self.kill_problematic_processes()
                self.should_halt = True
                return

            time.sleep(self.check_interval)

    def create_crash_report(self, current_mb: float):
        """크래시 리포트 생성"""
        crash_dir = OUTPUT_DIR / "crash_reports"
        crash_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_file = crash_dir / f"crash_{timestamp}.json"

        # 현재 실행 중인 Python 프로세스 정보 수집
        python_processes = []
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        python_processes.append({
                            "pid": proc.info['pid'],
                            "memory_mb": proc.info['memory_info'].rss / 1024 / 1024,
                            "cmdline": [str(c) for c in proc.info.get('cmdline', [])]
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            pass

        # 중간 파일 크기 수집
        intermediate_files = {}
        if INTERMEDIATE_DIR.exists():
            for f in INTERMEDIATE_DIR.iterdir():
                if f.is_file():
                    intermediate_files[f.name] = {
                        "size_mb": f.stat().st_size / 1024 / 1024,
                        "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    }

        crash_report = {
            "timestamp": datetime.now().isoformat(),
            "halt_phase": self.halt_phase,
            "current_memory_mb": current_mb,
            "threshold_mb": self.threshold_mb,
            "python_processes": python_processes,
            "intermediate_files": intermediate_files,
            "suggested_fixes": self.generate_fix_suggestions(current_mb, intermediate_files)
        }

        with open(crash_file, 'w', encoding='utf-8') as f:
            json.dump(crash_report, f, indent=2, ensure_ascii=False)

        log.info(f"Crash report created: {crash_file}")

        # 최신 크래시 리포트 (Windows용으로 복사)
        latest_crash = crash_dir / "latest_crash.json"
        with open(latest_crash, 'w', encoding='utf-8') as f:
            json.dump(crash_report, f, indent=2, ensure_ascii=False)

    def generate_fix_suggestions(self, current_mb: float, intermediate_files: dict) -> list:
        """수정 제안 생성"""
        suggestions = []

        # 파일 크기 기반 분석
        for name, info in intermediate_files.items():
            if info['size_mb'] > 500:  # 500MB 이상
                suggestions.append({
                    "type": "large_file",
                    "file": name,
                    "issue": f"File size {info['size_mb']:.1f} MB is too large",
                    "fix": f"Process {name} in streaming mode or reduce batch size"
                })

        # 메모리 양에 따른 제안
        if current_mb > 8000:
            suggestions.append({
                "type": "threshold",
                "issue": "Memory usage extremely high",
                "fix": "Reduce MEMORY_HALT_MB to 6000 or implement chunked processing"
            })

        # 단계별 제안
        phase_fixes = {
            "PREP (Steps 1-4)": "Use streaming mode in input_loader.py and token_normalizer.py. Don't load all data into memory.",
            "AI_REVIEW (Steps 5-7)": "Reduce batch size in ai_review_batch_processor.py or implement streaming processing.",
            "CONSENSUS (Step 8)": "Use streaming consensus (build_consensus_streaming) instead of loading all rebutted records.",
            "EXPORT (Steps 9-10)": "Process exports in chunks using streaming mode, don't accumulate all records in memory."
        }

        if self.halt_phase in phase_fixes:
            suggestions.append({
                "type": "phase_specific",
                "phase": self.halt_phase,
                "issue": f"Memory spike during {self.halt_phase}",
                "fix": phase_fixes[self.halt_phase]
            })

        return suggestions

    def kill_problematic_processes(self):
        """문제 Python 프로세스 종료"""
        try:
            import psutil
            current_pid = psutil.Process().pid

            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        mem_mb = proc.info['memory_info'].rss / 1024 / 1024
                        # 높은 메모리 사용 프로세스 종료 (70% 이상)
                        if mem_mb > self.threshold_mb * 0.7:
                            pid = proc.info['pid']
                            if pid != current_pid:
                                log.warning(f"Killing Python PID {pid} ({mem_mb:.1f} MB)")
                                proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            log.warning("psutil not available, cannot kill processes automatically")


def run_phase_with_monitoring(
    phase_name: str,
    cmd: list,
    monitor: MemoryMonitor,
    timeout: int = 3600
) -> bool:
    """메모리 모니터링과 함께 파이프라인 단계 실행"""
    log.info("=" * 60)
    log.info(f"PHASE: {phase_name}")
    log.info("=" * 60)

    monitor.halt_phase = phase_name

    # 모니터링 스레드 시작
    monitor_thread = threading.Thread(target=monitor.monitor_loop, daemon=True)
    monitor_thread.start()

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=1
        )

        # 실시간 출력
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break

            if line:
                try:
                    print(line.decode('utf-8', errors='replace').rstrip())
                except Exception:
                    print(str(line))

            # 메모리 HALT 확인
            if monitor.halt_occurred:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
                return False

        return_code = process.wait(timeout=timeout)

        if return_code != 0:
            log.error(f"Phase {phase_name} failed with code {return_code}")
            return False

        # 단계 완료 후 메모리 정리
        gc.collect()
        time.sleep(1)

        return True

    except subprocess.TimeoutExpired:
        log.error(f"Phase {phase_name} timed out")
        try:
            process.kill()
        except Exception:
            pass
        return False
    finally:
        monitor.should_halt = True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Safe Pipeline with Memory Monitoring")
    parser.add_argument(
        "--phase",
        choices=["prep", "ai", "consensus", "export", "all"],
        default="all",
        help="Pipeline phase to run"
    )
    parser.add_argument(
        "--max-memory-mb",
        type=float,
        default=7000,
        help="Memory halt threshold in MB (default: 7000)"
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=5,
        help="Memory check interval in seconds (default: 5)"
    )
    args = parser.parse_args()

    monitor = MemoryMonitor(threshold_mb=args.max_memory_mb, check_interval=args.check_interval)

    phases = {
        "prep": ([sys.executable, "src/pipeline.py", "--phase", "prep"], "PREP (Steps 1-4)", 3600),
        "ai": ([sys.executable, "src/ai_review_batch_processor.py"], "AI_REVIEW (Steps 5-7)", 7200),
        "consensus": ([sys.executable, "src/pipeline.py", "--phase", "consensus"], "CONSENSUS (Step 8)", 1800),
        "export": ([sys.executable, "src/pipeline.py", "--phase", "export"], "EXPORT (Steps 9-10)", 3600),
    }

    if args.phase == "all":
        for phase_key, (cmd, name, timeout) in phases.items():
            if not run_phase_with_monitoring(name, cmd, monitor, timeout):
                if monitor.halt_occurred:
                    log.error("=" * 60)
                    log.error("MEMORY HALT OCCURRED")
                    log.error("=" * 60)
                    log.error("Crash report saved to: output/crash_reports/latest_crash.json")
                    log.error("")
                    log.error("To auto-fix and retry, run:")
                    log.error("  python src/auto_fix_pipeline.py --mode full")
                    log.error("")
                    log.error("Or analyze the crash report and fix manually.")
                    sys.exit(130)  # Special exit code for memory halt
                else:
                    log.error(f"Phase {phase_key} failed.")
                    sys.exit(1)

        log.info("=" * 60)
        log.info("PIPELINE COMPLETED SUCCESSFULLY")
        log.info("=" * 60)
        sys.exit(0)
    else:
        cmd, name, timeout = phases[args.phase]
        if run_phase_with_monitoring(name, cmd, monitor, timeout):
            sys.exit(0)
        else:
            if monitor.halt_occurred:
                sys.exit(130)
            sys.exit(1)


if __name__ == "__main__":
    main()
