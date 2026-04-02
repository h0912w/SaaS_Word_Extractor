#!/usr/bin/env python3
"""
Primary Review for SaaS Word Candidates

This script performs AI-based primary review of screened tokens,
evaluating each word's suitability as a SaaS product name component.

Input: output/intermediate/04_screened_tokens.jsonl
Output: output/intermediate/05_primary_reviewed.jsonl
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def load_screened_tokens(input_path: Path) -> List[Dict[str, Any]]:
    """Load screened tokens, filtering for pass results only."""
    records = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                if record.get('screen_result') == 'pass':
                    records.append(record)
    return records


def create_judgment_template(word: str, judge_id: str) -> Dict[str, Any]:
    """Create a template for a single judge's decision."""
    return {
        'judge_id': judge_id,
        'decision': None,  # Will be filled: 'accept' or 'reject'
        'label': None,     # Will be filled: 'functional', 'brandable', 'ambiguous'
        'confidence': None,  # Will be filled: 0.0-1.0
        'why': []          # Will be filled: list of reasons
    }


def generate_prompts_for_batch(records: List[Dict[str, Any]]) -> str:
    """Generate a prompt for AI to judge a batch of words."""
    prompt = "You are a SaaS product naming expert. Evaluate each word's potential as a SaaS product name component.\n\n"
    prompt += "## Accept Criteria (liberal application)\n"
    prompt += "- Real English words (including rare/technical terms)\n"
    prompt += "- Functional: merge, sync, deploy, track, build, parse, render, queue, route, stream\n"
    prompt += "- Brandable: forge, pulse, nexus, apex, orbit, nova, beacon, vault, spark, craft\n"
    prompt += "- Adjectives/Adverbs: rapid, clear, smart, deep, bright, swift\n"
    prompt += "- Abstract nouns: flow, core, stack, mesh, grid, bridge, hub, link, edge, node\n\n"
    prompt += "## Reject Criteria (clear cases only)\n"
    prompt += "- Pure symbols: !!! @#$ --- ===\n"
    prompt += "- URL/path fragments: http www .exe /usr\n"
    prompt += "- Code tokens: __init__ 0x1A2B\n"
    prompt += "- Non-English gibberish\n"
    prompt += "- Repeated characters: aaaa !!!!\n\n"
    prompt += "## Labels (for accept decisions)\n"
    prompt += "- functional: directly describes function (sync, merge, deploy)\n"
    prompt += "- brandable: suitable for product/brand names (forge, pulse, nexus)\n"
    prompt += "- ambiguous: could be either\n\n"
    prompt += "## Words to Evaluate\n\n"

    for i, record in enumerate(records, 1):
        word = record.get('normalized_word', '')
        prompt += f"{i}. {word}\n"

    prompt += "\n\nFor each word, provide 5 independent judgments (judge-01 through judge-05):\n"
    prompt += "- judge-01: recall-focused (most liberal)\n"
    prompt += "- judge-02: brand value focused\n"
    prompt += "- judge-03: technical/functional value focused\n"
    prompt += "- judge-04: real English word verification\n"
    prompt += "- judge-05: balanced quality review\n\n"
    prompt += "Format your response as JSON for each word:\n"
    prompt += "{\n"
    prompt += "  \"word\": \"...\",\n"
    prompt += "  \"primary_votes\": [\n"
    prompt += "    {\"judge_id\": \"saas-title-judge-01\", \"decision\": \"accept\", \"label\": \"functional\", \"confidence\": 0.9, \"why\": [\"...\"]},\n"
    prompt += "    ...\n"
    prompt += "  ],\n"
    prompt += "  \"primary_summary\": {\"accept\": N, \"reject\": M, \"borderline\": L}\n"
    prompt += "}\n\n"
    prompt += "Process all words. Return as JSON array."

    return prompt


def save_intermediate_prompt(prompt: str, output_path: Path):
    """Save the prompt for human review/AI processing."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(prompt)


def main():
    """Main execution function."""
    project_root = Path(__file__).parent.parent
    input_file = project_root / 'output' / 'intermediate' / '04_screened_tokens.jsonl'
    output_file = project_root / 'output' / 'intermediate' / '05_primary_reviewed.jsonl'
    prompt_file = project_root / 'output' / 'intermediate' / 'primary_review_prompt.txt'

    print("Loading screened tokens...")
    records = load_screened_tokens(input_file)
    print(f"Loaded {len(records)} pass records")

    # Generate a prompt for batch processing
    # Due to token limits, we'll process in smaller batches
    batch_size = 50
    batches = [records[i:i+batch_size] for i in range(0, len(records), batch_size)]

    print(f"Created {len(batches)} batches of ~{batch_size} words each")
    print(f"\nIMPORTANT: This script prepares the data for AI judgment.")
    print(f"The actual AI judgment must be performed by Claude Code session.")
    print(f"\nPrompt file will be saved to: {prompt_file}")

    # Save first batch prompt as example
    if batches:
        first_prompt = generate_prompts_for_batch(batches[0])
        save_intermediate_prompt(first_prompt, prompt_file)
        print(f"\nFirst batch prompt saved. This prompt contains {len(batches[0])} words.")
        print(f"Please process this prompt through Claude Code AI session.")

    print(f"\nTotal words requiring primary review: {len(records)}")
    print(f"Estimated total judgments needed: {len(records) * 5}")


if __name__ == '__main__':
    main()
