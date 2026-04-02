#!/usr/bin/env python3
"""
Memory Monitor Module
=====================
Provides memory monitoring utilities for the pipeline.
Can be used as a decorator or context manager.
"""

import gc
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable


def get_memory_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        # Fallback: try Windows-specific method
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulonglong = ctypes.c_ulonglong
            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", c_ulonglong),
                    ("WorkingSetSize", c_ulonglong),
                    ("QuotaPeakPagedPoolUsage", c_ulonglong),
                    ("QuotaPagedPoolUsage", c_ulonglong),
                    ("QuotaPeakNonPagedPoolUsage", c_ulonglong),
                    ("QuotaNonPagedPoolUsage", c_ulonglong),
                    ("PagefileUsage", c_ulonglong),
                    ("PeakPagefileUsage", c_ulonglong),
                    ("PrivateUsage", c_ulonglong),
                ]
            counters = PROCESS_MEMORY_COUNTERS_EX()
            kernel32.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(),
                ctypes.byreference(counters),
                ctypes.sizeof(counters)
            )
            return counters.WorkingSetSize / 1024 / 1024
        except Exception:
            return 0.0


class MemoryMonitor:
    """Memory monitoring class with automatic halt on threshold exceed."""

    def __init__(
        self,
        threshold_mb: float = 7000,
        check_interval: int = 5,
        crash_dir: Optional[Path] = None,
        phase_name: str = "unknown"
    ):
        self.threshold_mb = threshold_mb
        self.check_interval = check_interval
        self.crash_dir = crash_dir or Path("output/crash_reports")
        self.phase_name = phase_name
        self.should_halt = False
        self.halt_occurred = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.start_memory = get_memory_mb()
        self.peak_memory = self.start_memory

    def _monitor_loop(self):
        """Internal monitoring loop running in separate thread."""
        while not self.should_halt:
            mem_mb = get_memory_mb()
            self.peak_memory = max(self.peak_memory, mem_mb)

            # Periodic logging (every 30 seconds)
            if int(time.time()) % 30 == 0 and mem_mb > 100:
                print(f"[Memory Monitor] {mem_mb:.1f} MB / {self.threshold_mb} MB (peak: {self.peak_memory:.1f} MB)")

            # Check threshold
            if mem_mb >= self.threshold_mb:
                self.halt_occurred = True
                print(f"\n{'='*60}")
                print(f"MEMORY HALT TRIGGERED")
                print(f"{'='*60}")
                print(f"Phase: {self.phase_name}")
                print(f"Current: {mem_mb:.1f} MB")
                print(f"Threshold: {self.threshold_mb} MB")
                print(f"Peak: {self.peak_memory:.1f} MB")
                print(f"{'='*60}\n")

                # Create crash report
                self._create_crash_report(mem_mb)
                self.should_halt = True
                return

            time.sleep(self.check_interval)

    def _create_crash_report(self, current_mb: float):
        """Create crash report with diagnostic information."""
        self.crash_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_file = self.crash_dir / f"crash_{timestamp}.json"

        # Collect intermediate file sizes
        intermediate_dir = Path("output/intermediate")
        intermediate_files = {}
        if intermediate_dir.exists():
            for f in intermediate_dir.iterdir():
                if f.is_file():
                    intermediate_files[f.name] = {
                        "size_mb": f.stat().st_size / 1024 / 1024,
                        "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    }

        crash_report = {
            "timestamp": datetime.now().isoformat(),
            "halt_phase": self.phase_name,
            "current_memory_mb": current_mb,
            "threshold_mb": self.threshold_mb,
            "peak_memory_mb": self.peak_memory,
            "start_memory_mb": self.start_memory,
            "intermediate_files": intermediate_files,
            "suggested_fixes": self._generate_fix_suggestions(intermediate_files)
        }

        with open(crash_file, 'w', encoding='utf-8') as f:
            json.dump(crash_report, f, indent=2, ensure_ascii=False)

        print(f"Crash report created: {crash_file}")

        # Also save as latest for auto-fix to find
        latest_crash = self.crash_dir / "latest_crash.json"
        with open(latest_crash, 'w', encoding='utf-8') as f:
            json.dump(crash_report, f, indent=2, ensure_ascii=False)

    def _generate_fix_suggestions(self, intermediate_files: dict) -> list:
        """Generate fix suggestions based on crash state."""
        suggestions = []

        # Large file analysis
        for name, info in intermediate_files.items():
            if info['size_mb'] > 500:
                suggestions.append({
                    "type": "large_file",
                    "file": name,
                    "issue": f"File size {info['size_mb']:.1f} MB is too large",
                    "fix": f"Process {name} in streaming mode or reduce batch size"
                })

        # Memory level suggestions
        if self.peak_memory > 8000:
            suggestions.append({
                "type": "threshold",
                "issue": "Memory usage extremely high",
                "fix": "Reduce MEMORY_HALT_MB to 6000 or implement chunked processing"
            })

        # Phase-specific suggestions
        phase_fixes = {
            "PREP": "Use streaming mode in input_loader.py and token_normalizer.py",
            "AI_REVIEW": "Reduce batch size in ai_review_batch_processor.py",
            "CONSENSUS": "Use streaming consensus (build_consensus_streaming)",
            "EXPORT": "Process exports in chunks using streaming mode"
        }

        for key, fix in phase_fixes.items():
            if key in self.phase_name.upper():
                suggestions.append({
                    "type": "phase_specific",
                    "phase": self.phase_name,
                    "issue": f"Memory spike during {self.phase_name}",
                    "fix": fix
                })
                break

        return suggestions

    def start(self):
        """Start memory monitoring in background thread."""
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.should_halt = False
            self.halt_occurred = False
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print(f"[Memory Monitor] Started (threshold: {self.threshold_mb} MB)")

    def stop(self):
        """Stop memory monitoring."""
        self.should_halt = True
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print(f"[Memory Monitor] Stopped (peak: {self.peak_memory:.1f} MB)")

    def check(self) -> bool:
        """Manual memory check. Returns True if OK, False if exceeded."""
        mem_mb = get_memory_mb()
        self.peak_memory = max(self.peak_memory, mem_mb)

        if mem_mb >= self.threshold_mb:
            self.halt_occurred = True
            self._create_crash_report(mem_mb)
            return False
        return True

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


def monitor_memory(
    threshold_mb: float = 7000,
    phase_name: str = "unknown"
):
    """Decorator for memory monitoring."""

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            with MemoryMonitor(threshold_mb=threshold_mb, phase_name=phase_name) as monitor:
                # Execute function
                result = func(*args, **kwargs)

                # Check if halt occurred during execution
                if monitor.halt_occurred:
                    raise MemoryError(
                        f"Memory threshold exceeded during {phase_name} "
                        f"(peak: {monitor.peak_memory:.1f} MB)"
                    )

                return result

        return wrapper

    return decorator


if __name__ == "__main__":
    # Test memory monitor
    print("Testing Memory Monitor...")

    with MemoryMonitor(threshold_mb=100, phase_name="TEST") as monitor:
        print(f"Start memory: {monitor.start_memory:.1f} MB")
        print("Allocating memory...")

        # Allocate some memory
        data = []
        for i in range(1000000):
            data.append("x" * 1000)
            if i % 100000 == 0:
                mem = get_memory_mb()
                print(f"  Allocated {i} items, memory: {mem:.1f} MB")

                if monitor.halt_occurred:
                    print("Halt occurred!")
                    break

    print("Test complete.")
