#!/usr/bin/env python3
"""
Primary Review Batch Processor
Processes 04_screened_tokens.jsonl through AI judgment with 5 perspectives per word
"""

import json
import time
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent))

from ai_judgment_helper import AIJudgmentHelper

class PrimaryReviewProcessor:
    """Process screened tokens through AI primary review"""

    def __init__(self, input_path: str, output_path: str, batch_size: int = 1000):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.batch_size = batch_size
        self.stats = {
            'total_processed': 0,
            'total_accepted': 0,
            'total_rejected': 0,
            'total_borderline': 0,
            'start_time': None,
            'end_time': None
        }

        # Judge configurations
        self.judges = {
            'saas-title-judge-01': 'recall_focus',      # Most liberal, recall priority
            'saas-title-judge-02': 'brand_focus',       # Brand value focus
            'saas-title-judge-03': 'tech_focus',        # Technical/functional value
            'saas-title-judge-04': 'english_focus',     # Real English word focus
            'saas-title-judge-05': 'balanced'           # Balanced quality review
        }

    def get_ai_judgment(self, word: str, judge_id: str, judge_focus: str) -> Dict[str, Any]:
        """
        Get AI judgment for a single word from a specific judge perspective
        Uses rule-based judgment from AIJudgmentHelper for consistency
        """
        return AIJudgmentHelper.get_rule_based_judgment(word, judge_id, judge_focus)

    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single record through 5-judge review"""

        word = record.get('normalized_word', '')

        # Skip if already rejected by rule screening
        if record.get('screen_result') == 'reject':
            # Still add primary_votes but all reject
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
        """Process the entire file with streaming to handle large datasets"""

        self.stats['start_time'] = datetime.now()

        print(f"Starting primary review processing")
        print(f"Input: {self.input_path}")
        print(f"Output: {self.output_path}")
        print(f"Batch size: {self.batch_size}")
        print("-" * 60)

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        batch = []
        processed_count = 0
        last_report_time = time.time()

        with open(self.input_path, 'r', encoding='utf-8') as infile, \
             open(self.output_path, 'w', encoding='utf-8') as outfile:

            for line_num, line in enumerate(infile, 1):
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

                    # Progress reporting every 10 seconds
                    current_time = time.time()
                    if current_time - last_report_time >= 10:
                        rate = processed_count / (current_time - self.stats['start_time'].timestamp())
                        print(f"Processed: {processed_count:,} records | Rate: {rate:.1f} records/sec")
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

        self.stats['end_time'] = datetime.now()

        # Print final statistics
        print("-" * 60)
        print(f"Processing complete!")
        print(f"Total records processed: {self.stats['total_processed']:,}")
        print(f"Total accept votes: {self.stats['total_accepted']:,}")
        print(f"Total reject votes: {self.stats['total_rejected']:,}")
        print(f"Total borderline votes: {self.stats['total_borderline']:,}")

        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        print(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        print(f"Average rate: {self.stats['total_processed']/duration:.2f} records/sec")
        print(f"Output saved to: {self.output_path}")


def main():
    """Main entry point"""

    input_file = "C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/04_screened_tokens.jsonl"
    output_file = "C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/05_primary_reviewed.jsonl"

    processor = PrimaryReviewProcessor(
        input_path=input_file,
        output_path=output_file,
        batch_size=1000
    )

    processor.process_stream()


if __name__ == "__main__":
    main()
