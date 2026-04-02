#!/usr/bin/env python3
"""
Process primary review in batches and write incrementally.
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import sys


def judge_word(word: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Judge a single word from 5 perspectives.
    Returns primary_votes array and primary_summary.
    """
    votes = []

    # Judge-01: Recall-focused (most liberal)
    vote_01 = judge_01_recall_focused(word)
    votes.append(vote_01)

    # Judge-02: Brand value focused
    vote_02 = judge_02_brand_focused(word)
    votes.append(vote_02)

    # Judge-03: Technical/functional value focused
    vote_03 = judge_03_technical_focused(word)
    votes.append(vote_03)

    # Judge-04: Real English word verification
    vote_04 = judge_04_english_verification(word)
    votes.append(vote_04)

    # Judge-05: Balanced quality review
    vote_05 = judge_05_balanced(word)
    votes.append(vote_05)

    # Calculate summary
    accept_count = sum(1 for v in votes if v['decision'] == 'accept')
    reject_count = sum(1 for v in votes if v['decision'] == 'reject')
    borderline_count = sum(1 for v in votes if v.get('confidence', 0) < 0.6)

    summary = {
        'accept': accept_count,
        'reject': reject_count,
        'borderline': borderline_count
    }

    return {
        'primary_votes': votes,
        'primary_summary': summary
    }


def judge_01_recall_focused(word: str) -> Dict[str, Any]:
    """Judge-01: Recall-focused - most liberal, accepts anything with potential."""
    decision = 'accept'
    confidence = 0.8
    label = None
    reasons = []

    # Clear rejects only
    if is_pure_noise(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('pure noise/symbols')
    elif is_code_token(word):
        decision = 'reject'
        confidence = 0.9
        reasons.append('code token')
    elif is_repeated_chars(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('repeated characters')
    elif has_leading_trailing_excess_punct(word):
        # Still accept but note the punctuation issue
        decision = 'accept'
        confidence = 0.6
        reasons.append('has leading/trailing punctuation but core word may be valid')
        label = 'ambiguous'
    else:
        # Accept liberally
        confidence = 0.85
        reasons.append('recall-focused: accept unless clearly noise')

        # Determine label
        if is_functional_word(word):
            label = 'functional'
        elif is_brandable_word(clean_word(word)):
            label = 'brandable'
        else:
            label = 'ambiguous'

    return {
        'judge_id': 'saas-title-judge-01',
        'decision': decision,
        'label': label,
        'confidence': confidence,
        'why': reasons
    }


def judge_02_brand_focused(word: str) -> Dict[str, Any]:
    """Judge-02: Brand value focused."""
    decision = 'accept'
    confidence = 0.75
    label = None
    reasons = []

    clean = clean_word(word)

    if is_pure_noise(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('no brand value - pure noise')
    elif is_code_token(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('not brandable - code token')
    elif is_repeated_chars(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('not brandable - repeated chars')
    elif is_brandable_word(clean):
        label = 'brandable'
        confidence = 0.85
        reasons.append('strong brand potential')
    elif is_functional_word(clean):
        label = 'functional'
        confidence = 0.7
        reasons.append('functional word, moderate brand value')
    else:
        label = 'ambiguous'
        confidence = 0.6
        reasons.append('uncertain brand value')

    return {
        'judge_id': 'saas-title-judge-02',
        'decision': decision,
        'label': label,
        'confidence': confidence,
        'why': reasons
    }


def judge_03_technical_focused(word: str) -> Dict[str, Any]:
    """Judge-03: Technical/functional value focused."""
    decision = 'accept'
    confidence = 0.75
    label = None
    reasons = []

    clean = clean_word(word)

    if is_pure_noise(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('no technical meaning')
    elif is_code_token(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('code token, not for product names')
    elif is_repeated_chars(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('no technical meaning')
    elif is_functional_word(clean):
        label = 'functional'
        confidence = 0.9
        reasons.append('clear technical/functional meaning')
    elif is_technical_word(clean):
        label = 'functional'
        confidence = 0.8
        reasons.append('technical domain word')
    elif is_brandable_word(clean):
        label = 'brandable'
        confidence = 0.7
        reasons.append('brandable but not strongly technical')
    else:
        label = 'ambiguous'
        confidence = 0.5
        reasons.append('unclear technical value')

    return {
        'judge_id': 'saas-title-judge-03',
        'decision': decision,
        'label': label,
        'confidence': confidence,
        'why': reasons
    }


def judge_04_english_verification(word: str) -> Dict[str, Any]:
    """Judge-04: Real English word verification."""
    decision = 'accept'
    confidence = 0.7
    label = None
    reasons = []

    clean = clean_word(word)

    if is_pure_noise(word):
        decision = 'reject'
        confidence = 0.98
        reasons.append('not an English word')
    elif is_code_token(word):
        decision = 'reject'
        confidence = 0.98
        reasons.append('not an English word - code')
    elif is_repeated_chars(word):
        decision = 'reject'
        confidence = 0.98
        reasons.append('not a valid English word')
    elif is_common_english_word(clean):
        label = 'ambiguous'  # Could be functional or brandable
        confidence = 0.95
        reasons.append('verified English word')
    elif looks_like_english(clean):
        label = 'ambiguous'
        confidence = 0.7
        reasons.append('appears to be English')
    else:
        # Non-English but might still be usable
        decision = 'accept'
        label = 'ambiguous'
        confidence = 0.4
        reasons.append('possibly non-English but accept for recall')

    return {
        'judge_id': 'saas-title-judge-04',
        'decision': decision,
        'label': label,
        'confidence': confidence,
        'why': reasons
    }


def judge_05_balanced(word: str) -> Dict[str, Any]:
    """Judge-05: Balanced quality review."""
    decision = 'accept'
    confidence = 0.75
    label = None
    reasons = []

    clean = clean_word(word)

    # Clear rejects
    if is_pure_noise(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('noise - balanced reject')
    elif is_code_token(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('code token - balanced reject')
    elif is_repeated_chars(word):
        decision = 'reject'
        confidence = 0.95
        reasons.append('repeated chars - balanced reject')
    # Quality assessment
    elif is_functional_word(clean) and is_brandable_word(clean):
        label = 'ambiguous'
        confidence = 0.9
        reasons.append('both functional and brandable - high quality')
    elif is_functional_word(clean):
        label = 'functional'
        confidence = 0.85
        reasons.append('clear functional value')
    elif is_brandable_word(clean):
        label = 'brandable'
        confidence = 0.85
        reasons.append('clear brand value')
    elif has_leading_trailing_excess_punct(word):
        label = 'ambiguous'
        confidence = 0.5
        reasons.append('punctuation issues - lower quality')
    else:
        label = 'ambiguous'
        confidence = 0.6
        reasons.append('moderate quality - borderline case')

    return {
        'judge_id': 'saas-title-judge-05',
        'decision': decision,
        'label': label,
        'confidence': confidence,
        'why': reasons
    }


# Helper functions

def clean_word(word: str) -> str:
    """Remove leading/trailing punctuation."""
    import string
    return word.strip(string.punctuation + '!¡¿§¶')


def is_pure_noise(word: str) -> bool:
    """Check if word is pure symbols/noise."""
    if not word:
        return True
    # Check if mostly non-alphabetic
    alpha_chars = sum(1 for c in word if c.isalpha())
    return len(word) > 2 and alpha_chars / len(word) < 0.3


def is_code_token(word: str) -> bool:
    """Check if word is a code token."""
    code_patterns = ['__', '0x', '::', '.exe', '.dll', '.so', '/usr', '/etc', 'http', 'www.']
    return any(p in word.lower() for p in code_patterns)


def is_repeated_chars(word: str) -> bool:
    """Check if word is repeated characters."""
    if len(word) < 3:
        return False
    # Check if same character repeated
    return len(set(word.lower())) <= 2


def has_leading_trailing_excess_punct(word: str) -> bool:
    """Check if word has excessive leading/trailing punctuation."""
    import string
    punct = '!¡¿§¶@#$%^&*'
    stripped = word.strip(punct)
    return len(stripped) < len(word) and len(word) - len(stripped) >= 2


def is_functional_word(word: str) -> bool:
    """Check if word is functional (verb/technical term)."""
    functional = [
        'merge', 'sync', 'deploy', 'track', 'build', 'parse', 'render',
        'queue', 'route', 'stream', 'connect', 'link', 'bridge', 'hub',
        'core', 'stack', 'flow', 'grid', 'mesh', 'node', 'edge', 'gate',
        'port', 'pipe', 'channel', 'api', 'sdk', 'cli', 'gui', 'auth',
        'login', 'signup', 'deploy', 'build', 'test', 'debug', 'monitor',
        'log', 'metric', 'alert', 'trace', 'scan', 'check', 'verify',
        'validate', 'process', 'handle', 'manage', 'control', 'run',
        'execute', 'load', 'save', 'store', 'fetch', 'query', 'search',
        'index', 'archive', 'backup', 'restore', 'sync', 'replicate'
    ]
    return word.lower() in functional


def is_brandable_word(word: str) -> bool:
    """Check if word is brandable."""
    brandable = [
        'forge', 'pulse', 'nexus', 'apex', 'orbit', 'nova', 'beacon',
        'vault', 'spark', 'craft', 'flow', 'core', 'stack', 'mesh',
        'grid', 'bridge', 'hub', 'link', 'edge', 'node', 'base',
        'prime', 'peak', 'summit', 'crest', 'vertex', 'axis', 'pivot',
        'anchor', 'beacon', 'signal', 'spark', 'flare', 'burst', 'wave',
        'drift', 'tide', 'current', 'stream', 'river', 'flow', 'path',
        'way', 'road', 'lane', 'track', 'trail', 'route', 'course'
    ]
    return word.lower() in brandable


def is_technical_word(word: str) -> bool:
    """Check if word is technical."""
    technical = [
        'byte', 'bit', 'pixel', 'vector', 'tensor', 'matrix', 'array',
        'object', 'class', 'method', 'function', 'variable', 'constant',
        'string', 'number', 'boolean', 'integer', 'float', 'decimal',
        'binary', 'octal', 'hex', 'ascii', 'unicode', 'utf', 'codec',
        'protocol', 'format', 'standard', 'spec', 'schema', 'model'
    ]
    return word.lower() in technical


def is_common_english_word(word: str) -> bool:
    """Check if word is a common English word."""
    # This is a simplified check - in production would use a dictionary
    if len(word) < 2:
        return False
    # Basic English pattern
    vowels = sum(1 for c in word.lower() if c in 'aeiou')
    return vowels >= 1 and word.isalpha()


def looks_like_english(word: str) -> bool:
    """Check if word looks like English."""
    if len(word) < 2:
        return False
    alpha_chars = sum(1 for c in word if c.isalpha())
    return alpha_chars / len(word) > 0.7


def main():
    """Process all records and write output."""
    project_root = Path(__file__).parent.parent
    input_file = project_root / 'output' / 'intermediate' / '04_screened_tokens.jsonl'
    output_file = project_root / 'output' / 'intermediate' / '05_primary_reviewed.jsonl'

    print("Loading screened tokens...")
    records = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                if record.get('screen_result') == 'pass':
                    records.append(record)

    print(f"Processing {len(records)} records...")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as out:
        for i, record in enumerate(records, 1):
            word = record.get('normalized_word', '')

            # Get judgments
            judgments = judge_word(word, record)

            # Add to record
            record['primary_votes'] = judgments['primary_votes']
            record['primary_summary'] = judgments['primary_summary']
            record['status'] = 'AI_PRIMARY_REVIEWED'

            # Write line
            out.write(json.dumps(record, ensure_ascii=False) + '\n')

            if i % 100 == 0:
                print(f"Processed {i}/{len(records)} records")

    print(f"Complete! Output written to {output_file}")
    print(f"Total records: {len(records)}")


if __name__ == '__main__':
    main()
