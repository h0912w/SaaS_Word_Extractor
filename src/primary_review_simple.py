#!/usr/bin/env python3
"""
Simple Primary Review Processor - No checkpoint dependency
Resumes based on output file line count only
"""

import json
import time
import sys
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from ai_judgment_helper import AIJudgmentHelper


class SimplePrimaryReviewProcessor:
    """Process screened tokens through AI primary review without checkpoint complexity"""

    def __init__(self, input_path: str, output_path: str, batch_size: int = 10000):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.batch_size = batch_size

        # Judge configurations
        self.judges = {
            'saas-title-judge-01': 'recall_focus',
            'saas-title-judge-02': 'brand_focus',
            'saas-title-judge-03': 'tech_focus',
            'saas-title-judge-04': 'english_focus',
            'saas-title-judge-05': 'balanced'
        }

        self.stats = {
            'total_processed': 0,
            'total_accepted': 0,
            'total_rejected': 0,
            'total_borderline': 0,
        }

    def get_ai_judgment(self, word: str, judge_id: str, judge_focus: str) -> Dict[str, Any]:
        """Get AI judgment using AIJudgmentHelper"""
        return AIJudgmentHelper.get_rule_based_judgment(word, judge_id, judge_focus)

    def get_output_line_count(self) -> int:
        """Get current number of lines in output file"""
        if self.output_path.exists():
            with open(self.output_path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        return 0

    def clean_datetime(self, obj):
        """Convert datetime objects to ISO format strings"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self.clean_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.clean_datetime(item) for item in obj]
        return obj

    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single record through 5-judge review"""
        # Clean any datetime objects from input record
        record = self.clean_datetime(record)

        word = record.get('normalized_word', '')

        # Skip if already rejected by rule screening
        if record.get('screen_result') == 'reject':
            primary_votes = []
            for judge_id, judge_focus in self.judges.items():
                primary_votes.append({
                    'judge_id': judge_id,
                    'decision': 'reject',
                    'label': None,
                    'confidence': 0.95,
                    'why': [record.get('screen_reason', 'previously_rejected')]
                })
            primary_summary = {'reject': 5, 'accept': 0, 'borderline': 0}
        else:
            # Get 5 independent judgments
            primary_votes = []
            accept_count = 0
            reject_count = 0
            borderline_count = 0

            for judge_id, judge_focus in self.judges.items():
                judgment = self.get_ai_judgment(word, judge_id, judge_focus)
                primary_votes.append({
                    'judge_id': judge_id,
                    'decision': judgment['decision'],
                    'label': judgment['label'],
                    'confidence': judgment['confidence'],
                    'why': judgment['why']
                })

                if judgment['decision'] == 'accept':
                    accept_count += 1
                elif judgment['decision'] == 'reject':
                    reject_count += 1
                else:
                    borderline_count += 1

            primary_summary = {
                'accept': accept_count,
                'reject': reject_count,
                'borderline': borderline_count
            }

        # Add review data to record
        record['primary_votes'] = primary_votes
        record['primary_summary'] = primary_summary
        record['status'] = 'AI_PRIMARY_REVIEWED'

        # Update statistics
        self.stats['total_processed'] += 1
        self.stats['total_accepted'] += primary_summary['accept']
        self.stats['total_rejected'] += primary_summary['reject']
        self.stats['total_borderline'] += primary_summary['borderline']

        return record

    def process_stream(self):
        """Process the entire file with streaming, resuming from existing output"""

        start_time = time.time()
        current_output_lines = self.get_output_line_count()
        start_line = current_output_lines

        print(f"Resuming from line {start_line:,}")
        print(f"Input: {self.input_path}")
        print(f"Output: {self.output_path}")
        print(f"Batch size: {self.batch_size}")
        print("-" * 60)

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        batch = []
        processed_count = start_line
        last_report_time = time.time()

        with open(self.input_path, 'r', encoding='utf-8') as infile, \
             open(self.output_path, 'a' if start_line > 0 else 'w', encoding='utf-8') as outfile:

            # Skip to start line if resuming
            if start_line > 0:
                for _ in range(start_line):
                    next(infile)
                print(f"Skipped to line {start_line:,} in input file")

            for line_num, line in enumerate(infile, start_line + 1):
                try:
                    record = json.loads(line.strip())
                    processed_record = self.process_record(record)

                    batch.append(processed_record)
                    processed_count += 1

                    # Write batch to output
                    if len(batch) >= self.batch_size:
                        for record in batch:
                            outfile.write(json.dumps(record, ensure_ascii=False) + '\n')
                        batch = []

                    # Progress reporting every 30 seconds
                    current_time = time.time()
                    if current_time - last_report_time >= 30:
                        rate = (processed_count - start_line) / (current_time - start_time)
                        pct = (processed_count / 12216231) * 100
                        print(f"Progress: {processed_count:,} / 12,216,231 ({pct:.1f}%) | "
                              f"Rate: {rate:.1f} rec/sec | "
                              f"Accept: {self.stats['total_accepted']:,} | "
                              f"Reject: {self.stats['total_rejected']:,}")
                        last_report_time = current_time

                except json.JSONDecodeError as e:
                    print(f"Error parsing line {line_num}: {e}")
                    continue
                except Exception as e:
                    print(f"Error processing line {line_num}: {e}")
                    continue

            # Write remaining records
            if batch:
                for record in batch:
                    outfile.write(json.dumps(record, ensure_ascii=False) + '\n')

        # Final summary
        duration = time.time() - start_time
        print("-" * 60)
        print(f"Processing complete!")
        print(f"Total records processed: {self.stats['total_processed']:,}")
        print(f"Total accept votes: {self.stats['total_accepted']:,}")
        print(f"Total reject votes: {self.stats['total_rejected']:,}")
        print(f"Total borderline votes: {self.stats['total_borderline']:,}")
        print(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        if duration > 0:
            print(f"Average rate: {self.stats['total_processed']/duration:.2f} records/sec")
        print(f"Output saved to: {self.output_path}")


def main():
    """Main entry point"""

    input_file = "C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/04_screened_tokens.jsonl"
    output_file = "C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/05_primary_reviewed.jsonl"

    processor = SimplePrimaryReviewProcessor(
        input_path=input_file,
        output_path=output_file,
        batch_size=10000
    )

    # Resume from existing output if present
    processor.process_stream()


if __name__ == "__main__":
    main()
