#!/usr/bin/env python3
"""
Rebuttal Review Processor - Step 7
Processes challenges from Step 6 and provides three-perspective rebuttals.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

class RebuttalProcessor:
    """Process challenges and provide rebuttals from three perspectives."""

    def __init__(self, input_path: str, output_path: str):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Statistics
        self.total_records = 0
        self.challenged_records = 0
        self.upheld_challenges = 0
        self.overturned_challenges = 0
        self.partial_challenges = 0

    def review_from_perspective(self, record: Dict[str, Any], perspective: str) -> Dict[str, Any]:
        """
        Review challenges from a specific perspective.

        Perspectives:
        - reviewer-01: Recall Guardian (favors recall, tough on over_reject)
        - reviewer-02: Quality Guardian (favors quality, tough on over_accept)
        - reviewer-03: Balance Arbiter (balanced, final recommendation)
        """
        word = record.get('normalized_word', '')
        raw_token = record.get('raw_token', '')
        challenges = record.get('challenges', [])
        primary_decision = record.get('primary_summary', {})

        # If no challenges, automatic accept
        if not challenges:
            return {
                "reviewer_id": f"rebuttal-{perspective}",
                "challenge_valid": False,
                "reasoning": "No challenges to review",
                "recommended_final": "accept"
            }

        # Analyze the word and challenges
        has_special_chars = any(c in word for c in '!@#$%^&*()+=[]{}|;:",.<>?/~`')
        has_non_ascii = any(ord(c) > 127 for c in word)
        is_filename = any(ext in word.lower() for ext in ['.txt', '.pdf', '.doc', '.exe', '.jpg'])
        is_noise_pattern = any(pattern in word.lower() for pattern in ['1st', '2nd', '3rd', 'readme', 'file'])
        is_generic_common = word.lower() in ['the', 'a', 'an', 'and', 'or', 'but', 'for', 'of', 'with', 'at', 'from', 'to']
        is_very_common = word.lower() in ['language', 'point', 'going', 'places', 'mark', 'de', 'la']

        challenge_types = [c.get('suggested_action', 'reject') for c in challenges]
        challenge_reasons = [c.get('reason', '') for c in challenges]

        # Perspective-specific logic
        if perspective == "reviewer-01":
            # Recall Guardian: tough on over_reject, easy on over_accept
            return self._recall_guardian_review(word, raw_token, challenges, has_special_chars,
                                               has_non_ascii, is_filename, is_noise_pattern,
                                               is_generic_common, is_very_common)

        elif perspective == "reviewer-02":
            # Quality Guardian: tough on over_accept, easy on over_reject
            return self._quality_guardian_review(word, raw_token, challenges, has_special_chars,
                                                has_non_ascii, is_filename, is_noise_pattern,
                                                is_generic_common, is_very_common)

        else:  # reviewer-03
            # Balance Arbiter: balanced view
            return self._balance_arbiter_review(word, raw_token, challenges, has_special_chars,
                                               has_non_ascii, is_filename, is_noise_pattern,
                                               is_generic_common, is_very_common)

    def _recall_guardian_review(self, word: str, raw_token: str, challenges: List[Dict],
                                has_special_chars: bool, has_non_ascii: bool, is_filename: bool,
                                is_noise_pattern: bool, is_generic_common: bool, is_very_common: bool) -> Dict[str, Any]:
        """Recall Guardian: Uphold recall, tough on over_reject challenges."""
        # Strong reject cases (even Recall Guardian agrees)
        if has_special_chars or has_non_ascii:
            return {
                "reviewer_id": "rebuttal-reviewer-01",
                "challenge_valid": True,
                "reasoning": f"Special character/non-ASCII contamination in '{word}' makes it unsuitable for SaaS titles",
                "recommended_final": "reject"
            }

        if is_filename or is_noise_pattern:
            return {
                "reviewer_id": "rebuttal-reviewer-01",
                "challenge_valid": True,
                "reasoning": f"Clear noise pattern/filename artifact '{word}' should be rejected",
                "recommended_final": "reject"
            }

        # For generic/common words, Recall Guardian is MORE lenient
        if is_generic_common or is_very_common:
            return {
                "reviewer_id": "rebuttal-reviewer-01",
                "challenge_valid": False,
                "reasoning": f"'{word}' is a valid English word. While generic, recall principle suggests keeping it for human review",
                "recommended_final": "accept"
            }

        # Check for non-English challenges
        for challenge in challenges:
            if 'non-English' in challenge.get('reason', ''):
                # If truly non-English, uphold
                if word.lower() in ['que', 'corra', 'voz', 'qué', 'clase']:
                    return {
                        "reviewer_id": "rebuttal-reviewer-01",
                        "challenge_valid": True,
                        "reasoning": f"'{word}' is non-English, uphold rejection",
                        "recommended_final": "reject"
                    }

        # Default: overturn challenges in favor of recall
        return {
            "reviewer_id": "rebuttal-reviewer-01",
            "challenge_valid": False,
            "reasoning": f"Recall priority: '{word}' has potential SaaS utility. Challenge not compelling enough to override",
            "recommended_final": "accept"
        }

    def _quality_guardian_review(self, word: str, raw_token: str, challenges: List[Dict],
                                 has_special_chars: bool, has_non_ascii: bool, is_filename: bool,
                                 is_noise_pattern: bool, is_generic_common: bool, is_very_common: bool) -> Dict[str, Any]:
        """Quality Guardian: Uphold quality, tough on over_accept challenges."""
        # Strong reject cases
        if has_special_chars or has_non_ascii:
            return {
                "reviewer_id": "rebuttal-reviewer-02",
                "challenge_valid": True,
                "reasoning": f"Quality issue: '{word}' contains special/non-ASCII characters unacceptable for SaaS titles",
                "recommended_final": "reject"
            }

        if is_filename or is_noise_pattern:
            return {
                "reviewer_id": "rebuttal-reviewer-02",
                "challenge_valid": True,
                "reasoning": f"Noise contamination: '{word}' is clearly a filename or artifact",
                "recommended_final": "reject"
            }

        # Quality Guardian is TOUGH on generic words
        if is_generic_common:
            return {
                "reviewer_id": "rebuttal-reviewer-02",
                "challenge_valid": True,
                "reasoning": f"'{word}' is too generic and lacks distinctiveness for SaaS branding",
                "recommended_final": "reject"
            }

        if is_very_common:
            return {
                "reviewer_id": "rebuttal-reviewer-02",
                "challenge_valid": True,
                "reasoning": f"'{word}' is extremely common with minimal SaaS branding value",
                "recommended_final": "borderline"
            }

        # Non-English words
        for challenge in challenges:
            if 'non-English' in challenge.get('reason', ''):
                return {
                    "reviewer_id": "rebuttal-reviewer-02",
                    "challenge_valid": True,
                    "reasoning": f"Quality standard: '{word}' is non-English and should be rejected",
                    "recommended_final": "reject"
                }

        # For other cases, quality guardian upholds quality concerns
        return {
            "reviewer_id": "rebuttal-reviewer-02",
            "challenge_valid": True,
            "reasoning": f"Quality concern: '{word}' lacks clear SaaS utility or distinctiveness",
            "recommended_final": "borderline"
        }

    def _balance_arbiter_review(self, word: str, raw_token: str, challenges: List[Dict],
                                has_special_chars: bool, has_non_ascii: bool, is_filename: bool,
                                is_noise_pattern: bool, is_generic_common: bool, is_very_common: bool) -> Dict[str, Any]:
        """Balance Arbiter: Balanced view, makes final recommendation."""
        # Clear reject cases
        if has_special_chars or has_non_ascii:
            return {
                "reviewer_id": "rebuttal-reviewer-03",
                "challenge_valid": True,
                "reasoning": f"Special characters/non-ASCII in '{word}' are unacceptable for SaaS titles",
                "recommended_final": "reject"
            }

        if is_filename or is_noise_pattern:
            return {
                "reviewer_id": "rebuttal-reviewer-03",
                "challenge_valid": True,
                "reasoning": f"Clear noise/filename pattern '{word}' should be rejected",
                "recommended_final": "reject"
            }

        # Non-English words
        for challenge in challenges:
            if 'non-English' in challenge.get('reason', ''):
                return {
                    "reviewer_id": "rebuttal-reviewer-03",
                    "challenge_valid": True,
                    "reasoning": f"'{word}' is non-English. Challenge upheld",
                    "recommended_final": "reject"
                }

        # Balance on generic/common words
        if is_generic_common:
            # Most generic words should be borderline
            return {
                "reviewer_id": "rebuttal-reviewer-03",
                "challenge_valid": True,
                "reasoning": f"'{word}' is very generic. While a valid word, borderline classification is appropriate",
                "recommended_final": "borderline"
            }

        if is_very_common:
            return {
                "reviewer_id": "rebuttal-reviewer-03",
                "challenge_valid": True,
                "reasoning": f"'{word}' is common but has some SaaS utility. Borderline allows human review",
                "recommended_final": "borderline"
            }

        # Default: favor recall when uncertain
        return {
            "reviewer_id": "rebuttal-reviewer-03",
            "challenge_valid": False,
            "reasoning": f"On balance, recall principle applies to '{word}'. Not compelling enough to reject",
            "recommended_final": "accept"
        }

    def calculate_final_decision(self, rebuttals: List[Dict[str, Any]]) -> str:
        """Calculate final decision from three reviewer perspectives."""
        if not rebuttals:
            return "accept"

        recommendations = [r.get('recommended_final', 'accept') for r in rebuttals]

        # Count votes
        accept_votes = recommendations.count('accept')
        reject_votes = recommendations.count('reject')
        borderline_votes = recommendations.count('borderline')

        # Decision logic with recall bias
        if reject_votes >= 2:
            return "reject"
        elif accept_votes >= 2:
            return "accept"
        else:
            # Mixed or tied -> borderline with recall bias
            if accept_votes >= 1:
                return "borderline"  # Keep for human review
            return "reject"

    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single record through all three reviewers."""
        # Get rebuttals from all three perspectives
        rebuttals = [
            self.review_from_perspective(record, "reviewer-01"),
            self.review_from_perspective(record, "reviewer-02"),
            self.review_from_perspective(record, "reviewer-03")
        ]

        # Calculate final decision
        final_decision = self.calculate_final_decision(rebuttals)

        # Add rebuttals and status to record
        record['rebuttals'] = rebuttals
        record['final_decision'] = final_decision
        record['status'] = 'AI_REBUTTED'

        # Update statistics
        self.total_records += 1
        if record.get('challenge_count', 0) > 0:
            self.challenged_records += 1

        return record

    def process(self):
        """Process all records from input to output."""
        print(f"Processing {self.input_path}...")

        with open(self.input_path, 'r', encoding='utf-8') as infile, \
             open(self.output_path, 'w', encoding='utf-8') as outfile:

            for line_num, line in enumerate(infile, 1):
                try:
                    record = json.loads(line.strip())
                    processed = self.process_record(record)
                    outfile.write(json.dumps(processed, ensure_ascii=False) + '\n')

                    # Progress update
                    if line_num % 10000 == 0:
                        print(f"Processed {line_num:,} records...")

                except json.JSONDecodeError as e:
                    print(f"Error parsing line {line_num}: {e}", file=sys.stderr)
                    continue
                except Exception as e:
                    print(f"Error processing line {line_num}: {e}", file=sys.stderr)
                    continue

        print(f"\nProcessing complete!")
        print(f"Total records: {self.total_records:,}")
        print(f"Challenged records: {self.challenged_records:,}")
        print(f"Output: {self.output_path}")

def main():
    """Main entry point."""
    input_path = "C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/06_challenged.jsonl"
    output_path = "C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/07_rebutted.jsonl"

    processor = RebuttalProcessor(input_path, output_path)
    processor.process()

if __name__ == "__main__":
    main()
