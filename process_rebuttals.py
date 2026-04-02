#!/usr/bin/env python3
"""
Process rebuttals for challenged SaaS word extractions.

This script reads 06_challenged.jsonl and creates 07_rebutted.jsonl
by evaluating each challenge from multiple reviewer perspectives.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class RebuttalProcessor:
    """Process rebuttals for challenged decisions."""

    def __init__(self):
        self.reviewer_profiles = {
            "rebuttal-reviewer-01": {
                "name": "Recall Guardian",
                "stance": "Supports over_reject challenges, strict on over_accept challenges",
                "bias": "favor_accept"
            },
            "rebuttal-reviewer-02": {
                "name": "Quality Guardian",
                "stance": "Supports over_accept challenges, strict on over_reject challenges",
                "bias": "favor_reject"
            },
            "rebuttal-reviewer-03": {
                "name": "Balance Arbiter",
                "stance": "Balanced evaluation with final recommendation",
                "bias": "balanced"
            }
        }

    def evaluate_challenge_validity(
        self,
        word: str,
        challenge: Dict[str, Any],
        reviewer_bias: str
    ) -> tuple[bool, str, str]:
        """
        Evaluate if a challenge is valid from a reviewer's perspective.

        Returns:
            (challenge_valid, reasoning, recommended_final)
        """
        challenge_type = challenge.get("challenge_type", "unknown")
        challenger_reasoning = challenge.get("reasoning", "")
        original_decision = challenge.get("original_decision", "unknown")

        # Key factors from the record
        is_english = challenge.get("is_english", True)
        has_meaning = challenge.get("has_meaning", True)
        semantic_score = challenge.get("semantic_score", 0.0)
        word_type = challenge.get("word_type", "unknown")
        tags = challenge.get("tags", [])

        # Reviewer-01: Recall Guardian (favor accept)
        if reviewer_bias == "favor_accept":
            if challenge_type == "over_reject":
                # Strongly support challenges to rejections
                if not is_english or not has_meaning:
                    # But still validate basic requirements
                    return True, "Challenge valid - basic criteria not met", "reject"
                elif semantic_score < 0.3 and word_type == "noise":
                    return True, "Challenge valid - low semantic score, likely noise", "reject"
                else:
                    return True, "Challenge valid - recall priority applies", "accept"
            else:  # over_accept
                # Strict on challenges to accepts
                if semantic_score >= 0.5 or "brandable" in tags or "functional" in tags:
                    return False, f"Challenge rejected - semantic score {semantic_score} indicates SaaS relevance", original_decision
                else:
                    # Consider borderline cases
                    return True, "Challenge accepted - marginal case warrants review", "accept_with_risk"

        # Reviewer-02: Quality Guardian (favor reject)
        elif reviewer_bias == "favor_reject":
            if challenge_type == "over_accept":
                # Support challenges to accepts
                if semantic_score < 0.4 or word_type in ["noise", "too_generic"]:
                    return True, "Challenge valid - low quality SaaS candidate", "reject"
                elif word_type == "ambiguous" and semantic_score < 0.5:
                    return True, "Challenge valid - too ambiguous for clear SaaS use", "accept_with_risk"
                else:
                    return False, "Challenge rejected - word has clear SaaS utility", original_decision
            else:  # over_reject
                # Strict on challenges to rejections
                if not is_english:
                    return False, "Challenge rejected - non-English words should be rejected", "reject"
                elif not has_meaning:
                    return False, "Challenge rejected - meaningless tokens should be rejected", "reject"
                else:
                    # More lenient for valid English words
                    return True, "Challenge valid - English word with potential deserves consideration", "accept"

        # Reviewer-03: Balance Arbiter
        else:
            # Balanced evaluation considering all factors
            valid_votes = 0
            total_factors = 0

            # Factor 1: Basic language validity
            total_factors += 1
            if is_english:
                valid_votes += 1

            # Factor 2: Semantic coherence
            total_factors += 1
            if has_meaning:
                valid_votes += 1

            # Factor 3: Semantic score threshold
            total_factors += 1
            if semantic_score >= 0.4:
                valid_votes += 1

            # Factor 4: Word type appropriateness
            total_factors += 1
            if word_type not in ["noise", "too_generic", "unknown"]:
                valid_votes += 1

            # Factor 5: Challenge quality
            total_factors += 1
            if len(challenger_reasoning) > 50:  # Substantive reasoning
                valid_votes += 1

            # Make balanced decision
            strength_ratio = valid_votes / total_factors

            if challenge_type == "over_reject":
                # For rejection challenges, be more permissive (recall bias)
                if strength_ratio >= 0.4:
                    return True, f"On balance, {valid_votes}/{total_factors} factors support reconsideration", "accept"
                else:
                    return False, f"Challenge not compelling - only {valid_votes}/{total_factors} factors support", "reject"
            else:  # over_accept
                # For accept challenges, be more rigorous (quality focus)
                if strength_ratio < 0.5 or semantic_score < 0.35:
                    return True, f"Challenge has merit - {valid_votes}/{total_factors} factors indicate weakness", "reject"
                else:
                    return False, f"Challenge lacks merit - {valid_votes}/{total_factors} factors support original decision", original_decision

    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single record and add rebuttals."""
        word = record.get("word", "")
        challenges = record.get("challenges", [])

        rebuttals = []

        if challenges:
            for i, challenge in enumerate(challenges):
                # Generate rebuttal from each reviewer perspective
                for reviewer_id in ["rebuttal-reviewer-01", "rebuttal-reviewer-02", "rebuttal-reviewer-03"]:
                    bias = self.reviewer_profiles[reviewer_id]["bias"]

                    # Add word context to challenge for evaluation
                    enriched_challenge = {
                        **challenge,
                        "is_english": record.get("is_english", True),
                        "has_meaning": record.get("has_meaning", True),
                        "semantic_score": record.get("semantic_score", 0.0),
                        "word_type": record.get("word_type", "unknown"),
                        "tags": record.get("tags", [])
                    }

                    valid, reasoning, recommended = self.evaluate_challenge_validity(
                        word, enriched_challenge, bias
                    )

                    rebuttal = {
                        "reviewer_id": reviewer_id,
                        "reviewer_name": self.reviewer_profiles[reviewer_id]["name"],
                        "challenge_index": i,
                        "challenge_valid": valid,
                        "reasoning": reasoning,
                        "recommended_final": recommended
                    }
                    rebuttals.append(rebuttal)
        else:
            # No challenges - empty rebuttals array
            pass

        # Create output record
        output_record = {
            **record,
            "rebuttals": rebuttals,
            "status": "AI_REBUTTED"
        }

        return output_record

    def process_file(
        self,
        input_path: Path,
        output_path: Path
    ) -> tuple[int, int]:
        """
        Process the entire challenged file.

        Returns:
            (total_records, records_with_challenges)
        """
        total_records = 0
        records_with_challenges = 0

        with open(input_path, 'r', encoding='utf-8') as infile, \
             open(output_path, 'w', encoding='utf-8') as outfile:

            for line in infile:
                total_records += 1

                try:
                    record = json.loads(line.strip())
                except json.JSONDecodeError as e:
                    print(f"Error parsing line {total_records}: {e}", file=sys.stderr)
                    continue

                # Process record
                processed = self.process_record(record)

                if record.get("challenges"):
                    records_with_challenges += 1

                # Write output
                outfile.write(json.dumps(processed, ensure_ascii=False) + '\n')

                if total_records % 100 == 0:
                    print(f"Processed {total_records} records...")

        return total_records, records_with_challenges


def main():
    """Main entry point."""
    input_path = Path(r"C:\Users\h0912\claude_project\SaaS_Word_Extractor\output\intermediate\06_challenged.jsonl")
    output_path = Path(r"C:\Users\h0912\claude_project\SaaS_Word_Extractor\output\intermediate\07_rebutted.jsonl")

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print("Processing rebuttals...")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print()

    processor = RebuttalProcessor()
    total, with_challenges = processor.process_file(input_path, output_path)

    print()
    print(f"Complete!")
    print(f"  Total records processed: {total}")
    print(f"  Records with challenges: {with_challenges}")
    print(f"  Rebuttals generated: {with_challenges * 3}")  # 3 reviewers per challenge


if __name__ == "__main__":
    main()
