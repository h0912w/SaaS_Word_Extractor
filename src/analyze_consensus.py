#!/usr/bin/env python3
"""Analyze consensus results"""

import json
import sys
from pathlib import Path

def main():
    # Read the consensus file
    records = []
    with open('output/intermediate/08_consensus.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    print(f'Total records: {len(records)}')
    print()

    # Find cases where challenge overturned primary decision
    print('='*60)
    print('CASES WHERE CHALLENGE OVERTURNED PRIMARY DECISION')
    print('='*60)
    overturned = [r for r in records if
                  ((r['primary_summary']['accept'] >= 3) and (r['consensus_decision'] == 'reject')) or
                  ((r['primary_summary']['accept'] < 3) and (r['consensus_decision'] == 'accept'))]

    for i, r in enumerate(overturned[:15], 1):
        primary_dec = 'ACCEPT' if r['primary_summary']['accept'] >= 3 else 'REJECT'
        word = r['normalized_word']
        # Skip problematic characters for display
        safe_word = word.encode('ascii', 'replace').decode('ascii')
        print(f'{i}. {safe_word}: {primary_dec} -> {r["consensus_decision"].upper()}')
        print(f'   Reason: {r["consensus_reasons"]}')
        print(f'   Confidence: {r["consensus_confidence"]}')
        print()

    print(f'Total overturned: {len(overturned)} out of {len(records)}')
    print()

    # Show distribution of rejection reasons
    print('='*60)
    print('REJECTION REASONS')
    print('='*60)
    reject_reasons = {}
    for r in records:
        if r['consensus_decision'] == 'reject':
            label = r['consensus_label']
            reject_reasons[label] = reject_reasons.get(label, 0) + 1

    for reason, count in sorted(reject_reasons.items(), key=lambda x: x[1], reverse=True):
        print(f'{reason}: {count}')

    print()
    print('='*60)
    print('ACCEPTED BY LABEL')
    print('='*60)
    for label in ['brandable', 'functional', 'ambiguous']:
        count = sum(1 for r in records if r['consensus_decision'] == 'accept' and r['consensus_label'] == label)
        print(f'{label}: {count}')

if __name__ == '__main__':
    main()
