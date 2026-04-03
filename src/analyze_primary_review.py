#!/usr/bin/env python3
"""
Analyze Primary Review Results
Generate statistics and validation reports for the primary review output
"""

import json
from collections import Counter, defaultdict
from pathlib import Path


def analyze_primary_review(output_path: str):
    """Analyze the primary review results and generate statistics"""

    output_file = Path(output_path)

    stats = {
        'total_records': 0,
        'total_accept': 0,
        'total_reject': 0,
        'total_borderline': 0,
        'label_distribution': Counter(),
        'judge_decisions': defaultdict(Counter),
        'confidence_distribution': Counter(),
        'rejection_reasons': Counter(),
        'sample_accepted': [],
        'sample_rejected': [],
        'unanimous_accept': 0,
        'unanimous_reject': 0,
        'majority_accept': 0,
        'majority_reject': 0,
        'split_decisions': 0
    }

    print(f"Analyzing {output_file}...")
    print("-" * 60)

    with open(output_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line.strip())
                stats['total_records'] += 1

                # Get summary
                summary = record.get('primary_summary', {})
                accept_count = summary.get('accept', 0)
                reject_count = summary.get('reject', 0)
                borderline_count = summary.get('borderline', 0)

                stats['total_accept'] += accept_count
                stats['total_reject'] += reject_count
                stats['total_borderline'] += borderline_count

                # Analyze decision patterns
                if accept_count == 5:
                    stats['unanimous_accept'] += 1
                elif reject_count == 5:
                    stats['unanimous_reject'] += 1
                elif accept_count >= 3:
                    stats['majority_accept'] += 1
                elif reject_count >= 3:
                    stats['majority_reject'] += 1
                else:
                    stats['split_decisions'] += 1

                # Analyze individual judge decisions
                primary_votes = record.get('primary_votes', [])
                for vote in primary_votes:
                    judge_id = vote.get('judge_id', 'unknown')
                    decision = vote.get('decision', 'unknown')
                    label = vote.get('label')
                    confidence = vote.get('confidence', 0)

                    stats['judge_decisions'][judge_id][decision] += 1

                    if label:
                        stats['label_distribution'][label] += 1

                    # Round confidence to 1 decimal place for distribution
                    conf_rounded = round(confidence, 1)
                    stats['confidence_distribution'][conf_rounded] += 1

                    # Track rejection reasons
                    if decision == 'reject':
                        for reason in vote.get('why', []):
                            stats['rejection_reasons'][reason] += 1

                # Sample records (first 100 of each type)
                word = record.get('normalized_word', '')
                if accept_count >= 3 and len(stats['sample_accepted']) < 100:
                    stats['sample_accepted'].append({
                        'word': word,
                        'accept': accept_count,
                        'reject': reject_count,
                        'labels': [v.get('label') for v in primary_votes if v.get('decision') == 'accept']
                    })
                elif reject_count >= 3 and len(stats['sample_rejected']) < 100:
                    stats['sample_rejected'].append({
                        'word': word,
                        'accept': accept_count,
                        'reject': reject_count,
                        'reasons': list(set([r for v in primary_votes for r in v.get('why', [])]))
                    })

                # Progress reporting
                if line_num % 1000000 == 0:
                    print(f"Processed {line_num:,} records...")

            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}")
                continue
            except Exception as e:
                print(f"Error processing line {line_num}: {e}")
                continue

    # Print statistics
    print("\n" + "=" * 60)
    print("PRIMARY REVIEW ANALYSIS RESULTS")
    print("=" * 60)

    print(f"\nTOTAL RECORDS: {stats['total_records']:,}")

    print(f"\nDECISION SUMMARY:")
    print(f"  Total Accept Votes: {stats['total_accept']:,} ({stats['total_accept']/stats['total_records']/5*100:.1f}%)")
    print(f"  Total Reject Votes: {stats['total_reject']:,} ({stats['total_reject']/stats['total_records']/5*100:.1f}%)")
    print(f"  Total Borderline Votes: {stats['total_borderline']:,} ({stats['total_borderline']/stats['total_records']/5*100:.1f}%)")

    print(f"\nCONSENSUS PATTERNS:")
    print(f"  Unanimous Accept (5/5): {stats['unanimous_accept']:,} ({stats['unanimous_accept']/stats['total_records']*100:.1f}%)")
    print(f"  Unanimous Reject (5/5): {stats['unanimous_reject']:,} ({stats['unanimous_reject']/stats['total_records']*100:.1f}%)")
    print(f"  Majority Accept (3-4/5): {stats['majority_accept']:,} ({stats['majority_accept']/stats['total_records']*100:.1f}%)")
    print(f"  Majority Reject (3-4/5): {stats['majority_reject']:,} ({stats['majority_reject']/stats['total_records']*100:.1f}%)")
    print(f"  Split Decisions: {stats['split_decisions']:,} ({stats['split_decisions']/stats['total_records']*100:.1f}%)")

    print(f"\nLABEL DISTRIBUTION:")
    for label, count in stats['label_distribution'].most_common():
        percentage = count / sum(stats['label_distribution'].values()) * 100
        print(f"  {label}: {count:,} ({percentage:.1f}%)")

    print(f"\nJUDGE DECISIONS:")
    for judge_id in sorted(stats['judge_decisions'].keys()):
        decisions = stats['judge_decisions'][judge_id]
        total = sum(decisions.values())
        print(f"  {judge_id}:")
        for decision, count in decisions.most_common():
            print(f"    {decision}: {count:,} ({count/total*100:.1f}%)")

    print(f"\nTOP REJECTION REASONS:")
    for reason, count in stats['rejection_reasons'].most_common(20):
        print(f"  {reason}: {count:,}")

    print(f"\nCONFIDENCE DISTRIBUTION:")
    for conf, count in sorted(stats['confidence_distribution'].items()):
        bar = '█' * int(count / 100000)
        print(f"  {conf:.1f}: {count:,} {bar}")

    print(f"\nSAMPLE ACCEPTED WORDS:")
    for i, sample in enumerate(stats['sample_accepted'][:20], 1):
        labels_str = ', '.join(set(sample['labels']))
        print(f"  {i}. {sample['word']} ({sample['accept']}/5 accept) [{labels_str}]")

    print(f"\nSAMPLE REJECTED WORDS:")
    for i, sample in enumerate(stats['sample_rejected'][:20], 1):
        reasons_str = ', '.join(sample['reasons'][:3])
        print(f"  {i}. {sample['word']} ({sample['reject']}/5 reject) [{reasons_str}]")

    return stats


if __name__ == "__main__":
    output_file = "C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/05_primary_reviewed.jsonl"
    analyze_primary_review(output_file)
