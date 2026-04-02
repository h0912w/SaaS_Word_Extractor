#!/usr/bin/env python3
"""Generate detailed consensus report"""

import json
from pathlib import Path
from collections import Counter

def main():
    # Read the consensus file
    records = []
    with open('output/intermediate/08_consensus.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    print('='*70)
    print('THREE-STEP REVIEW PROCESS - FINAL REPORT')
    print('='*70)
    print()

    # Overall statistics
    print('OVERALL STATISTICS')
    print('-'*70)
    total = len(records)
    accepted = sum(1 for r in records if r['consensus_decision'] == 'accept')
    rejected = sum(1 for r in records if r['consensus_decision'] == 'reject')

    print(f'Total records processed: {total}')
    print(f'  Accepted: {accepted} ({100*accepted/total:.1f}%)')
    print(f'  Rejected: {rejected} ({100*rejected/total:.1f}%)')
    print()

    # Primary review stats
    primary_accepted = sum(1 for r in records if r['primary_summary']['accept'] >= 3)
    primary_rejected = sum(1 for r in records if r['primary_summary']['accept'] < 3)
    print(f'Primary review:')
    print(f'  Accepted: {primary_accepted} ({100*primary_accepted/total:.1f}%)')
    print(f'  Rejected: {primary_rejected} ({100*primary_rejected/total:.1f}%)')
    print()

    # Challenge impact
    print('CHALLENGE REVIEW IMPACT')
    print('-'*70)
    challenges_made = sum(1 for r in records if
                          r['challenge_summary']['accept'] > 0 or
                          r['challenge_summary']['reject'] > 0)
    print(f'Records with challenges: {challenges_made} ({100*challenges_made/total:.1f}%)')
    print()

    # Rebuttal impact
    print('REBUTTAL IMPACT')
    print('-'*70)
    strong_rebuttals = sum(1 for r in records if
                          r['rebuttal_summary']['accept'] >= 2 or
                          r['rebuttal_summary']['reject'] >= 2)
    print(f'Records with strong rebuttals: {strong_rebuttals} ({100*strong_rebuttals/total:.1f}%)')
    print()

    # Consensus agreement levels
    print('CONSENSUS AGREEMENT LEVELS')
    print('-'*70)
    high_confidence = sum(1 for r in records if r['consensus_confidence'] >= 0.80)
    medium_confidence = sum(1 for r in records if 0.65 <= r['consensus_confidence'] < 0.80)
    low_confidence = sum(1 for r in records if r['consensus_confidence'] < 0.65)

    print(f'High confidence (>=0.80): {high_confidence} ({100*high_confidence/total:.1f}%)')
    print(f'Medium confidence (0.65-0.79): {medium_confidence} ({100*medium_confidence/total:.1f}%)')
    print(f'Low confidence (<0.65): {low_confidence} ({100*low_confidence/total:.1f}%)')
    print()

    # Decision changes
    print('DECISION CHANGES THROUGH PROCESS')
    print('-'*70)
    primary_to_consensus_rejected = sum(1 for r in records if
                                        r['primary_summary']['accept'] >= 3 and
                                        r['consensus_decision'] == 'reject')
    primary_to_consensus_accepted = sum(1 for r in records if
                                        r['primary_summary']['accept'] < 3 and
                                        r['consensus_decision'] == 'accept')

    print(f'Primary accept -> Consensus reject: {primary_to_consensus_rejected}')
    print(f'Primary reject -> Consensus accept: {primary_to_consensus_accepted}')
    print(f'Total changes: {primary_to_consensus_rejected + primary_to_consensus_accepted} ({100*(primary_to_consensus_rejected + primary_to_consensus_accepted)/total:.1f}%)')
    print()

    # Label distribution for accepted
    print('ACCEPTED WORDS BY LABEL')
    print('-'*70)
    for label in ['brandable', 'functional', 'ambiguous']:
        count = sum(1 for r in records if r['consensus_decision'] == 'accept' and r['consensus_label'] == label)
        pct = 100 * count / accepted if accepted > 0 else 0
        print(f'{label:15} {count:4} ({pct:.1f}% of accepted)')
    print()

    # Rejection reasons
    print('REJECTION REASONS')
    print('-'*70)
    reject_reasons = Counter()
    for r in records:
        if r['consensus_decision'] == 'reject':
            reject_reasons[r['consensus_label']] += 1

    for reason, count in reject_reasons.most_common():
        pct = 100 * count / rejected if rejected > 0 else 0
        print(f'{reason:25} {count:4} ({pct:.1f}% of rejected)')
    print()

    # Sample of high-confidence accepted words
    print('SAMPLE HIGH-CONFIDENCE ACCEPTED WORDS')
    print('-'*70)
    high_conf_accepted = [r for r in records
                         if r['consensus_decision'] == 'accept'
                         and r['consensus_confidence'] >= 0.80
                         and r['normalized_word'].isalpha()
                         and len(r['normalized_word']) >= 3][:20]

    for i, r in enumerate(high_conf_accepted, 1):
        label = r['consensus_label']
        conf = r['consensus_confidence']
        word = r['normalized_word'].encode('ascii', 'replace').decode('ascii')
        print(f'{i:2}. {word:15} [{label:10}] conf={conf}')
    print()

    # Sample of rejected words
    print('SAMPLE REJECTED WORDS')
    print('-'*70)
    rejected_samples = [r for r in records
                       if r['consensus_decision'] == 'reject'][:20]

    for i, r in enumerate(rejected_samples, 1):
        reason = r['consensus_label']
        word = r['normalized_word'].encode('ascii', 'replace').decode('ascii')
        print(f'{i:2}. {word:20} [{reason}]')
    print()

    print('='*70)
    print('PROCESS COMPLETE - All three stages executed successfully')
    print('='*70)

if __name__ == '__main__':
    main()
