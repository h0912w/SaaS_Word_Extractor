#!/usr/bin/env python3
"""
Monitor Primary Review Progress
Simple script to check the progress of the primary review processing
"""

import time
from pathlib import Path


def monitor_progress(output_path: str, input_line_count: int):
    """Monitor the progress of primary review processing"""

    output_file = Path(output_path)

    print("Monitoring Primary Review Progress")
    print("=" * 50)
    print(f"Input line count: {input_line_count:,}")
    print(f"Output file: {output_file}")
    print("-" * 50)

    last_count = 0
    check_interval = 30  # Check every 30 seconds

    while True:
        if output_file.exists():
            with open(output_file, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)

            progress_pct = (line_count / input_line_count) * 100
            remaining = input_line_count - line_count

            # Calculate rate
            if last_count > 0:
                rate = (line_count - last_count) / check_interval
                if rate > 0:
                    eta_seconds = remaining / rate
                    eta_minutes = eta_seconds / 60
                    eta_hours = eta_minutes / 60
                    eta_str = f"{eta_hours:.1f}h" if eta_hours >= 1 else f"{eta_minutes:.1f}m"
                else:
                    rate = 0
                    eta_str = "unknown"
            else:
                rate = 0
                eta_str = "calculating..."

            print(f"\rProgress: {line_count:,}/{input_line_count:,} ({progress_pct:.1f}%) | "
                  f"Rate: {rate:.0f} lines/sec | ETA: {eta_str}      ", end='', flush=True)

            last_count = line_count

            # Check if complete
            if line_count >= input_line_count:
                print("\n\nProcessing complete!")
                break

        else:
            print("\rWaiting for output file to be created...", end='', flush=True)

        time.sleep(check_interval)


if __name__ == "__main__":
    output_file = "C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/05_primary_reviewed.jsonl"
    input_lines = 12216231

    try:
        monitor_progress(output_file, input_lines)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
