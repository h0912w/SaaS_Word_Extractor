#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 6: Challenge Review - Analyze primary review results and identify potential misclassifications.
This script implements 5 reviewer perspectives to challenge potentially incorrect classifications.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

# reviewer-01: Recall Guardian - SaaS-worthy words that may have been over-rejected
RECALL_GUARDIAN_PATTERNS = {
    # Single consonant + common short tech words
    'sync', 'hub', 'flow', 'pulse', 'core', 'base', 'link', 'mesh', 'grid',
    'dock', 'port', 'gate', 'node', 'cell', 'unit', 'block', 'slot',

    # Action verbs commonly used in SaaS
    'scan', 'check', 'test', 'watch', 'guard', 'shield', 'track', 'trace',
    'spot', 'find', 'seek', 'hunt', 'chase', 'mark', 'tag', 'flag',

    # Business/Process concepts
    'task', 'job', 'work', 'plan', 'goal', 'target', 'scope', 'scale',
    'rate', 'score', 'rank', 'level', 'stage', 'phase', 'step', 'state',

    # Brandable short words
    'arc', 'orb', 'sky', 'air', 'fog', 'dew', 'ice', 'ash', 'dust', 'mist',
    'mox', 'vox', 'zen', 'nod', 'dot', 'bit', 'kit', 'fit', 'jet',

    # Dynamic/Abstract
    'flux', 'drift', 'shift', 'tilt', 'turn', 'spin', 'roll', 'wave',
    'beam', 'ray', 'glow', 'spark', 'flash', 'blink', 'pop', 'snap',

    # Platform metaphors
    'deck', 'yard', 'field', 'park', 'lane', 'road', 'path', 'trail',
    'loop', 'ring', 'band', 'belt', 'zone', 'area', 'space', 'room',
}

# reviewer-02: Noise Detector - Words that should be rejected
NOISE_PATTERNS = {
    # Common function words
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
    'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his',
    'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'did',

    # Pronouns
    'i', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
    'my', 'your', 'his', 'its', 'our', 'their', 'mine', 'yours', 'ours',

    # Basic prepositions/articles
    'a', 'an', 'at', 'by', 'in', 'of', 'on', 'to', 'up', 'as', 'if', 'or',
    'so', 'no', 'go', 'do', 'be', 'is', 'am', 'are', 'was', 'were',

    # Generic nouns
    'thing', 'stuff', 'item', 'object', 'piece', 'part', 'something',
}

# reviewer-03: Brand Expert - Brandability patterns
BRANDABLE_PATTERNS = {
    # Short, punchy tech-friendly words
    'sync', 'hub', 'flow', 'pulse', 'core', 'base', 'link', 'mesh', 'grid',
    'flux', 'drift', 'shift', 'spark', 'glow', 'beam', 'wave', 'orbit',

    # Modern tech aesthetics
    'pixel', 'vector', 'tensor', 'matrix', 'cipher', 'binary', 'quantum',
    'prism', 'spectrum', 'radius', 'diameter', 'optics', 'photon',
}

# reviewer-04: Functional Expert - Functional words in SaaS
FUNCTIONAL_PATTERNS = {
    # Technical infrastructure
    'host', 'node', 'port', 'gate', 'bridge', 'router', 'switch', 'proxy',
    'cache', 'store', 'queue', 'stack', 'heap', 'pool', 'buffer',

    # Monitoring/management
    'watch', 'monitor', 'alert', 'track', 'trace', 'log', 'audit', 'check',
    'scan', 'verify', 'validate', 'prove', 'test', 'measure',

    # Data/content
    'index', 'search', 'find', 'match', 'filter', 'sort', 'group', 'split',
    'merge', 'join', 'link', 'connect', 'attach', 'bind',
}

def extract_word(record):
    """Extract the normalized word from a record."""
    if isinstance(record, dict):
        return record.get('normalized_word', '')
    return ''

def get_decision(record):
    """Determine the decision based on primary_summary."""
    if isinstance(record, dict):
        summary = record.get('primary_summary', {})
        accept_count = summary.get('accept', 0)
        reject_count = summary.get('reject', 0)

        if accept_count >= 3:
            return 'accept'
        elif reject_count >= 3:
            return 'reject'
        else:
            return 'borderline'
    return ''

def get_vote_counts(record):
    """Get all vote counts from a record."""
    if isinstance(record, dict):
        summary = record.get('primary_summary', {})
        return {
            'accept': summary.get('accept', 0),
            'reject': summary.get('reject', 0),
            'borderline': summary.get('borderline', 0)
        }
    return {'accept': 0, 'reject': 0, 'borderline': 0}

def reviewer_01_recall_guardian(word, decision, votes):
    """
    Reviewer-01: Recall Guardian
    Identifies words that were over-rejected (should have been accepted).
    """
    challenges = []

    if decision == 'reject':
        word_lower = word.lower()

        # Check against known SaaS-worthy patterns
        if word_lower in RECALL_GUARDIAN_PATTERNS:
            challenges.append({
                "reviewer_id": "challenge-reviewer-01",
                "challenge_type": "over_reject",
                "argument": f"'{word}' has strong SaaS naming potential. This type of word is commonly used in successful SaaS brands (e.g., Sync, Hub, Flow). The word is memorable, short, and tech-friendly.",
                "suggested_decision": "accept",
                "suggested_label": "functional"
            })

        # Check for close misses (2 accept votes vs 3 reject)
        elif votes['accept'] == 2 and votes['reject'] == 3:
            # Check if word has SaaS-like characteristics
            if len(word) <= 6 and word.isalpha():
                challenges.append({
                    "reviewer_id": "challenge-reviewer-01",
                    "challenge_type": "over_reject",
                    "argument": f"'{word}' narrowly missed acceptance (2-3 split). Given recall priority, this borderline case should be re-examined. Short, pronounceable words often have good SaaS branding potential.",
                    "suggested_decision": "accept",
                    "suggested_label": "review"
                })

    return challenges

def reviewer_02_noise_detector(word, decision, votes):
    """
    Reviewer-02: Noise Detector
    Identifies words that were over-accepted (should have been rejected).
    """
    challenges = []

    if decision == 'accept':
        word_lower = word.lower()

        # Check against known noise patterns
        if word_lower in NOISE_PATTERNS:
            challenges.append({
                "reviewer_id": "challenge-reviewer-02",
                "challenge_type": "over_accept",
                "argument": f"'{word}' is a common function word with minimal SaaS branding potential. These words are too generic and lack distinctiveness for brand recognition.",
                "suggested_decision": "reject",
                "suggested_label": "noise"
            })

        # Check for weak accepts (3-2 splits)
        elif votes['accept'] == 3 and votes['reject'] == 2:
            # If it's a very common short word, flag it
            if len(word) <= 3 and word_lower in NOISE_PATTERNS:
                challenges.append({
                    "reviewer_id": "challenge-reviewer-02",
                    "challenge_type": "over_accept",
                    "argument": f"'{word}' barely passed (3-2 split). This is an extremely common function word with almost no SaaS branding value. Should be reconsidered for rejection.",
                    "suggested_decision": "reject",
                    "suggested_label": "noise"
                })

    return challenges

def reviewer_03_brand_expert(word, decision, votes):
    """
    Reviewer-03: Brand Expert
    Identifies misclassified words from a brand perspective.
    """
    challenges = []
    word_lower = word.lower()

    # Rejected brandable words
    if decision == 'reject' and word_lower in BRANDABLE_PATTERNS:
        challenges.append({
            "reviewer_id": "challenge-reviewer-03",
            "challenge_type": "over_reject",
            "argument": f"'{word}' has excellent brandability. Modern SaaS companies frequently use such words for their clean, tech-forward aesthetic. This rejection may be overly conservative.",
            "suggested_decision": "accept",
            "suggested_label": "brandable"
        })

    return challenges

def reviewer_04_functional_expert(word, decision, votes):
    """
    Reviewer-04: Functional Expert
    Identifies misclassified words from a functional/technical perspective.
    """
    challenges = []
    word_lower = word.lower()

    # Rejected functional words
    if decision == 'reject' and word_lower in FUNCTIONAL_PATTERNS:
        challenges.append({
            "reviewer_id": "challenge-reviewer-04",
            "challenge_type": "over_reject",
            "argument": f"'{word}' is a functional term commonly used in technical/SaaS contexts. While it may seem generic, such words are frequently used to describe what the SaaS does (e.g., 'Monitor', 'Scan', 'Track').",
            "suggested_decision": "accept",
            "suggested_label": "functional"
        })

    return challenges

def reviewer_05_borderline_clarifier(word, decision, votes):
    """
    Reviewer-05: Borderline Clarifier
    Identifies borderline cases that could be more clearly classified.
    """
    challenges = []

    # Cases with 2 accept votes (close to acceptance)
    if votes['accept'] == 2 and decision == 'reject':
        challenges.append({
            "reviewer_id": "challenge-reviewer-05",
            "challenge_type": "borderline_clarify",
            "argument": f"'{word}' received 2 accept votes, indicating it has some SaaS potential. Under recall-priority policy, this deserves another look rather than outright rejection.",
            "suggested_decision": "review",
            "suggested_label": "borderline"
        })

    # Cases that barely passed (3-2 or 3-1-1)
    elif votes['accept'] == 3 and decision == 'accept':
        if votes['reject'] >= 2:
            challenges.append({
                "reviewer_id": "challenge-reviewer-05",
                "challenge_type": "borderline_clarify",
                "argument": f"'{word}' barely passed with significant dissent (3-{votes['reject']}). This split indicates ambiguity. Consider flagging for human review rather than automatic acceptance.",
                "suggested_decision": "review",
                "suggested_label": "borderline"
            })

    return challenges

def analyze_record(record):
    """Analyze a single record from all reviewer perspectives."""
    word = extract_word(record)
    decision = get_decision(record)
    votes = get_vote_counts(record)

    # Skip non-English or malformed words
    if not word or not word.isalpha() or len(word) < 2:
        return []

    challenges = []

    # Apply all 5 reviewer perspectives
    challenges.extend(reviewer_01_recall_guardian(word, decision, votes))
    challenges.extend(reviewer_02_noise_detector(word, decision, votes))
    challenges.extend(reviewer_03_brand_expert(word, decision, votes))
    challenges.extend(reviewer_04_functional_expert(word, decision, votes))
    challenges.extend(reviewer_05_borderline_clarifier(word, decision, votes))

    return challenges

def main():
    """Main execution function."""
    input_path = Path("C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/05_primary_reviewed.jsonl")
    output_path = Path("C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/06_challenged.jsonl")

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print("Starting challenge analysis...")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}\n")

    total_records = 0
    challenged_records = 0
    challenge_counts = defaultdict(int)

    with open(input_path, 'r', encoding='utf-8') as inp, \
         open(output_path, 'w', encoding='utf-8', newline='\n') as out:

        for line_num, line in enumerate(inp, 1):
            if not line.strip():
                continue

            total_records += 1

            try:
                record = json.loads(line)
                challenges = analyze_record(record)

                # Build output record
                if challenges:
                    challenged_records += 1

                    # Count challenge types
                    for c in challenges:
                        challenge_counts[c['challenge_type']] += 1

                    summary = {
                        "over_accept": challenge_counts.get('over_accept', 0),
                        "over_reject": challenge_counts.get('over_reject', 0),
                        "borderline_clarify": challenge_counts.get('borderline_clarify', 0)
                    }

                    output_record = {
                        **record,
                        "challenges": challenges,
                        "challenge_summary": summary,
                        "status": "AI_CHALLENGED"
                    }
                else:
                    # No challenges
                    output_record = {
                        **record,
                        "challenges": [],
                        "challenge_summary": {
                            "over_accept": 0,
                            "over_reject": 0,
                            "borderline_clarify": 0
                        },
                        "status": "AI_CHALLENGED"
                    }

                out.write(json.dumps(output_record, ensure_ascii=False) + '\n')

                # Progress indicator
                if total_records % 500 == 0:
                    print(f"Processed {total_records} records...")

            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON at line {line_num}: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Error processing line {line_num}: {e}", file=sys.stderr)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Challenge Analysis Complete")
    print(f"{'='*60}")
    print(f"Total records processed: {total_records}")
    print(f"Records with challenges: {challenged_records}")
    print(f"\nChallenge breakdown:")
    print(f"  - Over-reject challenges: {challenge_counts.get('over_reject', 0)}")
    print(f"  - Over-accept challenges: {challenge_counts.get('over_accept', 0)}")
    print(f"  - Borderline clarifications: {challenge_counts.get('borderline_clarify', 0)}")
    print(f"\nOutput: {output_path}")

if __name__ == "__main__":
    main()
