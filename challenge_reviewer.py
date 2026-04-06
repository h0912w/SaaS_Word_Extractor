#!/usr/bin/env python3
"""
Challenge Reviewer - Analyzes primary review decisions and identifies over-accepts
"""

import json
import re
from typing import Dict, List, Any
from collections import defaultdict

class ChallengeReviewer:
    """Reviews primary judgments and identifies potentially over-accepted tokens"""

    # Patterns that suggest over-acceptance
    OVER_ACCEPT_PATTERNS = {
        'non_english': [
            # Spanish/French/Portuguese articles and prepositions
            r'^el$', r'^la$', r'^los$', r'^las$', r'^un$', r'^una$', r'^le$', r'^les$',
            r'^de$', r'^del$', r'^en$', r'^por$', r'^para$', r'^con$', r'^sin$',
            r'^que$', r'^qué$', r'^qui$', r'^quien$', r'^quién$', r'^donde$', r'^dónde$',
            r'^y$', r'^o$', r'^pero$', r'^porque$', r'^porqué$',
            r'^esta$', r'este$', r'^esto$', r'^ese$', r'^esa$',
            r'^mi$', r'^mis$', r'^tu$', r'^tus$', r'^su$', r'^sus$',
            # German articles
            r'^der$', r'^die$', r'^das$', r'^ein$', r'^eine$',
            r'^von$', r'^zu$', r'^auf$', r'^mit$', r'^für$',
            # Italian
            r'^il$', r'^lo$', r'^la$', r'^gli$', r'^i$', r'^le$',
            r'^di$', r'^a$', r'^da$', r'^in$', r'^su$', r'^per$',
            # Common non-English words
            r'^que$', r'^corra$', r'^voz$', r'^clase$', r'^qué$',
        ],
        'too_generic': [
            # Extremely common words with no branding potential
            r'^the$', r'^a$', r'^an$', r'^and$', r'^or$', r'^but$',
            r'^in$', r'^on$', r'^at$', r'^to$', r'^for$', r'^of$', r'^with$',
            r'^is$', r'^are$', r'^was$', r'^were$', r'^be$', r'^been$',
            r'^have$', r'^has$', r'^had$', r'^do$', r'^does$', r'^did$',
            r'^this$', r'^that$', r'^these$', r'^those$',
            r'^i$', r'^you$', r'^he$', r'^she$', r'^it$', r'^we$', r'^they$',
            r'^my$', r'^your$', r'^his$', r'^her$', r'^its$', r'^our$', r'^their$',
            # Very generic nouns/verbs
            r'^go$', r'^going$', r'^went$', r'^gone$',
            r'^come$', r'^came$', r'^get$', r'^got$', r'^make$', r'^made$',
            r'^take$', r'^took$', r'^see$', r'^saw$', r'^seen$',
            r'^know$', r'^knew$', r'^think$', r'^thought$',
            r'^want$', r'^wanted$', r'^need$', r'^needed$',
            r'^like$', r'^liked$', r'^use$', r'^used$',
            r'^find$', r'^found$', r'^give$', r'^gave$', r'^given$',
            r'^tell$', r'^told$', r'^ask$', r'^asked$', r'^work$', r'^worked$',
            r'^seem$', r'^seemed$', r'^feel$', r'^felt$', r'^try$', r'^tried$',
            r'^leave$', r'^left$', r'^call$', r'^called$',
            # Generic pronouns/determiners
            r'^some$', r'^any$', r'^no$', r'^not$', r'^all$', r'^every$',
            r'^very$', r'^more$', r'^most$', r'^less$', r'^least$',
            r'^other$', r'^another$', r'^same$', r'^such$',
            r'^what$', r'^which$', r'^who$', r'^when$', r'^where$', r'^why$', r'^how$',
            r'^can$', r'^could$', r'^will$', r'^would$', r'^shall$', r'^should$',
            r'^may$', r'^might$', r'^must$',
            # Generic numbers/time
            r'^one$', r'^two$', r'^three$', r'^four$', r'^five$',
            r'^six$', r'^seven$', r'^eight$', r'^nine$', r'^ten$',
            r'^first$', r'^second$', r'^third$', r'^last$',
            r'^now$', r'^then$', r'^here$', r'^there$',
            # Generic places/directions
            r'^place$', r'^places$', r'^point$', r'^points$',
            r'^way$', r'^ways$', r'^side$', r'^sides$',
        ],
        'technical_jargon': [
            # Overly technical with limited SaaS branding potential
            r'^pthread$', r'^mutex$', r'^semaphore$',
            r'^endianness$', r'^bytecode$', r'^opcode$',
            r'^syscall$', r'^kernel$', r'^syscall$',
            r'^endi$', r'^oem$', r'^oem$',
        ],
        'noise_patterns': [
            # Filename-like patterns
            r'.*\.txt$', r'.*\.log$', r'.*\.csv$', r'.*\.json$',
            r'.*\.md$', r'.*\.html$', r'.*\.css$', r'.*\.js$',
            # Version patterns
            r'^v\d+$', r'^\d+\.\d+$', r'^\d+\.\d+\.\d+$',
            # Alphanumeric codes
            r'^[a-z]\d+[a-z]?$', r'^\d+[a-z]+\d*$',
        ],
        'special_chars': [
            # Words with special characters that shouldn't have passed
            r'.*[!@#$%^&*()+=\[\]{};:"\'<>,?/\\|].*',
            # Non-ASCII characters
            r'.*[ŋščžžýáéíóúàèìòùäëïöü].*',
        ]
    }

    def __init__(self):
        self.challenge_stats = defaultdict(int)
        self.challenge_reasons = defaultdict(list)

    def matches_pattern(self, word: str, category: str) -> bool:
        """Check if word matches any pattern in category"""
        patterns = self.OVER_ACCEPT_PATTERNS.get(category, [])
        word_lower = word.lower()

        for pattern in patterns:
            if re.match(pattern, word_lower, re.IGNORECASE):
                return True
        return False

    def should_challenge(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Determine if a record should be challenged and return challenge details
        """
        challenges = []
        word = record.get('normalized_word', '')
        raw_token = record.get('raw_token', '')
        primary_summary = record.get('primary_summary', {})
        accept_count = primary_summary.get('accept', 0)

        # Only challenge if accepted by majority (3+ votes)
        if accept_count < 3:
            return challenges

        # Check each challenge category
        if self.matches_pattern(word, 'non_english'):
            challenges.append({
                "reviewer_id": "challenge-reviewer-01",
                "challenged": True,
                "reason": f"Non-English word '{word}' that should have been rejected",
                "suggested_action": "reject"
            })
            self.challenge_stats['non_english'] += 1

        if self.matches_pattern(word, 'too_generic'):
            # Skip if the word is in raw_token without special chars
            # (might be a legitimate extraction)
            if not any(c in raw_token for c in '!@#$%^&*()[]{}<>?/\\|'):
                challenges.append({
                    "reviewer_id": "challenge-reviewer-02",
                    "challenged": True,
                    "reason": f"Generic common word '{word}' with minimal SaaS branding potential",
                    "suggested_action": "reject"
                })
                self.challenge_stats['too_generic'] += 1

        if self.matches_pattern(word, 'technical_jargon'):
            challenges.append({
                "reviewer_id": "challenge-reviewer-03",
                "challenged": True,
                "reason": f"Technical jargon '{word}' with limited SaaS applicability",
                "suggested_action": "reject"
            })
            self.challenge_stats['technical_jargon'] += 1

        if self.matches_pattern(word, 'noise_patterns'):
            challenges.append({
                "reviewer_id": "challenge-reviewer-04",
                "challenged": True,
                "reason": f"Noise pattern '{word}' (filename/version/code)",
                "suggested_action": "reject"
            })
            self.challenge_stats['noise_patterns'] += 1

        if self.matches_pattern(word, 'special_chars'):
            challenges.append({
                "reviewer_id": "challenge-reviewer-05",
                "challenged": True,
                "reason": f"Special characters or non-ASCII in '{word}'",
                "suggested_action": "reject"
            })
            self.challenge_stats['special_chars'] += 1

        return challenges

    def process_file(self, input_path: str, output_path: str):
        """Process primary review file and generate challenges"""
        processed = 0
        challenged = 0
        no_challenge = 0

        print(f"Processing {input_path}...")

        with open(input_path, 'r', encoding='utf-8') as infile, \
             open(output_path, 'w', encoding='utf-8') as outfile:

            for line_num, line in enumerate(infile, 1):
                try:
                    record = json.loads(line.strip())
                    processed += 1

                    # Get challenges for this record
                    challenges = self.should_challenge(record)

                    # Add challenge fields to record
                    record['challenges'] = challenges
                    record['challenge_count'] = len(challenges)
                    record['status'] = 'AI_CHALLENGED'

                    # Write to output
                    outfile.write(json.dumps(record, ensure_ascii=False) + '\n')

                    if challenges:
                        challenged += 1
                        if processed % 1000 == 0:
                            print(f"  Processed {processed:,}, Challenged {challenged:,}")
                    else:
                        no_challenge += 1

                    # Progress update
                    if processed % 5000 == 0:
                        print(f"  Progress: {processed:,} processed, {challenged:,} challenged")

                except json.JSONDecodeError as e:
                    print(f"  Error parsing line {line_num}: {e}")
                    continue
                except Exception as e:
                    print(f"  Error processing line {line_num}: {e}")
                    continue

        # Print summary
        print(f"\n{'='*60}")
        print(f"Challenge Review Summary")
        print(f"{'='*60}")
        print(f"Total processed:     {processed:,}")
        print(f"Challenged:          {challenged:,} ({100*challenged/processed:.1f}%)")
        print(f"No challenge:        {no_challenge:,} ({100*no_challenge/processed:.1f}%)")
        print(f"\nChallenge breakdown:")
        for category, count in sorted(self.challenge_stats.items()):
            print(f"  {category:20s}: {count:6,}")
        print(f"{'='*60}")
        print(f"\nOutput written to: {output_path}")

def main():
    """Main execution"""
    import os

    base_dir = "C:/Users/h0912/claude_project/SaaS_Word_Extractor"
    input_file = os.path.join(base_dir, "output/intermediate/05_primary_reviewed.jsonl")
    output_file = os.path.join(base_dir, "output/intermediate/06_challenged.jsonl")

    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        return 1

    reviewer = ChallengeReviewer()
    reviewer.process_file(input_file, output_file)

    return 0

if __name__ == "__main__":
    exit(main())
