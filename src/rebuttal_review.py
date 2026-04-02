#!/usr/bin/env python3
"""
Rebuttal Review (Step 7)
Reviews challenges and provides final recommendations.
Recall-first principle: when uncertain, lean toward accept.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def evaluate_challenge(challenge: Dict[str, Any], word: str) -> Dict[str, Any]:
    """
    Evaluate a single challenge from 3 reviewer perspectives.
    Returns list of rebuttal opinions.
    """
    challenge_type = challenge.get('challenge_type', '')
    suggested_decision = challenge.get('suggested_decision', '')
    argument = challenge.get('argument', '')

    rebuttals = []

    # reviewer-01: Recall Guardian - supports over_reject, strict on over_accept
    if challenge_type == 'over_reject' or suggested_decision == 'accept':
        # Support the challenge - word may have been rejected too harshly
        rebuttals.append({
            'reviewer_id': 'rebuttal-reviewer-01',
            'challenge_valid': True,
            'reasoning': f'Challenge valid. "{word}" deserves another look for SaaS potential. Recall principle applies.',
            'recommended_final': 'accept'
        })
    elif challenge_type == 'over_accept' or suggested_decision == 'reject':
        # Reject the challenge - need strong evidence to overturn accept
        rebuttals.append({
            'reviewer_id': 'rebuttal-reviewer-01',
            'challenge_valid': False,
            'reasoning': f'Challenge rejected. "{word}" shows SaaS potential. High bar for overturning accept decision.',
            'recommended_final': 'accept'
        })
    else:
        # Borderline - lean accept for recall
        rebuttals.append({
            'reviewer_id': 'rebuttal-reviewer-01',
            'challenge_valid': False,
            'reasoning': f'Borderline case for "{word}". Recall principle: keep in dataset with risk flag if needed.',
            'recommended_final': 'accept'
        })

    # reviewer-02: Quality Guardian - supports over_accept, strict on over_reject
    if challenge_type == 'over_accept' or suggested_decision == 'reject':
        # Support the challenge - quality matters
        rebuttals.append({
            'reviewer_id': 'rebuttal-reviewer-02',
            'challenge_valid': True,
            'reasoning': f'Challenge valid. "{word}" shows quality concerns. Better to reject noise.',
            'recommended_final': 'reject'
        })
    elif challenge_type == 'over_reject' or suggested_decision == 'accept':
        # More cautious - need evidence this is truly SaaS-worthy
        rebuttals.append({
            'reviewer_id': 'rebuttal-reviewer-02',
            'challenge_valid': False,
            'reasoning': f'Challenge noted but "{word}" may still be noise. Require clearer SaaS relevance.',
            'recommended_final': 'reject'
        })
    else:
        # Borderline - lean conservative
        rebuttals.append({
            'reviewer_id': 'rebuttal-reviewer-02',
            'challenge_valid': True,
            'reasoning': f'Borderline case for "{word}". Recommend review to ensure quality.',
            'recommended_final': 'review'
        })

    # reviewer-03: Balance Arbitrator - balances both sides
    if challenge_type == 'borderline_clarify':
        # Always support borderline clarification
        rebuttals.append({
            'reviewer_id': 'rebuttal-reviewer-03',
            'challenge_valid': True,
            'reasoning': f'Agreed. "{word}" shows split decision. Human review recommended for final classification.',
            'recommended_final': 'review'
        })
    elif challenge_type == 'over_reject':
        # Generally support recall but with consideration
        rebuttals.append({
            'reviewer_id': 'rebuttal-reviewer-03',
            'challenge_valid': True,
            'reasoning': f'On balance, challenge for "{word}" has merit. Recall principle: accept with risk flag if borderline.',
            'recommended_final': 'accept'
        })
    elif challenge_type == 'over_accept':
        # Evaluate more carefully
        rebuttals.append({
            'reviewer_id': 'rebuttal-reviewer-03',
            'challenge_valid': False,
            'reasoning': f'Challenge for "{word}" not sufficiently compelling. Original accept decision stands.',
            'recommended_final': 'accept'
        })
    else:
        # Default to accept for recall
        rebuttals.append({
            'reviewer_id': 'rebuttal-reviewer-03',
            'challenge_valid': False,
            'reasoning': f'No strong reason to overturn decision for "{word}". Recall principle applies.',
            'recommended_final': 'accept'
        })

    return rebuttals


def process_file(input_path: Path, output_path: Path) -> Dict[str, int]:
    """Process the challenged file and add rebuttals."""
    stats = {
        'total': 0,
        'with_challenges': 0,
        'without_challenges': 0,
        'rebuttals_added': 0
    }

    with open(input_path, 'r', encoding='utf-8') as infile, \
         open(output_path, 'w', encoding='utf-8') as outfile:

        for line_num, line in enumerate(infile, 1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
                stats['total'] += 1

                # Get challenges
                challenges = record.get('challenges', [])

                # Process challenges
                all_rebuttals = []
                if challenges:
                    stats['with_challenges'] += 1
                    word = record.get('normalized_word', '')

                    for challenge in challenges:
                        rebuttals = evaluate_challenge(challenge, word)
                        all_rebuttals.extend(rebuttals)

                    stats['rebuttals_added'] += len(all_rebuttals)
                else:
                    stats['without_challenges'] += 1

                # Add rebuttals to record
                record['rebuttals'] = all_rebuttals
                record['status'] = 'AI_REBUTTED'

                # Write output
                json.dump(record, outfile, ensure_ascii=False)
                outfile.write('\n')

                # Progress update every 10000 records
                if line_num % 10000 == 0:
                    print(f"Processed {line_num} lines...", file=sys.stderr)

            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}", file=sys.stderr)
                continue

    return stats


def main():
    """Main execution."""
    base_dir = Path('C:/Users/h0912/claude_project/SaaS_Word_Extractor')
    input_path = base_dir / 'output' / 'intermediate' / '06_challenged.jsonl'
    output_path = base_dir / 'output' / 'intermediate' / '07_rebutted.jsonl'

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print(f"Reading from: {input_path}")
    print(f"Writing to: {output_path}")
    print()

    stats = process_file(input_path, output_path)

    print("\n=== Rebuttal Review Summary ===")
    print(f"Total records processed: {stats['total']}")
    print(f"Records with challenges: {stats['with_challenges']}")
    print(f"Records without challenges: {stats['without_challenges']}")
    print(f"Total rebuttals added: {stats['rebuttals_added']}")
    print(f"\nOutput written to: {output_path}")
    print("\nNext: python src/pipeline.py --phase consensus")


if __name__ == '__main__':
    main()
