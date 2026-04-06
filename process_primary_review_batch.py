#!/usr/bin/env python3
"""
Primary Review Batch Processor for SaaS Title Judgment
Processes tokens in batches and generates primary review decisions
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Configuration
INPUT_FILE = Path("output/intermediate/04_screened_tokens.jsonl")
OUTPUT_FILE = Path("output/intermediate/05_primary_reviewed.jsonl")
BATCH_SIZE = 200
START_BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 0

# Judge definitions
JUDGES = [
    "saas-title-judge-01",  # Recall-focused (most permissive)
    "saas-title-judge-02",  # Brand value focused
    "saas-title-judge-03",  # Technical/functional value focused
    "saas-title-judge-04",  # Real English word focused
    "saas-title-judge-05",  # Balanced quality reviewer
]

def judge_word_01_recall_focused(word: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Most permissive - accepts if any possibility exists"""
    word_lower = word.lower()

    # Reject only for clear noise
    if any(c in word for c in '!@#$%^&*()+=[]{}|;:,.<>?/~`' if c not in {'-', "'"}):
        if len([c for c in word if c in '!@#$%^&*()+=[]{}|;:,.<>?/~`']) > 2:
            return {"decision": "reject", "label": "reject", "confidence": 0.9, "why": ["too many special chars"]}

    # Check for reversed text
    if word_lower in ['gnimoc', 'edoc', 'gnitset', 'pooloop', 'wonk']:
        return {"decision": "reject", "label": "reject", "confidence": 0.95, "why": ["reversed text"]}

    # Accept almost all real words
    return {"decision": "accept", "label": "ambiguous", "confidence": 0.7, "why": ["potential SaaS use"]}

def judge_word_02_brand_focused(word: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Brand value focused - looks for brandable qualities"""
    word_lower = word.lower()

    # Strong brand words
    brand_words = ['forge', 'pulse', 'nexus', 'apex', 'orbit', 'nova', 'beacon', 'vault',
                   'spark', 'craft', 'bolt', 'arc', 'ion', 'flint', 'rock', 'stone',
                   'surge', 'flame', 'blaze', 'glow', 'flow', 'core', 'stack', 'mesh',
                   'grid', 'bridge', 'hub', 'sphere', 'loop', 'vortex', 'spin']

    if word_lower in brand_words:
        return {"decision": "accept", "label": "brandable", "confidence": 0.95, "why": ["strong brand image"]}

    # Brandable sound patterns
    if len(word) <= 8 and any(word.endswith(suffix) for suffix in ['ify', 'io', 'ia', 'ium', 'ex']):
        return {"decision": "accept", "label": "brandable", "confidence": 0.8, "why": ["brandable sound pattern"]}

    # Reject generic/unbranded
    generic = ['the', 'and', 'for', 'with', 'from', 'have', 'this', 'that', 'been', 'were']
    if word_lower in generic:
        return {"decision": "reject", "label": "generic", "confidence": 0.9, "why": ["too generic for brand"]}

    return {"decision": "accept", "label": "ambiguous", "confidence": 0.6, "why": ["possible brand use"]}

def judge_word_03_functional_focused(word: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Technical/functional value focused"""
    word_lower = word.lower()

    # Functional SaaS verbs
    functional_verbs = ['sync', 'merge', 'deploy', 'track', 'build', 'parse', 'render',
                        'queue', 'route', 'stream', 'crawl', 'scrape', 'index', 'search',
                        'filter', 'sort', 'group', 'compute', 'validate', 'encrypt',
                        'backup', 'monitor', 'log', 'audit', 'cache', 'proxy']

    if word_lower in functional_verbs:
        return {"decision": "accept", "label": "functional", "confidence": 0.95, "why": ["clear SaaS function"]}

    # Business/tech nouns
    tech_nouns = ['payment', 'invoice', 'order', 'cart', 'inventory', 'catalog',
                  'subscription', 'account', 'profile', 'dashboard', 'analytics',
                  'metrics', 'report', 'api', 'sdk', 'framework', 'platform']

    if word_lower in tech_nouns:
        return {"decision": "accept", "label": "functional", "confidence": 0.9, "why": ["business/tech term"]}

    # Reject non-functional
    if len(word) > 15 or any(c in word for c in '!@#$%^&*()+=[]{}|;:,.<>?/~`' if c not in {"-", "'"}):
        return {"decision": "reject", "label": "non_functional", "confidence": 0.85, "why": ["not clearly functional"]}

    return {"decision": "accept", "label": "ambiguous", "confidence": 0.65, "why": ["potential functional use"]}

def judge_word_04_english_word_focused(word: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Real English word verification"""
    word_lower = word.lower()

    # Non-English indicators
    non_english_patterns = ['ñ', 'ü', 'ö', 'ä', 'ß', 'ø', 'æ', 'œ', 'đ']
    if any(c in word for c in non_english_patterns):
        return {"decision": "reject", "label": "non_english", "confidence": 0.9, "why": ["non-english characters"]}

    # Common non-English words
    non_english = ['que', 'corra', 'voz', 'alfaro', 'vive', 'adios', 'amigos', 'alabadle',
                   'alarma', 'luchar', 'yawa', 'ekat', 'gnimoc', 'carajo']

    if word_lower in non_english:
        return {"decision": "reject", "label": "non_english", "confidence": 0.85, "why": ["likely non-english word"]}

    # Technical English words for SaaS
    tech_english = ['album', 'discography', 'action', 'pact', 'magazine', 'records',
                    'revolution', 'mark', 'point', 'language', 'destroy', 'going',
                    'places', 'time', 'quarterback', 'source', 'target', 'master',
                    'server', 'client', 'host', 'port', 'socket', 'stream', 'pipe']

    if word_lower in tech_english:
        return {"decision": "accept", "label": "functional", "confidence": 0.9, "why": ["valid english word"]}

    return {"decision": "accept", "label": "ambiguous", "confidence": 0.7, "why": ["appears to be english"]}

def judge_word_05_balanced_quality(word: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Balanced quality reviewer - considers all factors"""
    word_lower = word.lower()

    # Clear rejects
    if len(word) < 2:
        return {"decision": "reject", "label": "too_short", "confidence": 0.95, "why": ["too short"]}

    if any(c in word for c in '!@#$%^&*()+=[]{}|;:,.<>?/~`' if c not in {'-', "'"}):
        special_count = len([c for c in word if c in '!@#$%^&*()+=[]{}|;:,.<>?/~`'])
        if special_count > 1:
            return {"decision": "reject", "label": "noisy", "confidence": 0.85, "why": ["too noisy"]}

    # High quality accepts
    high_quality = ['sync', 'forge', 'pulse', 'nexus', 'apex', 'deploy', 'track',
                    'build', 'core', 'stack', 'flow', 'hub', 'bridge', 'vault',
                    'spark', 'craft', 'bolt', 'grid', 'mesh', 'orbit']

    if word_lower in high_quality:
        return {"decision": "accept", "label": "brandable", "confidence": 0.95, "why": ["high quality SaaS term"]}

    # Balanced decision for others
    return {"decision": "accept", "label": "ambiguous", "confidence": 0.6, "why": ["acceptable but unclear category"]}

def process_batch(tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process a batch of tokens through all 5 judges"""

    judges = [
        judge_word_01_recall_focused,
        judge_word_02_brand_focused,
        judge_word_03_functional_focused,
        judge_word_04_english_word_focused,
        judge_word_05_balanced_quality
    ]

    results = []

    for token in tokens:
        word = token['normalized_word']
        primary_votes = []

        # Get votes from all 5 judges
        for i, judge_func in enumerate(judges):
            judge_id = JUDGES[i]
            judgment = judge_func(word, token)
            primary_votes.append({
                "judge_id": judge_id,
                "decision": judgment["decision"],
                "label": judgment["label"],
                "confidence": judgment["confidence"],
                "why": judgment["why"]
            })

        # Calculate summary
        accept_count = sum(1 for v in primary_votes if v["decision"] == "accept")
        reject_count = sum(1 for v in primary_votes if v["decision"] == "reject")

        # Determine primary label (most common among accepts)
        accept_labels = [v["label"] for v in primary_votes if v["decision"] == "accept"]
        if accept_labels:
            from collections import Counter
            primary_label = Counter(accept_labels).most_common(1)[0][0]
        else:
            primary_label = "reject"

        result_record = {
            **token,  # Include all original fields
            "primary_votes": primary_votes,
            "primary_summary": {
                "accept": accept_count,
                "reject": reject_count,
                "borderline": 0
            },
            "primary_label": primary_label,
            "status": "AI_PRIMARY_REVIEWED"
        }

        results.append(result_record)

    return results

def main():
    print(f"Starting primary review from batch {START_BATCH}")
    print(f"Input: {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")

    # Count total passed tokens
    print("Counting total passed tokens...")
    total_passed = 0
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            if record.get('screen_result') == 'pass':
                total_passed += 1

    print(f"Total passed tokens to process: {total_passed}")

    # Calculate batch range
    total_batches = (total_passed + BATCH_SIZE - 1) // BATCH_SIZE
    start_batch = START_BATCH
    end_batch = min(start_batch + 100, total_batches)  # Process up to 100 batches at a time

    print(f"Processing batches {start_batch} to {end_batch-1} (of {total_batches} total)")

    # Skip to start batch
    passed_count = 0
    batch_num = 0
    tokens_in_batch = []
    processed_count = 0
    appended_count = 0

    mode = 'append' if START_BATCH > 0 and OUTPUT_FILE.exists() else 'write'

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            if record.get('screen_result') != 'pass':
                continue

            # Skip until we reach start batch
            if batch_num < start_batch:
                passed_count += 1
                if passed_count % BATCH_SIZE == 0:
                    batch_num += 1
                continue

            # Add to current batch
            tokens_in_batch.append(record)
            passed_count += 1

            # Process batch when full
            if len(tokens_in_batch) >= BATCH_SIZE:
                print(f"Processing batch {batch_num}...")
                results = process_batch(tokens_in_batch)

                # Write results
                with open(OUTPUT_FILE, 'a' if mode == 'append' else 'w', encoding='utf-8') as out:
                    for result in results:
                        out.write(json.dumps(result, ensure_ascii=False) + '\n')

                processed_count += len(results)
                appended_count += len(results)
                tokens_in_batch = []
                batch_num += 1
                mode = 'append'

                # Stop if we've processed enough batches
                if batch_num >= end_batch:
                    break

    # Process remaining partial batch
    if tokens_in_batch and batch_num < end_batch:
        print(f"Processing final partial batch {batch_num}...")
        results = process_batch(tokens_in_batch)

        with open(OUTPUT_FILE, 'a' if mode == 'append' else 'w', encoding='utf-8') as out:
            for result in results:
                out.write(json.dumps(result, ensure_ascii=False) + '\n')

        processed_count += len(results)
        appended_count += len(results)

    print(f"\nProcessing complete!")
    print(f"Processed: {processed_count} tokens")
    print(f"Appended to output: {appended_count} records")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"\nTo continue with next batch, run:")
    print(f"  python process_primary_review_batch.py {end_batch}")

if __name__ == "__main__":
    main()
