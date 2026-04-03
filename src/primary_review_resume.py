#!/usr/bin/env python3
"""
Primary Review Processor with Resume Capability
Can resume from where it left off if processing is interrupted
"""

import json
import time
import sys
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from ai_judgment_helper import AIJudgmentHelper


class ResumablePrimaryReviewProcessor:
    """Process screened tokens through AI primary review with resume capability"""

    def __init__(self, input_path: str, output_path: str, batch_size: int = 5000):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.batch_size = batch_size
        self.checkpoint_path = Path(output_path).with_suffix('.checkpoint.json')

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
            'start_time': None,
            'last_checkpoint_time': None,
            'last_line_processed': 0
        }

    def save_checkpoint(self):
        """Save checkpoint for resuming"""
        checkpoint = {
            'stats': self.stats,
            'timestamp': datetime.now().isoformat(),
            'last_line_processed': self.stats['last_line_processed']
        }
        with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2)

    def load_checkpoint(self) -> Dict:
        """Load checkpoint if exists"""
        if self.checkpoint_path.exists():
            with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def get_ai_judgment(self, word: str, judge_id: str, judge_focus: str) -> Dict[str, Any]:
        """Get AI judgment using AIJudgmentHelper"""
        return AIJudgmentHelper.get_rule_based_judgment(word, judge_id, judge_focus)

    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single record through 5-judge review"""
        word = record.get('normalized_word', '')

        # Clean record of any datetime objects before processing
        cleaned_record = {}
        for k, v in record.items():
            if isinstance(v, datetime):
                cleaned_record[k] = v.isoformat()
            elif isinstance(v, dict):
                cleaned_record[k] = {sk: sv.isoformat() if isinstance(sv, datetime) else sv for sk, sv in v.items()}
            else:
                cleaned_record[k] = v

        # Skip if already rejected by rule screening
        if cleaned_record.get('screen_result') == 'reject':
            primary_votes = []
            for judge_id, judge_focus in self.judges.items():
                primary_votes.append({
                    'judge_id': judge_id,
                    'decision': 'reject',
                    'label': None,
                    'confidence': 0.95,
                    'why': [cleaned_record.get('screen_reason', 'previously_rejected')]
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

        # Add review data to cleaned record
        cleaned_record['primary_votes'] = primary_votes
        cleaned_record['primary_summary'] = primary_summary
        cleaned_record['status'] = 'AI_PRIMARY_REVIEWED'

        # Update statistics
        self.stats['total_processed'] += 1
        self.stats['total_accepted'] += primary_summary['accept']
        self.stats['total_rejected'] += primary_summary['reject']
        self.stats['total_borderline'] += primary_summary['borderline']

        return cleaned_record

    def get_output_line_count(self) -> int:
        """Get current number of lines in output file"""
        if self.output_path.exists():
            with open(self.output_path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        return 0

    def process_stream(self, resume: bool = True):
        """Process the entire file with streaming and resume capability"""

        self.stats['start_time'] = datetime.now()

        # Check for resume
        start_line = 0
        mode = 'a' if resume and self.output_path.exists() else 'w'

        if resume:
            current_output_lines = self.get_output_line_count()
            checkpoint = self.load_checkpoint()

            if checkpoint and current_output_lines > 0:
                start_line = checkpoint.get('last_line_processed', current_output_lines)
                self.stats = checkpoint.get('stats', self.stats)
                print(f"Resuming from line {start_line:,}")
                print(f"Previously processed: {self.stats['total_processed']:,} records")
            elif current_output_lines > 0:
                start_line = current_output_lines
                print(f"Resuming from output file line {start_line:,}")

        if start_line > 0:
            print(f"Starting from input line {start_line:,}")
        else:
            print(f"Starting fresh processing")

        print(f"Input: {self.input_path}")
        print(f"Output: {self.output_path}")
        print(f"Mode: {'append (resume)' if mode == 'a' else 'overwrite'}")
        print(f"Batch size: {self.batch_size}")
        print("-" * 60)

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        batch = []
        processed_count = start_line
        last_report_time = time.time()
        last_checkpoint_time = time.time()
        checkpoint_interval = 300  # Save checkpoint every 5 minutes

        with open(self.input_path, 'r', encoding='utf-8') as infile, \
             open(self.output_path, 'a' if mode == 'a' and start_line > 0 else 'w', encoding='utf-8') as outfile:

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
                        rate = (processed_count - start_line) / (current_time - self.stats['start_time'].timestamp())
                        print(f"Processed: {processed_count:,} records | Rate: {rate:.1f} records/sec | " +
                              f"Accept: {self.stats['total_accepted']:,} | Reject: {self.stats['total_rejected']:,}")
                        last_report_time = current_time

                    # Checkpoint saving
                    if current_time - last_checkpoint_time >= checkpoint_interval:
                        self.stats['last_line_processed'] = processed_count
                        self.save_checkpoint()
                        print(f"Checkpoint saved at line {processed_count:,}")
                        last_checkpoint_time = current_time

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

        # Final checkpoint and summary
        self.stats['last_line_processed'] = processed_count
        self.stats['end_time'] = datetime.now().isoformat()
        self.save_checkpoint()

        print("-" * 60)
        print(f"Processing complete!")
        print(f"Total records processed: {self.stats['total_processed']:,}")
        print(f"Total accept votes: {self.stats['total_accepted']:,}")
        print(f"Total reject votes: {self.stats['total_rejected']:,}")
        print(f"Total borderline votes: {self.stats['total_borderline']:,}")

        if self.stats['start_time']:
            start = datetime.fromisoformat(self.stats['start_time']) if isinstance(self.stats['start_time'], str) else self.stats['start_time']
            end = datetime.fromisoformat(self.stats['end_time']) if isinstance(self.stats['end_time'], str) else datetime.now()
            duration = (end - start).total_seconds()
            print(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
            if duration > 0:
                print(f"Average rate: {self.stats['total_processed']/duration:.2f} records/sec")

        print(f"Output saved to: {self.output_path}")
        print(f"Checkpoint saved to: {self.checkpoint_path}")


def main():
    """Main entry point"""

    input_file = "C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/04_screened_tokens.jsonl"
    output_file = "C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/05_primary_reviewed.jsonl"

    processor = ResumablePrimaryReviewProcessor(
        input_path=input_file,
        output_path=output_file,
        batch_size=10000  # Larger batch for better performance
    )

    # Resume from existing output if present
    processor.process_stream(resume=True)


if __name__ == "__main__":
    main()
