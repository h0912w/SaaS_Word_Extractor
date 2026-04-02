#!/usr/bin/env python3
"""
Step 6: Challenge Review

Analyzes primary review results from Step 5 and identifies potentially
misjudged words from 5 different reviewer perspectives:
- reviewer-01: Recall guardian (finds over-rejected)
- reviewer-02: Noise detector (finds over-accepted)
- reviewer-03: Brand expert
- reviewer-04: Functional expert
- reviewer-05: Borderline adjuster
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any


def load_primary_review(input_path: Path) -> List[Dict[str, Any]]:
    """Load primary review results from JSONL file."""
    records = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def should_challenge_word(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Analyze a word and determine if it should be challenged.
    Returns a list of challenge objects (empty if no challenges).
    """
    challenges = []
    word = record.get('normalized_word', '')
    raw_token = record.get('raw_token', '')
    primary_summary = record.get('primary_summary', {})
    accept_count = primary_summary.get('accept', 0)
    reject_count = primary_summary.get('reject', 0)
    borderline_count = primary_summary.get('borderline', 0)

    # Get labels from votes
    labels = []
    for vote in record.get('primary_votes', []):
        label = vote.get('label', '')
        if label:
            labels.append(label)

    # Calculate decision (accept if >= 3 accept votes)
    was_accepted = accept_count >= 3

    # Common stop words and function words that are clearly noise for SaaS titles
    common_stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this',
        'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
        'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our',
        'their', 'mine', 'yours', 'hers', 'ours', 'theirs', 'what', 'which',
        'who', 'whom', 'whose', 'where', 'when', 'why', 'how', 'all', 'each',
        'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
        'also', 'now', 'here', 'there', 'then', 'once', 'about', 'into',
        'through', 'during', 'before', 'after', 'above', 'below', 'between',
        'under', 'again', 'further', 'while', 'until', 'up', 'down', 'off',
        'over', 'out', 'if', 'else', 'because', 'although', 'though', 'since',
        'unless', 'until', 'while', 'whereas', 'whether', 'either', 'neither',
        'nor', 'so', 'yet', 'however', 'therefore', 'moreover', 'nevertheless',
        'nonetheless', 'accordingly', 'consequently', 'thus', 'hence',
        'otherwise', 'anyway', 'anyhow', 'anywhere', 'somewhere', 'nowhere',
        'everyone', 'everybody', 'someone', 'somebody', 'anyone', 'anybody',
        'noone', 'nobody', 'nothing', 'something', 'anything', 'someone',
        'someone', 'sometime', 'always', 'never', 'often', 'sometimes',
        'usually', 'generally', 'frequently', 'rarely', 'seldom', 'hardly',
        'scarcely', 'barely', 'quite', 'rather', 'pretty', 'fairly', 'somewhat'
    }

    # Patterns indicating noise or non-words
    noise_patterns = [
        '!!!', '###', '***', '---', '___',  # Excessive punctuation
        'fuck', 'shit', 'damn', 'crap',  # Profanity (rarely good for SaaS)
    ]

    # REVIEWER-01: Recall Guardian - finds over-rejected words
    if not was_accepted:
        # Skip stopwords entirely for over-reject challenges
        if word.lower() not in common_stopwords:
            # Skip clearly problematic words
            problematic = {'ass', 'bab', 'bbf', 'mama', 'papa', 'dada', 'bobo', 'lala'}
            if word.lower() in problematic:
                pass  # Don't challenge these
            # Check if this is actually a good SaaS word that was rejected
            # Technical/functional words with high SaaS potential
            elif any(word.endswith(suffix) for suffix in ['api', 'ai', 'io', 'ly', 'ify', 'hub', 'lab', 'ops', 'sys']):
                challenges.append({
                    "reviewer_id": "challenge-reviewer-01",
                    "challenge_type": "over_reject",
                    "argument": f"Word '{word}' has technical SaaS-friendly suffix/pattern",
                    "suggested_decision": "accept",
                    "suggested_label": "functional"
                })

            # Short brandable words (4-6 chars, slightly more conservative)
            elif 4 <= len(word) <= 6 and word.isalpha() and word.islower():
                # Check if it's not clearly noise
                if not any(pattern in word.lower() for pattern in noise_patterns):
                    # At least 2 vowels for better phonetic quality
                    vowels = sum(1 for c in word if c in 'aeiou')
                    if vowels >= 2:
                        challenges.append({
                            "reviewer_id": "challenge-reviewer-01",
                            "challenge_type": "over_reject",
                            "argument": f"Short brandable word '{word}' may have SaaS potential",
                            "suggested_decision": "accept",
                            "suggested_label": "brandable"
                        })

            # Verbs (often good for SaaS - action-oriented)
            elif len(word) >= 5 and word.endswith(('e', 'n', 'r', 's')):
                # Simple heuristic for potential verbs
                if word.isalpha():
                    challenges.append({
                        "reviewer_id": "challenge-reviewer-01",
                        "challenge_type": "over_reject",
                        "argument": f"Word '{word}' may be a verb with functional SaaS value",
                        "suggested_decision": "accept",
                        "suggested_label": "functional"
                    })

    # REVIEWER-02: Noise Detector - finds over-accepted noise
    if was_accepted:
        # Profanity with punctuation
        if any(pattern in word.lower() for pattern in ['fuck', 'shit']):
            challenges.append({
                "reviewer_id": "challenge-reviewer-02",
                "challenge_type": "over_accept",
                "argument": f"Word '{word}' contains profanity - inappropriate for SaaS titles",
                "suggested_decision": "reject",
                "suggested_label": "noise"
            })

        # Common stopwords that add no value
        elif word.lower() in common_stopwords:
            challenges.append({
                "reviewer_id": "challenge-reviewer-02",
                "challenge_type": "over_accept",
                "argument": f"Word '{word}' is a common stopword with no SaaS title value",
                "suggested_decision": "reject",
                "suggested_label": "stopword"
            })

        # Excessive punctuation
        elif sum(1 for c in word if c in '!@#$%^&*()_+=-[]{}|;:",.<>?/') > len(word) / 2:
            challenges.append({
                "reviewer_id": "challenge-reviewer-02",
                "challenge_type": "over_accept",
                "argument": f"Word '{word}' has excessive punctuation - likely noise",
                "suggested_decision": "reject",
                "suggested_label": "noise"
            })

        # Numbers only
        elif word.isdigit():
            challenges.append({
                "reviewer_id": "challenge-reviewer-02",
                "challenge_type": "over_accept",
                "argument": f"Word '{word}' is numeric only - not a valid SaaS title",
                "suggested_decision": "reject",
                "suggested_label": "noise"
            })

        # Very long words (likely phrases or technical jargon)
        elif len(word) > 20:
            challenges.append({
                "reviewer_id": "challenge-reviewer-02",
                "challenge_type": "over_accept",
                "argument": f"Word '{word}' is too long for a practical SaaS title",
                "suggested_decision": "reject",
                "suggested_label": "noise"
            })

    # REVIEWER-03: Brand Expert - brand perspective
    if was_accepted:
        # Words that are too generic for branding
        generic_words = {'system', 'service', 'product', 'solution', 'platform', 'tool'}
        if word.lower() in generic_words:
            challenges.append({
                "reviewer_id": "challenge-reviewer-03",
                "challenge_type": "over_accept",
                "argument": f"Word '{word}' is too generic for distinctive SaaS branding",
                "suggested_decision": "reject",
                "suggested_label": "generic"
            })
    else:
        # Brandable words that were rejected
        # Skip stopwords and problematic words
        if word.lower() not in common_stopwords:
            problematic = {'ass', 'bab', 'bbf', 'mama', 'papa', 'dada', 'bobo', 'lala', 'aka'}
            if word.lower() not in problematic:
                # Short, memorable words with pleasant sounds
                vowels = sum(1 for c in word if c in 'aeiou')
                if 4 <= len(word) <= 6 and word.isalpha() and vowels >= 2:
                    # Has good vowel ratio for brandability
                    challenges.append({
                        "reviewer_id": "challenge-reviewer-03",
                        "challenge_type": "over_reject",
                        "argument": f"Word '{word}' has good phonetic properties for branding",
                        "suggested_decision": "accept",
                        "suggested_label": "brandable"
                    })

    # REVIEWER-04: Functional Expert - technical/functional perspective
    if was_accepted:
        # Clearly non-technical words accepted as technical
        non_technical = {'good', 'bad', 'big', 'small', 'old', 'new', 'hot', 'cold'}
        if word.lower() in non_technical:
            if labels.count('functional') >= 2:
                challenges.append({
                    "reviewer_id": "challenge-reviewer-04",
                    "challenge_type": "over_accept",
                    "argument": f"Word '{word}' is not truly technical/functional",
                    "suggested_decision": "reject",
                    "suggested_label": "noise"
                })
    else:
        # Technical indicators that were rejected
        tech_prefixes = ['auto', 'micro', 'multi', 'ultra', 'hyper', 'meta', 'para', 'pseudo']
        if any(word.lower().startswith(prefix) for prefix in tech_prefixes):
            if len(word) >= 5:
                challenges.append({
                    "reviewer_id": "challenge-reviewer-04",
                    "challenge_type": "over_reject",
                    "argument": f"Word '{word}' has technical prefix suggesting functional value",
                    "suggested_decision": "accept",
                    "suggested_label": "functional"
                })

    # REVIEWER-05: Borderline Adjuster - clarifies borderline cases
    if borderline_count >= 3:
        # Too uncertain - should lean one way
        if word.lower() in common_stopwords:
            challenges.append({
                "reviewer_id": "challenge-reviewer-05",
                "challenge_type": "borderline_clarify",
                "argument": f"Borderline word '{word}' is clearly a stopword - should reject",
                "suggested_decision": "reject",
                "suggested_label": "stopword"
            })
        elif word.isalpha() and 3 <= len(word) <= 8:
            challenges.append({
                "reviewer_id": "challenge-reviewer-05",
                "challenge_type": "borderline_clarify",
                "argument": f"Borderline word '{word}' has reasonable length - lean toward accept",
                "suggested_decision": "accept",
                "suggested_label": "ambiguous"
            })

    return challenges


def process_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process all records and add challenges."""
    processed = []

    for record in records:
        challenges = should_challenge_word(record)

        # Add challenge fields
        record['challenges'] = challenges

        # Calculate challenge summary
        challenge_summary = {
            "over_accept": sum(1 for c in challenges if c['challenge_type'] == 'over_accept'),
            "over_reject": sum(1 for c in challenges if c['challenge_type'] == 'over_reject'),
            "borderline_clarify": sum(1 for c in challenges if c['challenge_type'] == 'borderline_clarify')
        }
        record['challenge_summary'] = challenge_summary

        # Update status
        record['status'] = 'AI_CHALLENGED'

        processed.append(record)

    return processed


def write_challenged_records(records: List[Dict[str, Any]], output_path: Path) -> None:
    """Write challenged records to JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"Written {len(records)} records to {output_path}")


def print_summary(records: List[Dict[str, Any]]) -> None:
    """Print summary of challenges."""
    total = len(records)
    with_challenges = sum(1 for r in records if r['challenges'])

    total_over_accept = sum(r['challenge_summary']['over_accept'] for r in records)
    total_over_reject = sum(r['challenge_summary']['over_reject'] for r in records)
    total_borderline = sum(r['challenge_summary']['borderline_clarify'] for r in records)

    print(f"\n{'='*60}")
    print(f"CHALLENGE REVIEW SUMMARY")
    print(f"{'='*60}")
    print(f"Total records processed: {total}")
    print(f"Records with challenges: {with_challenges} ({100*with_challenges/total:.1f}%)")
    print(f"\nChallenge types:")
    print(f"  - Over-accept challenges: {total_over_accept}")
    print(f"  - Over-reject challenges: {total_over_reject}")
    print(f"  - Borderline clarifications: {total_borderline}")
    print(f"{'='*60}\n")


def main():
    """Main execution."""
    input_path = Path("C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/05_primary_reviewed.jsonl")
    output_path = Path("C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/06_challenged.jsonl")

    print("Loading primary review results...")
    records = load_primary_review(input_path)
    print(f"Loaded {len(records)} records")

    print("Analyzing and generating challenges...")
    processed = process_records(records)

    print("Writing challenged records...")
    write_challenged_records(processed, output_path)

    print_summary(processed)


if __name__ == "__main__":
    main()
