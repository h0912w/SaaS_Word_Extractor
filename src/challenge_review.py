#!/usr/bin/env python3
"""
Challenge Review (Step 6)
Adds 5 reviewer perspectives to challenge primary review decisions.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


def is_noise_word(word: str) -> bool:
    """Check if word is clearly noise/non-word that should be rejected."""
    # Words with excessive punctuation/special chars
    if word.count('!') >= 2 or word.count('?') >= 2:
        return True
    # Non-ASCII dominant (more than 50% non-ASCII)
    ascii_count = sum(1 for c in word if ord(c) < 128)
    if len(word) > 0 and ascii_count / len(word) < 0.5:
        return True
    # Pure punctuation
    if all(not c.isalnum() for c in word):
        return True
    return False


def has_saas_potential(word: str) -> bool:
    """Check if rejected word might have SaaS potential (over-reject check)."""
    word_lower = word.lower()

    # Known SaaS/tech words that might be incorrectly rejected
    saas_patterns = [
        'flow', 'sync', 'cloud', 'hub', 'spot', 'base', 'bot', 'io', 'ly',
        'ify', 'lab', 'ops', 'dev', 'api', 'app', 'web', 'net', 'sys',
        'data', 'code', 'tool', 'kit', 'box', 'deck', 'board', 'sheet',
        'doc', 'file', 'note', 'task', 'team', 'work', 'time', 'track',
        'dash', 'view', 'page', 'site', 'link', 'chat', 'mail', 'message',
        'alert', 'report', 'log', 'stat', 'metric', 'analyt', 'chart',
        'graph', 'map', 'plan', 'goal', 'target', 'milestone', 'project',
        'sprint', 'scrum', 'agile', 'kanban', 'ticket', 'issue', 'bug'
    ]

    return any(pattern in word_lower for pattern in saas_patterns)


def is_brandable(word: str) -> bool:
    """Check if word has strong brand potential."""
    # Short, punchy words (3-6 letters)
    if 3 <= len(word) <= 6:
        # Has pleasant sound/structure
        vowels = sum(1 for c in word.lower() if c in 'aeiou')
        if vowels >= 1:
            return True
    return False


def review_challenges(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply 5 reviewer perspectives to challenge decisions."""
    challenges = []
    word = record.get('normalized_word', '')
    summary = record.get('primary_summary', {})

    accept_votes = summary.get('accept', 0)
    reject_votes = summary.get('reject', 0)
    borderline_votes = summary.get('borderline', 0)

    # Only review AI_PRIMARY_REVIEWED records
    if record.get('status') != 'AI_PRIMARY_REVIEWED':
        return challenges

    # reviewer-01: Recall Guardian - look for over-rejects (KEEP)
    if accept_votes < 2 and reject_votes >= 2:  # Updated threshold for 3 judges
        if has_saas_potential(word):
            challenges.append({
                'reviewer_id': 'challenge-reviewer-01',
                'challenge_type': 'over_reject',
                'argument': f'Word "{word}" contains SaaS-related patterns and may have been over-rejected. SaaS titles frequently use such functional terms.',
                'suggested_decision': 'accept',
                'suggested_label': 'functional'
            })

    # reviewer-02: Noise Detector - look for over-accepts (KEEP)
    if accept_votes >= 2:  # Updated threshold for 3 judges
        if is_noise_word(word):
            challenges.append({
                'reviewer_id': 'challenge-reviewer-02',
                'challenge_type': 'over_accept',
                'argument': f'Word "{word}" appears to be noise or non-word with excessive punctuation/special characters.',
                'suggested_decision': 'reject',
                'suggested_label': 'noise'
            })

    # REMOVED: reviewer-03 (Brand Expert), reviewer-04 (Functional Expert), reviewer-05 (Boundary Adjuster)
    # These perspectives are already covered by the primary review judges

    return challenges


def process_file(input_path: Path, output_path: Path) -> Dict[str, int]:
    """Process the primary reviewed file and add challenges."""
    stats = {
        'total': 0,
        'challenged': 0,
        'unchallenged': 0,
        'over_accept_challenges': 0,
        'over_reject_challenges': 0,
        'borderline_challenges': 0
    }

    with open(input_path, 'r', encoding='utf-8', errors='ignore') as infile, \
         open(output_path, 'w', encoding='utf-8') as outfile:

        for line_num, line in enumerate(infile, 1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
                stats['total'] += 1

                # Skip non-AI_PRIMARY_REVIEWED records
                if record.get('status') != 'AI_PRIMARY_REVIEWED':
                    json.dump(record, outfile, ensure_ascii=False)
                    outfile.write('\n')
                    continue

                # Apply challenges
                challenges = review_challenges(record)

                # Add challenge metadata to record
                record['challenges'] = challenges

                # Count challenge types
                over_accept = sum(1 for c in challenges if c['challenge_type'] == 'over_accept')
                over_reject = sum(1 for c in challenges if c['challenge_type'] == 'over_reject')
                borderline = sum(1 for c in challenges if c['challenge_type'] == 'borderline_clarify')

                record['challenge_summary'] = {
                    'over_accept': over_accept,
                    'over_reject': over_reject,
                    'borderline_clarify': borderline
                }

                record['status'] = 'AI_CHALLENGED'

                # Update stats
                if challenges:
                    stats['challenged'] += 1
                    stats['over_accept_challenges'] += over_accept
                    stats['over_reject_challenges'] += over_reject
                    stats['borderline_challenges'] += borderline
                else:
                    stats['unchallenged'] += 1

                # Write output
                json.dump(record, outfile, ensure_ascii=False)
                outfile.write('\n')

                # Progress update every 1000 records
                if line_num % 1000 == 0:
                    print(f"Processed {line_num} lines...", file=sys.stderr)

            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}", file=sys.stderr)
                continue

    return stats


def main():
    """Main execution."""
    base_dir = Path('C:/Users/h0912/claude_project/SaaS_Word_Extractor')
    input_path = base_dir / 'output' / 'intermediate' / '05_primary_reviewed_new.jsonl'
    output_path = base_dir / 'output' / 'intermediate' / '06_challenged.jsonl'

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print(f"Reading from: {input_path}")
    print(f"Writing to: {output_path}")
    print()

    stats = process_file(input_path, output_path)

    print("\n=== Challenge Review Summary ===")
    print(f"Total records processed: {stats['total']}")
    print(f"Records with challenges: {stats['challenged']}")
    print(f"Records without challenges: {stats['unchallenged']}")
    print(f"\nChallenge breakdown:")
    print(f"  Over-accept challenges: {stats['over_accept_challenges']}")
    print(f"  Over-reject challenges: {stats['over_reject_challenges']}")
    print(f"  Borderline clarifications: {stats['borderline_challenges']}")
    print(f"\nOutput written to: {output_path}")


if __name__ == '__main__':
    main()
