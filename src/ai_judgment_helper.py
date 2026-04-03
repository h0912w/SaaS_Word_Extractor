#!/usr/bin/env python3
"""
AI Judgment Helper
Provides functions for integrating AI judgment into the pipeline
"""

import json
from typing import Dict, List, Any
from pathlib import Path


class AIJudgmentHelper:
    """Helper for AI-based judgment of SaaS word suitability"""

    # Rejection criteria - must be explicitly rejected
    REJECT_GENERIC_WORDS = {
        # Pronouns
        'me', 'you', 'he', 'she', 'it', 'we', 'they', 'myself', 'yourself', 'himself',
        'herself', 'itself', 'ourselves', 'themselves', 'this', 'that', 'these', 'those',
        'who', 'what', 'where', 'when', 'why', 'how', 'which', 'whose', 'whom',
        # Articles
        'the', 'a', 'an',
        # Prepositions
        'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from', 'up', 'about',
        'into', 'over', 'after', 'under', 'out', 'through', 'during', 'before',
        'between', 'against', 'without', 'within', 'among', 'around', 'behind',
        'beyond', 'plus', 'except', 'but', 'per', 'via',
        # Conjunctions
        'and', 'but', 'or', 'nor', 'yet', 'so', 'although', 'because', 'since',
        'unless', 'until', 'while', 'where', 'whereas', 'whether', 'if', 'then', 'else',
        'therefore', 'thus', 'hence', 'consequently', 'accordingly', 'meanwhile',
        'besides', 'furthermore', 'moreover', 'however', 'nevertheless', 'nonetheless',
        'instead', 'likewise', 'similarly', 'otherwise',
        # Auxiliary verbs
        'do', 'does', 'did', 'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'having', 'can', 'could', 'will', 'would', 'shall',
        'should', 'may', 'might', 'must',
        # Common modal verbs
        'get', 'got', 'need', 'let', 'make', 'take', 'give', 'come', 'go', 'see',
        'say', 'think', 'know', 'want', 'like', 'look', 'use', 'find', 'tell', 'ask',
        'work', 'seem', 'feel', 'try', 'leave', 'call', 'keep', 'put', 'mean', 'hold',
        'bring', 'begin', 'start', 'show', 'hear', 'play', 'run', 'move', 'live',
        'believe', 'happen', 'write', 'sit', 'stand', 'lose', 'pay', 'meet', 'include',
        'continue', 'set', 'change', 'lead', 'understand', 'watch', 'follow', 'stop',
        'create', 'speak', 'read', 'allow', 'add', 'spend', 'grow', 'open', 'walk',
        'win', 'offer', 'remember', 'love', 'consider', 'appear', 'buy', 'wait', 'serve',
        'die', 'send', 'expect', 'stay', 'fall', 'cut', 'reach', 'kill', 'remain',
        'suggest', 'raise', 'pass', 'sell', 'require', 'report', 'decide', 'pull',
        'break', 'thank', 'receive', 'join', 'cause', 'represent', 'apply', 'learn',
        'increase', 'occur', 'accept', 'drive', 'deal', 'achieve', 'seek', 'affect',
        'handle', 'claim', 'study', 'produce', 'contain', 'reduce', 'establish',
        # Common generic words
        'other', 'another', 'some', 'any', 'no', 'every', 'each', 'both', 'few',
        'many', 'much', 'little', 'more', 'most', 'less', 'least', 'same', 'different',
        'new', 'old', 'big', 'small', 'good', 'bad', 'best', 'better', 'worse', 'worst',
        'only', 'just', 'also', 'very', 'even', 'back', 'well', 'way', 'here', 'there',
        'now', 'then', 'again', 'ever', 'never', 'always', 'often', 'sometimes',
        'usually', 'already', 'still', 'yet', 'once', 'twice', 'today', 'tomorrow',
        'yesterday'
    }

    REJECT_GEOGRAPHIC = {
        # Countries/continents
        'america', 'europe', 'asia', 'africa', 'australia', 'antarctica',
        'northamerica', 'southamerica', 'centralamerica', 'latinamerica',
        'middleeast', 'fareast', 'oceania', 'pacific', 'atlantic', 'indian',
        'arctic', 'southern', 'northern', 'eastern', 'western',
        # Major cities
        'detroit', 'chicago', 'london', 'paris', 'tokyo', 'seoul', 'beijing',
        'shanghai', 'singapore', 'sydney', 'berlin', 'rome', 'madrid', 'moscow',
        'mumbai', 'dubai', 'amsterdam', 'bangkok', 'barcelona', 'istanbul',
        'hongkong', 'toronto', 'vancouver', 'montreal', 'mexico', 'sanfrancisco',
        'losangeles', 'newyork', 'boston', 'washington', 'philadelphia', 'miami',
        'atlanta', 'dallas', 'houston', 'austin', 'denver', 'seattle', 'portland',
        'phoenix', 'lasvegas', 'sanjose', 'sandiego', 'minneapolis', 'kansas',
        'cleveland', 'pittsburgh', 'baltimore', 'charlotte', 'nashville', 'memphis',
        'orlando', 'tampa', 'jacksonville', 'raleigh', 'richmond', 'louisville',
        'columbus', 'indianapolis', 'milwaukee', 'oklahoma', 'omaha', 'saltlake',
        'reno', 'boise', 'honolulu', 'anchorage'
    }

    REJECT_PROFANITY = {
        'fuck', 'shit', 'damn', 'hell', 'bitch', 'bastard', 'ass'
    }

    REJECT_NAMES = {
        # Common first names
        'john', 'mary', 'gary', 'kiley', 'smith', 'jones', 'williams', 'brown',
        'davis', 'miller', 'wilson', 'moore', 'taylor', 'anderson', 'thomas',
        'jackson', 'white', 'harris', 'martin', 'thompson', 'garcia', 'martinez',
        'robinson', 'clark', 'rodriguez', 'lewis', 'lee', 'walker', 'hall',
        'allen', 'young', 'king', 'wright', 'scott', 'torres', 'hill', 'henry',
        'carl', 'murray', 'jefferson', 'james', 'robert', 'patricia', 'jennifer',
        'michael', 'linda', 'william', 'elizabeth', 'barbara', 'richard', 'susan',
        'joseph', 'jessica', 'sarah', 'charles', 'karen', 'nancy', 'christopher',
        'lisa', 'daniel', 'matthew', 'betty', 'donald', 'helen', 'paul', 'sandra',
        'mark', 'donna', 'george', 'dorothy', 'steven', 'carol', 'kenneth', 'julie',
        'brian', 'amanda', 'edward', 'shirley', 'ronald', 'melissa', 'anthony',
        'deborah', 'kevin', 'jason', 'stephanie', 'timothy', 'rebecca', 'jeffrey',
        'laura', 'ryan', 'sharon', 'jacob', 'cynthia', 'nicholas', 'amy', 'eric',
        'jonathan', 'angela', 'stephen', 'larry', 'anna', 'justin', 'pamela',
        'brandon', 'katherine', 'benjamin', 'emma', 'samuel', 'samantha', 'gregory',
        'alexander', 'christine', 'frank', 'deanna', 'raymond', 'joshua', 'patrick',
        'cheryl', 'jack', 'dennis', 'jerry', 'tyler', 'aaron', 'jose', 'adam',
        'nathan', 'douglas', 'zachary', 'peter', 'kyle', 'walter', 'ethan', 'jeremy',
        'harold', 'christian', 'keith', 'logan', 'noah', 'erik', 'roger', 'sean',
        'teresa', 'dylan', 'joe', 'juan', 'jordan', 'alberto', 'jesus', 'bobby',
        'harry', 'bradley', 'brad', 'albert', 'lucas', 'craig', 'alan', 'shawn',
        'grace', 'connor', 'sebastian', 'jared'
    }

    # Functional words - clear technical/business function
    FUNCTIONAL_WORDS = {
        # SaaS verbs
        'sync', 'merge', 'deploy', 'track', 'build', 'parse', 'render', 'queue',
        'route', 'stream', 'crawl', 'scrape', 'index', 'search', 'filter', 'sort',
        'group', 'aggregate', 'compute', 'calculate', 'validate', 'verify',
        'authenticate', 'authorize', 'encrypt', 'decrypt', 'compress', 'extract',
        'transform', 'convert', 'format', 'tokenize', 'stem', 'lemmatize',
        'cluster', 'classify', 'categorize', 'rank', 'score', 'recommend',
        'predict', 'forecast', 'analyze', 'visualize', 'notify', 'alert',
        'monitor', 'log', 'audit', 'backup', 'restore', 'replicate', 'shard',
        'partition', 'distribute', 'proxy', 'tunnel', 'bridge', 'gateway',
        'router', 'switch', 'schedule', 'trigger', 'listen', 'subscribe',
        'publish', 'broker', 'validate', 'verify',
        # Business nouns
        'payment', 'invoice', 'receipt', 'order', 'cart', 'checkout', 'shipment',
        'delivery', 'inventory', 'stock', 'warehouse', 'catalog', 'product',
        'service', 'subscription', 'membership', 'account', 'profile', 'user',
        'customer', 'client', 'partner', 'vendor', 'supplier', 'provider',
        'platform', 'marketplace', 'exchange', 'auction', 'bidding', 'contract',
        'compliance', 'dashboard', 'analytics', 'metrics', 'insights'
    }

    # Brandable words - strong brand potential
    BRANDABLE_WORDS = {
        # Short strong syllables
        'forge', 'pulse', 'nexus', 'apex', 'orbit', 'nova', 'beacon', 'vault',
        'spark', 'craft', 'bolt', 'arc', 'ion', 'ox', 'ax', 'flint', 'rock',
        'stone', 'steel', 'iron', 'gold', 'silver', 'zinc', 'lead', 'copper',
        'brass', 'bronze', 'metal', 'alloy', 'carbon', 'silicon', 'neon',
        'xenon', 'argon', 'krypton', 'radon', 'helium', 'lithium', 'sodium',
        'potassium', 'calcium', 'titanium', 'zirconium', 'platinum', 'palladium',
        # Energy/power
        'surge', 'flame', 'blaze', 'glow', 'shine', 'bright', 'vivid', 'flash',
        'volt', 'watt', 'amp', 'ohm', 'hertz', 'cycle', 'rhythm', 'beat', 'tempo',
        'pace', 'rate', 'speed', 'velocity', 'momentum', 'force', 'power', 'drive',
        'push', 'pull', 'lift', 'rise', 'boost', 'jump', 'leap', 'spring',
        'bounce', 'soar', 'climb', 'scale',
        # Abstract positive
        'flow', 'mesh', 'grid', 'sphere', 'circle', 'ring', 'loop', 'spiral',
        'vortex', 'whirl', 'spin', 'turn', 'twist', 'bend', 'curve', 'bow',
        'knot', 'tie', 'bind', 'bond',
        # Sensory
        'sonic', 'audio', 'visual', 'optic', 'chroma', 'spectrum', 'color',
        'hue', 'tint', 'shade', 'tone', 'pitch', 'note', 'chord', 'harmony',
        'melody', 'cadence', 'resonance', 'echo', 'prism', 'lens'
    }

    # Ambiguous words - can be either functional or brandable
    AMBIGUOUS_WORDS = {
        'cloud', 'data', 'code', 'tech', 'soft', 'ware', 'net', 'web', 'app',
        'api', 'sdk', 'bot', 'ai', 'ml', 'core', 'stack', 'hub', 'link', 'node',
        'edge', 'base', 'port', 'host', 'server', 'client', 'system', 'engine'
    }

    @classmethod
    def check_rejection_criteria(cls, word: str) -> List[str]:
        """Check if word should be rejected, return list of reasons"""
        word_lower = word.lower()
        reasons = []

        # Check for repeated characters (3+ consecutive)
        if len(word_lower) >= 3:
            for i in range(len(word_lower) - 2):
                if word_lower[i] == word_lower[i+1] == word_lower[i+2]:
                    reasons.append("repeated_chars")
                    break

        # Check generic words
        if word_lower in cls.REJECT_GENERIC_WORDS:
            reasons.append("generic_word")

        # Check geographic names
        if word_lower in cls.REJECT_GEOGRAPHIC:
            reasons.append("geographic_name")

        # Check profanity
        if word_lower in cls.REJECT_PROFANITY:
            reasons.append("profanity")

        # Check common names
        if word_lower in cls.REJECT_NAMES:
            reasons.append("common_name")

        # Check for non-English patterns (basic)
        if any(ord(c) > 127 for c in word):
            reasons.append("non_english_chars")

        return reasons

    @classmethod
    def determine_label(cls, word: str, judge_focus: str) -> str:
        """Determine label (functional/brandable/ambiguous) based on word and judge focus"""

        word_lower = word.lower()

        # Direct matches
        if word_lower in cls.FUNCTIONAL_WORDS:
            return 'functional'

        if word_lower in cls.BRANDABLE_WORDS:
            return 'brandable'

        if word_lower in cls.AMBIGUOUS_WORDS:
            return 'ambiguous'

        # Pattern-based classification
        # Check for common SaaS verb endings
        if word_lower.endswith(('sync', 'track', 'build', 'parse', 'render', 'queue',
                                  'route', 'stream', 'crawl', 'scrape', 'index')):
            return 'functional'

        # Check for brand-sounding endings
        if word_lower.endswith(('forge', 'pulse', 'nexus', 'apex', 'nova', 'vault',
                                  'spark', 'craft', 'bolt', 'arc')):
            return 'brandable'

        # Check for ambiguous-sounding endings
        if word_lower.endswith(('flow', 'core', 'stack', 'mesh', 'grid', 'hub',
                                  'link', 'node', 'edge', 'base')):
            return 'ambiguous'

        # Judge-specific bias
        if judge_focus == 'brand_focus':
            # Brand-focused judge leans toward brandable
            return 'brandable'
        elif judge_focus == 'tech_focus':
            # Tech-focused judge leans toward functional
            return 'functional'
        else:
            # Default to ambiguous for unknown words
            return 'ambiguous'

    @classmethod
    def get_rule_based_judgment(cls, word: str, judge_id: str,
                                 judge_focus: str) -> Dict[str, Any]:
        """Get rule-based judgment for a word (fallback when AI unavailable)"""

        # Check rejection criteria
        reject_reasons = cls.check_rejection_criteria(word)

        if reject_reasons:
            return {
                'decision': 'reject',
                'label': None,
                'confidence': 0.95,
                'why': reject_reasons
            }

        # Determine label
        label = cls.determine_label(word, judge_focus)

        # Accept with confidence based on clarity
        confidence = 0.75
        why = [f"passes_{judge_focus}_criteria", f"classified_as_{label}"]

        # Adjust confidence based on word characteristics
        word_lower = word.lower()
        if word_lower in cls.FUNCTIONAL_WORDS or word_lower in cls.BRANDABLE_WORDS:
            confidence = 0.85
            why.append("clear_category_match")
        elif word_lower in cls.AMBIGUOUS_WORDS:
            confidence = 0.70
            why.append("ambiguous_category")

        return {
            'decision': 'accept',
            'label': label,
            'confidence': confidence,
            'why': why
        }


def create_ai_judgment_prompt(word: str, judge_focus: str) -> str:
    """Create a prompt for AI judgment"""

    focus_descriptions = {
        'recall_focus': 'Recall-focused (most liberal): When in doubt, accept. Prioritize finding potential SaaS words over avoiding false positives.',
        'brand_focus': 'Brand-focused: Evaluate the word\'s potential as a SaaS brand name. Is it memorable, pronounceable, and brandable?',
        'tech_focus': 'Tech/Functional-focused: Evaluate the word\'s technical or functional meaning in SaaS context. Does it describe a feature, function, or technical concept?',
        'english_focus': 'English word verification: Is this a real English word? Accept technical terms and rare words, reject non-English and nonsense strings.',
        'balanced': 'Balanced review: Consider all aspects - brand potential, functional meaning, and word validity. Make a nuanced judgment.'
    }

    focus_desc = focus_descriptions.get(judge_focus, 'balanced')

    return f"""As a SaaS product naming expert, evaluate the word: "{word}"

Your perspective: {focus_desc}

Acceptance criteria (liberal):
- Real English words (including rare/technical terms)
- Functional SaaS terms: merge, sync, deploy, track, build, parse, render, queue, route, stream
- Brandable terms: forge, pulse, nexus, apex, orbit, nova, beacon, vault, spark, craft
- Descriptive terms: rapid, clear, smart, deep, bright, swift
- Abstract concepts: flow, core, stack, mesh, grid, bridge, hub, link, edge, node

Rejection criteria (only clear cases):
- Pure symbols: !!!, @#$, ---, ===
- URL fragments: http, www, .exe, /usr
- Code tokens: __init__, 0x1A2B
- 3+ consecutive identical characters: aaa, bbb, !!!
- Generic words: pronouns (me, you, he, she, it, we, they), articles (the, a, an), prepositions (of, in, on, at, to, for, with, by), conjunctions (and, but, or), auxiliary verbs (is, am, are, was, were, be, have, has, had, can, could, will, would)
- Geographic names: cities, countries
- Profanity: fuck, shit, damn, hell, bitch, bastard
- Common names: john, mary, smith, jones

Label categories:
- functional: Clear technical/business function (sync, merge, deploy, payment, invoice, authenticate)
- brandable: Strong brand potential (forge, pulse, nexus, surge, nova, beacon)
- ambiguous: Can be both (cloud, data, code, tech, web, app, api)

Respond in JSON format:
{{
  "decision": "accept" or "reject",
  "label": "functional" or "brandable" or "ambiguous" or null,
  "confidence": 0.0-1.0,
  "why": ["reason1", "reason2"]
}}"""


if __name__ == "__main__":
    # Test the judgment helper
    test_words = ['sync', 'forge', 'cloud', 'data', 'the', 'and', 'aaa', 'london']

    for word in test_words:
        print(f"\nEvaluating: {word}")
        reasons = AIJudgmentHelper.check_rejection_criteria(word)
        if reasons:
            print(f"  REJECT: {reasons}")
        else:
            for judge_focus in ['recall_focus', 'brand_focus', 'tech_focus', 'english_focus', 'balanced']:
                judgment = AIJudgmentHelper.get_rule_based_judgment(word, f'judge-{judge_focus}', judge_focus)
                print(f"  {judge_focus}: {judgment['decision']} ({judgment['label']}) conf={judgment['confidence']}")
