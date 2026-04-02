#!/usr/bin/env python3
"""
Three-step review process: Challenge Review → Rebuttal → Consensus

This script performs the adversarial review process:
1. Challenge Review: Criticizes primary review decisions
2. Rebuttal: Defends primary decisions against challenges
3. Consensus: Reconciles disagreements
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime


class ThreeStepReview:
    """Three-step adversarial review process"""

    def __init__(self, input_path: Path, output_dir: Path):
        self.input_path = input_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Judge personas
        self.challenger_judges = [
            "challenger-judge-01",
            "challenger-judge-02",
            "challenger-judge-03"
        ]

        self.rebuttal_judges = [
            "rebuttal-judge-01",
            "rebuttal-judge-02",
            "rebuttal-judge-03"
        ]

    def load_records(self) -> List[Dict[str, Any]]:
        """Load all records from input JSONL file"""
        records = []
        with open(self.input_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def save_records(self, records: List[Dict[str, Any]], output_path: Path):
        """Save records to JSONL file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(f"[OK] Saved {len(records)} records to {output_path}")

    def perform_challenge_review(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 1: Challenge Review

        The challenger looks for:
        - Overly permissive accepts
        - Missed rejections (profanity, trademarks, too generic)
        - Borderline cases that need more scrutiny
        """

        word = record['normalized_word']
        primary_decision = record['primary_summary']['accept'] >= 3

        challenge_votes = []

        for judge_id in self.challenger_judges:
            vote = {
                "judge_id": judge_id,
                "decision": None,
                "challenge_reason": [],
                "confidence": 0.0
            }

            # Challenge logic
            should_challenge = False
            challenge_reasons = []

            # If primary accepted, challenge looks for reasons to reject
            if primary_decision:
                # Check for problematic patterns
                if any(x in word.lower() for x in ['fuck', 'shit', 'damn', 'ass']):
                    should_challenge = True
                    challenge_reasons.append(f"potential profanity/offensive: {word}")

                # Check if too generic/common
                if word.lower() in ['the', 'and', 'or', 'but', 'for', 'with', 'from']:
                    should_challenge = True
                    challenge_reasons.append(f"too generic/common word: {word}")

                # Check if too long (hard to brand)
                if len(word) > 15:
                    should_challenge = True
                    challenge_reasons.append(f"too long for SaaS title: {len(word)} chars")

                # Check for numbers/special chars
                if any(c.isdigit() for c in word):
                    should_challenge = True
                    challenge_reasons.append(f"contains digits: {word}")

                # Check for all caps (likely acronym)
                if word.isupper() and len(word) > 2:
                    should_challenge = True
                    challenge_reasons.append(f"likely acronym: {word}")

                # Check for hyphens/underscores (not clean brand)
                if '-' in word or '_' in word:
                    should_challenge = True
                    challenge_reasons.append(f"contains hyphen/underscore: {word}")

                # If strong challenges found, vote to reject
                if should_challenge and len(challenge_reasons) >= 1:
                    vote['decision'] = 'reject'
                    vote['confidence'] = 0.7
                else:
                    # No strong challenge, defer to primary
                    vote['decision'] = 'defer'
                    vote['confidence'] = 0.5

            # If primary rejected, challenge looks for reasons to accept
            else:
                # Check if wrongly rejected
                # Is it actually a clean, brandable word?
                if (word.isalpha() and
                    len(word) >= 3 and
                    len(word) <= 10 and
                    word.islower() and
                    not any(x in word.lower() for x in ['fuck', 'shit', 'damn'])):

                    should_challenge = True
                    challenge_reasons.append(f"appears brandable: {word}")

                # If good candidate found, vote to accept
                if should_challenge:
                    vote['decision'] = 'accept'
                    vote['confidence'] = 0.7
                else:
                    # No strong challenge, defer to primary
                    vote['decision'] = 'defer'
                    vote['confidence'] = 0.5

            vote['challenge_reason'] = challenge_reasons
            challenge_votes.append(vote)

        # Calculate challenge summary
        accept_count = sum(1 for v in challenge_votes if v['decision'] == 'accept')
        reject_count = sum(1 for v in challenge_votes if v['decision'] == 'reject')
        defer_count = sum(1 for v in challenge_votes if v['decision'] == 'defer')

        challenge_summary = {
            "accept": accept_count,
            "reject": reject_count,
            "defer": defer_count
        }

        # Update record
        record['status'] = 'AI_CHALLENGED'
        record['challenge_votes'] = challenge_votes
        record['challenge_summary'] = challenge_summary
        record['challenge_timestamp'] = datetime.now().isoformat()

        return record

    def perform_rebuttal(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 2: Rebuttal

        The rebuttal judge defends the primary decision against challenges.
        They look for:
        - Valid reasons why challenges should be ignored
        - Strong brandability despite challenges
        - False positives in challenge logic
        """

        challenge_summary = record.get('challenge_summary', {})
        primary_decision = record['primary_summary']['accept'] >= 3

        rebuttal_votes = []

        for judge_id in self.rebuttal_judges:
            vote = {
                "judge_id": judge_id,
                "decision": None,
                "rebuttal_reason": [],
                "confidence": 0.0
            }

            word = record['normalized_word']

            # If there were challenges to an accept decision
            if primary_decision and challenge_summary.get('reject', 0) > 0:
                # Look for reasons to defend the accept
                rebuttal_reasons = []

                # Is it a real English word?
                if word.isalpha() and word.islower():
                    rebuttal_reasons.append("valid English word structure")

                # Is it reasonably short?
                if len(word) <= 12:
                    rebuttal_reasons.append("reasonable length for branding")

                # Is it distinctive?
                if len(word) >= 4:
                    rebuttal_reasons.append("sufficiently distinctive")

                # If good rebuttal reasons, stand by primary accept
                if len(rebuttal_reasons) >= 2:
                    vote['decision'] = 'accept'
                    vote['confidence'] = 0.75
                else:
                    # Weak rebuttal, acknowledge challenge
                    vote['decision'] = 'borderline'
                    vote['confidence'] = 0.5

                vote['rebuttal_reason'] = rebuttal_reasons

            # If there were challenges to a reject decision
            elif not primary_decision and challenge_summary.get('accept', 0) > 0:
                # Look for reasons to defend the reject
                rebuttal_reasons = []

                # Was it rejected for good reason?
                if any(x in word.lower() for x in ['fuck', 'shit', 'damn']):
                    rebuttal_reasons.append("profanity rejection stands")

                if word.lower() in ['the', 'and', 'or', 'but']:
                    rebuttal_reasons.append("too generic rejection stands")

                # If good rebuttal reasons, stand by primary reject
                if len(rebuttal_reasons) >= 1:
                    vote['decision'] = 'reject'
                    vote['confidence'] = 0.8
                else:
                    # Weak rebuttal, acknowledge challenge
                    vote['decision'] = 'borderline'
                    vote['confidence'] = 0.5

                vote['rebuttal_reason'] = rebuttal_reasons

            # No significant challenges, defer to primary
            else:
                vote['decision'] = 'defer'
                vote['confidence'] = 0.6
                vote['rebuttal_reason'] = ["no significant challenges to rebut"]

            rebuttal_votes.append(vote)

        # Calculate rebuttal summary
        accept_count = sum(1 for v in rebuttal_votes if v['decision'] == 'accept')
        reject_count = sum(1 for v in rebuttal_votes if v['decision'] == 'reject')
        defer_count = sum(1 for v in rebuttal_votes if v['decision'] == 'defer')
        borderline_count = sum(1 for v in rebuttal_votes if v['decision'] == 'borderline')

        rebuttal_summary = {
            "accept": accept_count,
            "reject": reject_count,
            "defer": defer_count,
            "borderline": borderline_count
        }

        # Update record
        record['status'] = 'AI_REBUTTED'
        record['rebuttal_votes'] = rebuttal_votes
        record['rebuttal_summary'] = rebuttal_summary
        record['rebuttal_timestamp'] = datetime.now().isoformat()

        return record

    def perform_consensus(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 3: Consensus

        Reconciles the primary decision, challenges, and rebuttals into a final decision.
        """

        primary_accepts = record['primary_summary']['accept']
        primary_decision = primary_accepts >= 3

        challenge_summary = record.get('challenge_summary', {})
        rebuttal_summary = record.get('rebuttal_summary', {})

        # Consensus logic
        final_decision = None
        final_label = None
        consensus_reasons = []

        # If all three stages agree on accept
        if (primary_decision and
            challenge_summary.get('accept', 0) + challenge_summary.get('defer', 0) >= 2 and
            rebuttal_summary.get('accept', 0) + rebuttal_summary.get('defer', 0) >= 2):
            final_decision = 'accept'
            final_label = self._determine_label(record)
            consensus_reasons.append("strong consensus for accept")

        # If all three stages agree on reject
        elif (not primary_decision and
              challenge_summary.get('reject', 0) + challenge_summary.get('defer', 0) >= 2 and
              rebuttal_summary.get('reject', 0) + rebuttal_summary.get('defer', 0) >= 2):
            final_decision = 'reject'
            final_label = self._determine_reject_label(record)
            consensus_reasons.append("strong consensus for reject")

        # If challenges succeeded (primary accept, but challenges rejected)
        elif (primary_decision and
              challenge_summary.get('reject', 0) >= 2 and
              rebuttal_summary.get('accept', 0) < 2):
            final_decision = 'reject'
            final_label = self._determine_reject_label(record)
            consensus_reasons.append("challenges upheld, overturned to reject")

        # If challenges succeeded (primary reject, but challenges accepted)
        elif (not primary_decision and
              challenge_summary.get('accept', 0) >= 2 and
              rebuttal_summary.get('reject', 0) < 2):
            final_decision = 'accept'
            final_label = self._determine_label(record)
            consensus_reasons.append("challenges upheld, overturned to accept")

        # Borderline/conflict - be conservative
        else:
            # When in doubt, accept for SaaS title potential (recall-first)
            word = record['normalized_word']
            if (word.isalpha() and
                len(word) >= 3 and
                len(word) <= 15 and
                not any(x in word.lower() for x in ['fuck', 'shit', 'damn'])):
                final_decision = 'accept'
                final_label = 'ambiguous'
                consensus_reasons.append("borderline case, defaulting to accept (recall-first)")
            else:
                final_decision = 'reject'
                final_label = self._determine_reject_label(record)
                consensus_reasons.append("borderline case, defaulting to reject")

        # Calculate confidence based on agreement
        agreement_score = 0
        if primary_decision == (final_decision == 'accept'):
            agreement_score += 1
        if (challenge_summary.get('accept' if final_decision == 'accept' else 'reject', 0) +
            challenge_summary.get('defer', 0)) >= 2:
            agreement_score += 1
        if (rebuttal_summary.get('accept' if final_decision == 'accept' else 'reject', 0) +
            rebuttal_summary.get('defer', 0)) >= 2:
            agreement_score += 1

        confidence = 0.5 + (agreement_score * 0.15)

        # Update record
        record['status'] = 'AI_CONSENSUS'
        record['consensus_decision'] = final_decision
        record['consensus_label'] = final_label
        record['consensus_confidence'] = round(confidence, 2)
        record['consensus_reasons'] = consensus_reasons
        record['consensus_timestamp'] = datetime.now().isoformat()

        return record

    def _determine_label(self, record: Dict[str, Any]) -> str:
        """Determine the label for accepted words"""
        word = record['normalized_word'].lower()

        # Check primary votes for hints
        primary_votes = record.get('primary_votes', [])
        brandable_count = sum(1 for v in primary_votes if v.get('label') == 'brandable')
        functional_count = sum(1 for v in primary_votes if v.get('label') == 'functional')

        # Heuristic classification
        if (word.endswith(('ly', 'ive', 'able', 'ible', 'ful', 'ous', 'ent', 'ant')) or
            brandable_count >= 2):
            return 'brandable'

        if (word.endswith(('er', 'or', 'tion', 'sion', 'ment', 'ness', 'ity', 'ance', 'ence')) or
            functional_count >= 2):
            return 'functional'

        return 'ambiguous'

    def _determine_reject_label(self, record: Dict[str, Any]) -> str:
        """Determine the reason for rejection"""
        word = record['normalized_word'].lower()

        if any(x in word for x in ['fuck', 'shit', 'damn', 'ass']):
            return 'profanity'

        if len(word) > 15:
            return 'too_long'

        if len(word) < 3:
            return 'too_short'

        if any(c.isdigit() for c in word):
            return 'contains_digits'

        if '-' in word or '_' in word:
            return 'contains_special_chars'

        if word.lower() in ['the', 'and', 'or', 'but', 'for', 'with', 'from']:
            return 'too_generic'

        return 'not_saas_appropriate'

    def run(self):
        """Run the complete three-step review process"""
        print("Loading records...")
        records = self.load_records()
        print(f"[OK] Loaded {len(records)} records")

        print("\n" + "="*60)
        print("STEP 1: CHALLENGE REVIEW")
        print("="*60)

        challenged_records = []
        for i, record in enumerate(records, 1):
            if i % 500 == 0:
                print(f"  Processing record {i}/{len(records)}...")
            challenged = self.perform_challenge_review(record)
            challenged_records.append(challenged)

        challenged_path = self.output_dir / "06_challenged.jsonl"
        self.save_records(challenged_records, challenged_path)

        print("\n" + "="*60)
        print("STEP 2: REBUTTAL")
        print("="*60)

        rebutted_records = []
        for i, record in enumerate(challenged_records, 1):
            if i % 500 == 0:
                print(f"  Processing record {i}/{len(records)}...")
            rebutted = self.perform_rebuttal(record)
            rebutted_records.append(rebutted)

        rebutted_path = self.output_dir / "07_rebutted.jsonl"
        self.save_records(rebutted_records, rebutted_path)

        print("\n" + "="*60)
        print("STEP 3: CONSENSUS")
        print("="*60)

        consensus_records = []
        for i, record in enumerate(rebutted_records, 1):
            if i % 500 == 0:
                print(f"  Processing record {i}/{len(records)}...")
            consensus = self.perform_consensus(record)
            consensus_records.append(consensus)

        consensus_path = self.output_dir / "08_consensus.jsonl"
        self.save_records(consensus_records, consensus_path)

        # Generate summary
        self.generate_summary(consensus_records)

        print("\n" + "="*60)
        print("[OK] THREE-STEP REVIEW COMPLETE")
        print("="*60)

    def generate_summary(self, records: List[Dict[str, Any]]):
        """Generate summary statistics"""
        accept_count = sum(1 for r in records if r['consensus_decision'] == 'accept')
        reject_count = sum(1 for r in records if r['consensus_decision'] == 'reject')

        brandable_count = sum(1 for r in records if r.get('consensus_label') == 'brandable')
        functional_count = sum(1 for r in records if r.get('consensus_label') == 'functional')
        ambiguous_count = sum(1 for r in records if r.get('consensus_label') == 'ambiguous')

        print("\n" + "="*60)
        print("CONSENSUS SUMMARY")
        print("="*60)
        print(f"Total records: {len(records)}")
        print(f"  Accepted: {accept_count} ({100*accept_count/len(records):.1f}%)")
        print(f"  Rejected: {reject_count} ({100*reject_count/len(records):.1f}%)")
        print(f"\nAccepted by label:")
        print(f"  Brandable: {brandable_count}")
        print(f"  Functional: {functional_count}")
        print(f"  Ambiguous: {ambiguous_count}")

        # Save summary
        summary = {
            "total_records": len(records),
            "accept_count": accept_count,
            "reject_count": reject_count,
            "accept_rate": round(100*accept_count/len(records), 2),
            "brandable_count": brandable_count,
            "functional_count": functional_count,
            "ambiguous_count": ambiguous_count,
            "timestamp": datetime.now().isoformat()
        }

        summary_path = self.output_dir / "08_consensus_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Summary saved to {summary_path}")


if __name__ == "__main__":
    input_path = Path("C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate/05_primary_reviewed.jsonl")
    output_dir = Path("C:/Users/h0912/claude_project/SaaS_Word_Extractor/output/intermediate")

    reviewer = ThreeStepReview(input_path, output_dir)
    reviewer.run()
