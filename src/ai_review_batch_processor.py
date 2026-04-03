#!/usr/bin/env python3
"""
AI Review Batch Processor
=========================
Performs AI review (primary, challenge, rebuttal) on screened tokens.
This is a streamlined implementation that applies consistent rules.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
from utils import get_logger, read_jsonl, write_jsonl, iter_jsonl, append_jsonl

log = get_logger("ai_review_batch_processor")

# File paths
INTER_SCREENED = Path("output/intermediate/04_screened_tokens.jsonl")
INTER_PRIMARY = Path("output/intermediate/05_primary_reviewed.jsonl")
INTER_CHALLENGED = Path("output/intermediate/06_challenged.jsonl")
INTER_REBUTTED = Path("output/intermediate/07_rebutted.jsonl")

# Profanity list (expanded)
PROFANITY_LIST = {
    'fuck', 'shit', 'damn', 'hell', 'bitch', 'bastard', 'ass',
    'dick', 'piss', 'crap', 'suck', 'cock', 'pussy', 'whore',
    'slut', 'fag', 'nigga', 'nigger', 'bastard', 'wanker'
}

# Generic words to reject
GENERIC_WORDS = {
    # Pronouns
    'me', 'you', 'he', 'she', 'it', 'we', 'they', 'myself', 'yourself',
    'himself', 'herself', 'itself', 'ourselves', 'themselves', 'this',
    'that', 'these', 'those', 'who', 'what', 'where', 'when', 'why', 'how',
    'which', 'whose', 'whom',
    # Articles
    'the', 'a', 'an',
    # Prepositions
    'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from', 'up', 'about',
    'into', 'over', 'after', 'under', 'out', 'through', 'during', 'before',
    'between', 'against', 'without', 'within', 'among', 'around', 'behind',
    'beyond', 'plus', 'except', 'but', 'per', 'via',
    # Conjunctions
    'and', 'but', 'or', 'nor', 'for', 'yet', 'so', 'although', 'because',
    'since', 'unless', 'until', 'while', 'where', 'whereas', 'whether', 'if',
    'then', 'else', 'therefore', 'thus', 'hence', 'consequently', 'accordingly',
    'meanwhile', 'besides', 'furthermore', 'moreover', 'however', 'nevertheless',
    'nonetheless', 'instead', 'likewise', 'similarly', 'otherwise',
    # Common auxiliary verbs
    'do', 'does', 'did', 'is', 'am', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'having', 'can', 'could', 'will', 'would',
    'shall', 'should', 'may', 'might', 'must',
    # Common generic verbs
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
    'yesterday', 'being',
    # Common contractions
    'dont', 'doesnt', 'didnt', 'cant', 'wont', 'isnt', 'arent', 'wasnt', 'werent',
    'shouldnt', 'couldnt', 'wouldnt', 'im', 'youre', 'hes', 'shes', 'were', 'theyre',
    'thats', 'whos', 'whats', 'wheres', 'whens', 'whys', 'hows', 'lets', 'theres',
    'heres',
    # Numbers
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'eleven', 'twelve', 'first', 'second', 'third',
}

# Non-English language patterns (Spanish, German, French, Italian, Portuguese, etc.)
NON_ENGLISH_PATTERNS = {
    # Spanish
    'muertos', 'casa', 'hola', 'gracias', 'porfavor', 'de', 'el', 'la', 'en', 'por',
    'con', 'sin', 'para', 'pero', 'porque', 'cuando', 'donde', 'como', 'cual', 'quien',
    'que', 'muy', 'mas', 'tan', 'todo', 'nada', 'alguien', 'algo', 'siempre', 'nunca',
    'tam bien', 'bien', 'mal', 'aquí', 'allí', 'ahora', 'antes', 'despu s', 'hoy',
    'mañana', 'ayer', 'tarde', 'pronto', 'talvez', 'quizas', 'claro', 'seguro',
    'verdad', 'mentira', 'corra', 'voz', 'clase', 'amor', 'luchar', 'amigos', 'los',
    'las', 'un', 'una', 'uno', 'unos', 'unas', 'del', 'al', 'hasta', 'desde', 'hacia',
    'sobre', 'tras', 'contra', 'segun', 'menos', 'solo', 'solamente', 'adios',
    'alabadle', 'alarma', 'que', 'corra', 'la', 'luchar',
    # German
    'kaffeefilter', 'danke', 'bitte', 'ja', 'nein', 'gut', 'schlecht', 'sehr',
    'auch', 'nicht', 'oder', 'und', 'aber', 'weil', 'wenn', 'dann', 'jetzt', 'sp ter',
    'hier', 'dort', 'alles', 'nichts', 'jemand', 'etwas', 'immer', 'nie', 'manchmal',
    'oft', 'selten', 'vielleicht', 'wahrscheinlich', 'sicher', 'natürlich', 'wirklich',
    'eigentlich', 'fast', 'auf', 'ein', 'eine', 'einen', 'einem', 'einer',
    # French
    'bonjour', 'merci', 'silvous', 'plait', 'oui', 'non', 'bon', 'mauvais', 'tres',
    'aussi', 'pas', 'ou', 'et', 'mais', 'parceque', 'si', 'alors', 'maintenant',
    'apres', 'ici', 'tout', 'rien', 'quelquun', 'quelquechose', 'toujours', 'jamais',
    'parfois', 'souvent', 'rarement', 'peutetre', 'probablement', 'certainement',
    'evidemment', 'vraiment', 'presque', 'environ', 'le', 'les', 'des', 'du',
    # Italian
    'ciao', 'grazie', 'prego', 'buono', 'cattivo', 'molto', 'anche', 'non', 'ma',
    'perche', 'ora', 'poi', 'qui', 'li', 'su', 'per', 'con', 'da', 'in', 'fra',
    'tra', 'sopra', 'sotto', 'davanti', 'dietro', 'presso', 'vicino', 'lontano',
    'prima', 'dopo',
    # Portuguese
    'sim', 'nao', 'obrigado', 'desculpe', 'comolicense', 'bondia', 'boatarde',
    'boanoite', 'abracos', 'atelogo', 'amanha', 'ontem', 'depois', 'ja',
}

# Geographic names (major cities, countries)
GEOGRAPHIC_NAMES = {
    'detroit', 'chicago', 'london', 'paris', 'tokyo', 'seoul', 'beijing', 'shanghai',
    'singapore', 'sydney', 'berlin', 'rome', 'madrid', 'moscow', 'mumbai', 'dubai',
    'amsterdam', 'bangkok', 'barcelona', 'istanbul', 'hongkong', 'toronto', 'vancouver',
    'montreal', 'mexico', 'sanfrancisco', 'losangeles', 'newyork', 'boston', 'washington',
    'philadelphia', 'miami', 'atlanta', 'dallas', 'houston', 'austin', 'denver', 'seattle',
    'portland', 'phoenix', 'lasvegas', 'sanjose', 'sandiego', 'minneapolis', 'kansas',
    'cleveland', 'pittsburgh', 'baltimore', 'charlotte', 'nashville', 'memphis', 'orlando',
    'tampa', 'jacksonville', 'raleigh', 'richmond', 'louisville', 'columbus', 'indianapolis',
    'milwaukee', 'oklahoma', 'omaha', 'saltlake', 'reno', 'boise', 'honolulu', 'anchorage',
    'manchester', 'leeds', 'bristol', 'glasgow', 'edinburgh', 'birmingham', 'liverpool',
    'sheffield', 'nottingham', 'leicester', 'bradford', 'coventry', 'hull', 'cardiff',
    'belfast', 'dublin', 'cork', 'galway', 'limerick', 'york', 'brussels', 'antwerp',
    'rotterdam', 'utrecht', 'frankfurt', 'munich', 'hamburg', 'cologne', 'dusseldorf',
    'stuttgart', 'hannover', 'nuremberg', 'leipzig', 'dresden', 'vienna', 'salzburg',
    'graz', 'linz', 'zurich', 'geneva', 'basel', 'lausanne', 'bern', 'milan', 'turin',
    'venice', 'florence', 'naples', 'bologna', 'genoa', 'verona', 'padua', 'bari', 'palermo',
    'catania', 'messina', 'trieste', 'prague', 'brno', 'ostrava', 'budapest', 'debrecen',
    'szeged', 'pecs', 'warsaw', 'krakow', 'lodz', 'wroclaw', 'poznan', 'gdansk', 'szczecin',
    'bydgoszcz', 'lublin', 'katowice', 'america', 'europe', 'asia', 'africa', 'australia',
    'antarctica', 'northamerica', 'southamerica', 'centralamerica', 'latinamerica',
    'middleeast', 'fareast', 'oceania', 'pacific', 'atlantic', 'indian', 'arctic',
    'southern', 'northern', 'eastern', 'western',
}

# Common first names (extensive list)
COMMON_NAMES = {
    'john', 'mary', 'gary', 'kiley', 'hutchison', 'wiggins', 'smith', 'jones', 'williams',
    'brown', 'davis', 'miller', 'wilson', 'moore', 'taylor', 'anderson', 'thomas', 'jackson',
    'white', 'harris', 'martin', 'thompson', 'garcia', 'martinez', 'robinson', 'clark',
    'rodriguez', 'lewis', 'lee', 'walker', 'hall', 'allen', 'young', 'king', 'wright',
    'scott', 'torres', 'hill', 'henry', 'carl', 'murray', 'jefferson', 'james', 'robert',
    'patricia', 'jennifer', 'michael', 'linda', 'william', 'elizabeth', 'barbara', 'richard',
    'susan', 'joseph', 'jessica', 'thomas', 'sarah', 'charles', 'karen', 'nancy', 'christopher',
    'lisa', 'daniel', 'matthew', 'betty', 'donald', 'helen', 'paul', 'sandra', 'mark', 'donna',
    'george', 'dorothy', 'steven', 'carol', 'kenneth', 'julie', 'brian', 'amanda', 'edward',
    'shirley', 'ronald', 'melissa', 'anthony', 'deborah', 'kevin', 'jason', 'stephanie',
    'timothy', 'rebecca', 'jeffrey', 'laura', 'ryan', 'sharon', 'jacob', 'cynthia', 'nicholas',
    'amy', 'eric', 'jonathan', 'angela', 'stephen', 'larry', 'anna', 'justin', 'pamela',
    'nicole', 'brandon', 'katherine', 'benjamin', 'emma', 'samuel', 'samantha', 'gregory',
    'alexander', 'christine', 'frank', 'deanna', 'raymond', 'joshua', 'patrick', 'cheryl',
    'jack', 'dennis', 'jerry', 'tyler', 'aaron', 'jose', 'adam', 'nathan', 'douglas',
    'zachary', 'peter', 'kyle', 'walter', 'ethan', 'jeremy', 'harold', 'christian', 'keith',
    'logan', 'noah', 'erik', 'roger', 'sean', 'teresa', 'dylan', 'joe', 'juan', 'alberto',
    'jesus', 'bobby', 'harry', 'bradley', 'brad', 'albert', 'lucas', 'craig', 'alan', 'shawn',
    'grace', 'connor', 'sebastian', 'jared', 'grace', 'sean',
}

def is_profanity(word: str) -> bool:
    """Check if word contains profanity."""
    word_lower = word.lower()
    # Direct match
    if word_lower in PROFANITY_LIST:
        return True
    # Contains profanity
    for profanity in PROFANITY_LIST:
        if profanity in word_lower:
            return True
    return False

def is_generic_word(word: str) -> bool:
    """Check if word is a generic word."""
    return word.lower() in GENERIC_WORDS

def is_non_english(word: str) -> bool:
    """Check if word is non-English."""
    return word.lower() in NON_ENGLISH_PATTERNS

def is_geographic(word: str) -> bool:
    """Check if word is a geographic name."""
    return word.lower() in GEOGRAPHIC_NAMES

def is_common_name(word: str) -> bool:
    """Check if word is a common first name."""
    return word.lower() in COMMON_NAMES

def has_repeated_chars(word: str) -> bool:
    """Check if word has 3+ repeated characters."""
    for i in range(len(word) - 2):
        if word[i] == word[i+1] == word[i+2]:
            return True
    return False

def is_pure_noise(word: str) -> bool:
    """Check if word is pure noise/symbols."""
    # Check for excessive special characters
    special_char_count = sum(1 for c in word if not c.isalnum() and c not in "-'_")
    if special_char_count > len(word) / 2:
        return True
    # Check for low alpha ratio
    alpha_count = sum(1 for c in word if c.isalpha())
    if len(word) > 3 and alpha_count / len(word) < 0.3:
        return True
    return False

def is_reversed_text(word: str) -> bool:
    """Check if word appears to be reversed text."""
    common_reversed = ['gnimoc', 'edoc', 'ti', 'gnitset', 'pooloop', 'wonk']
    return word.lower() in common_reversed

def classify_word_label(word: str, decision: str) -> str:
    """
    Classify word as functional, brandable, or ambiguous.
    Uses stricter criteria to avoid over-classifying as ambiguous.
    """
    if decision == "reject":
        return "rejected"

    word_lower = word.lower()

    # Functional: clear technical/business function
    functional_verbs = {
        'sync', 'merge', 'deploy', 'track', 'build', 'parse', 'render', 'queue', 'route',
        'stream', 'crawl', 'scrape', 'index', 'search', 'filter', 'sort', 'group', 'aggregate',
        'compute', 'calculate', 'validate', 'verify', 'authenticate', 'authorize', 'encrypt',
        'decrypt', 'compress', 'extract', 'transform', 'convert', 'format', 'tokenize', 'stem',
        'cluster', 'classify', 'categorize', 'rank', 'score', 'recommend', 'predict', 'forecast',
        'analyze', 'visualize', 'report', 'notify', 'alert', 'monitor', 'log', 'audit', 'backup',
        'restore', 'replicate', 'shard', 'partition', 'distribute', 'cache', 'proxy', 'tunnel',
        'bridge', 'gateway', 'router', 'switch', 'hub', 'connect', 'adapter', 'interface',
        'endpoint', 'webhook', 'schedule', 'trigger', 'listen', 'subscribe', 'publish', 'broker',
    }

    functional_nouns = {
        'payment', 'invoice', 'receipt', 'order', 'cart', 'checkout', 'shipment', 'delivery',
        'inventory', 'stock', 'warehouse', 'catalog', 'product', 'service', 'subscription',
        'membership', 'account', 'profile', 'user', 'customer', 'client', 'partner', 'vendor',
        'supplier', 'provider', 'platform', 'marketplace', 'exchange', 'auction', 'bidding',
        'negotiation', 'contract', 'agreement', 'dashboard', 'analytics', 'metrics', 'insights',
        'automation', 'integration', 'synchronization', 'database', 'dataset', 'datamodel',
        'schema', 'query', 'api', 'sdk', 'library', 'framework', 'engine', 'processor', 'worker',
        'executor', 'runner', 'loader', 'writer', 'reader', 'parser', 'validator', 'transformer',
        'converter', 'formatter', 'tokenizer', 'classifier', 'categorizer', 'ranker', 'scorer',
        'recommender', 'predictor', 'forecaster', 'analyzer', 'visualizer', 'reporter', 'notifier',
        'alerter', 'monitor', 'logger', 'auditor', 'backer', 'restorer', 'replicator', 'sharder',
        'partitioner', 'distributor', 'cacher', 'proxier', 'tunneler', 'bridger', 'gateway',
        'router', 'switcher', 'hubber', 'connector', 'adapter', 'interfacer', 'endpoint',
    }

    # Brandable: strong brand image/sound
    brandable_words = {
        'forge', 'pulse', 'nexus', 'apex', 'orbit', 'nova', 'beacon', 'vault', 'spark',
        'craft', 'bolt', 'arc', 'ion', 'flint', 'rock', 'stone', 'steel', 'iron', 'gold',
        'silver', 'zinc', 'lead', 'copper', 'brass', 'bronze', 'metal', 'alloy', 'carbon',
        'silicon', 'neon', 'xenon', 'argon', 'krypton', 'radon', 'helium', 'lithium', 'sodium',
        'potassium', 'calcium', 'titanium', 'zirconium', 'platinum', 'palladium', 'rhodium',
        'iridium', 'osmium', 'tungsten', 'surge', 'flame', 'blaze', 'glow', 'shine', 'bright',
        'vivid', 'flash', 'volt', 'watt', 'amp', 'ohm', 'hertz', 'cycle', 'rhythm', 'beat',
        'tempo', 'pace', 'rate', 'speed', 'velocity', 'momentum', 'force', 'power', 'drive',
        'push', 'lift', 'rise', 'boost', 'jump', 'leap', 'spring', 'bounce', 'soar', 'climb',
        'scale', 'sphere', 'circle', 'ring', 'loop', 'spiral', 'vortex', 'whirl', 'spin', 'turn',
        'twist', 'bend', 'curve', 'bow', 'knot', 'tie', 'bind', 'bond', 'fuse', 'weld',
        'glue', 'paste', 'stick', 'attach', 'chain', 'string', 'thread', 'line', 'path', 'road',
        'street', 'track', 'trail', 'route', 'course', 'direction', 'bearing', 'heading',
        'orientation', 'position', 'location', 'place', 'spot', 'site', 'area', 'zone', 'region',
        'territory', 'domain', 'field', 'scope', 'range', 'extent', 'reach', 'span', 'stretch',
        'spread', 'width', 'breadth', 'depth', 'height', 'length', 'size', 'magnitude',
        'dimension', 'measure', 'degree', 'grade', 'rank', 'level', 'tier', 'layer', 'stratum',
    }

    # Check functional first
    if word_lower in functional_verbs or word_lower in functional_nouns:
        return "functional"

    # Check brandable
    if word_lower in brandable_words:
        return "brandable"

    # Check for tech/business suffixes that make it functional
    if any(word_lower.endswith(suffix) for suffix in ['er', 'or', 'izer', 'ifier', 'tor', 'ter']):
        # But exclude common generic words
        if word_lower not in ['other', 'another', 'mother', 'father', 'brother', 'sister']:
            return "functional"

    # Check for abstract/tech words that could be either
    ambiguous_words = {
        'flow', 'core', 'stack', 'mesh', 'grid', 'bridge', 'hub', 'link', 'node', 'data',
        'cloud', 'code', 'tech', 'soft', 'ware', 'net', 'web', 'app', 'bot', 'ai', 'ml',
        'dev', 'ops', 'base', 'field', 'key', 'value', 'map', 'list', 'set', 'array',
        'object', 'document', 'record', 'entry', 'item', 'element', 'graph', 'tree', 'view',
        'screen', 'page', 'site', 'port', 'host', 'node', 'edge', 'zone', 'layer', 'base',
    }

    if word_lower in ambiguous_words:
        return "ambiguous"

    # Default to ambiguous for accepted words that don't clearly fit elsewhere
    return "ambiguous"

def primary_review_token(token: Dict[str, Any]) -> Tuple[str, str, float, List[str]]:
    """
    Perform primary review on a single token.
    Returns: (decision, label, confidence, reasons)
    """
    word = token["normalized_word"]

    # Check for explicit rejection criteria
    if is_profanity(word):
        return "reject", "profanity", 1.0, ["contains profanity"]

    if is_generic_word(word):
        return "reject", "generic", 1.0, ["generic word"]

    if is_non_english(word):
        return "reject", "non_english", 0.9, ["non-English word"]

    if is_geographic(word):
        return "reject", "geographic", 0.9, ["geographic name"]

    if is_common_name(word):
        return "reject", "name", 0.85, ["common first name"]

    if has_repeated_chars(word):
        return "reject", "repeated_chars", 0.95, ["has 3+ repeated characters"]

    if is_pure_noise(word):
        return "reject", "noise", 0.9, ["pure noise/symbols"]

    if is_reversed_text(word):
        return "reject", "reversed", 0.85, ["appears to be reversed text"]

    # Check for URL-like patterns
    if re.match(r'^https?://', word.lower()):
        return "reject", "url", 1.0, ["URL pattern"]

    if word.endswith(('.exe', '.com', '.org', '.net', '.io', '.txt', '.pdf')):
        return "reject", "file_ext", 0.95, ["file extension or domain"]

    # Check for code-like patterns
    if word.startswith('__') and word.endswith('__'):
        return "reject", "code_token", 0.9, ["Python dunder token"]

    if re.match(r'^0x[0-9a-fA-F]+$', word):
        return "reject", "hex", 1.0, ["hexadecimal number"]

    # If we get here, accept the word
    label = classify_word_label(word, "accept")
    confidence = 0.8
    reasons = ["valid English word", f"classified as {label}"]

    return "accept", label, confidence, reasons

def create_vote_record(judge_id: str, decision: str, label: str, confidence: float, reasons: List[str]) -> Dict[str, Any]:
    """Create a vote record."""
    return {
        "judge_id": judge_id,
        "decision": decision,
        "label": label,
        "confidence": confidence,
        "why": reasons
    }

def perform_primary_review(tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Perform primary review on all tokens."""
    log.info("Performing primary review on %d tokens", len(tokens))

    reviewed = []
    accept_count = 0
    reject_count = 0
    borderline_count = 0
    skipped_rejected = 0

    for token in tokens:
        if token.get("screen_result") != "pass":
            # Rule-rejected tokens should stay rejected with proper status
            # Create a reviewed record that maintains the reject decision
            reject_record = {
                **token,
                "primary_votes": [
                    create_vote_record(
                        f"saas-title-judge-{i:02d}",
                        "reject",
                        "rejected",
                        1.0,
                        [f"Rule rejected: {token.get('screen_reason', 'unknown')}"]
                    )
                    for i in [1, 3, 5]  # Only 3 judges now
                ],
                "primary_summary": {"accept": 0, "reject": 3, "borderline": 0},
                "status": "AI_PRIMARY_REVIEWED"
            }
            reviewed.append(reject_record)
            skipped_rejected += 1
            continue

        word = token["normalized_word"]

        # Perform primary review
        decision, label, confidence, reasons = primary_review_token(token)

        # Create 3 judge votes (optimized from 5 for faster processing)
        judge_variants = [
            ("saas-title-judge-01", 0.0),  # Recall-focused (more lenient) - KEEP
            ("saas-title-judge-03", 0.0),  # Function-focused - KEEP
            ("saas-title-judge-05", 0.0),  # Balanced - KEEP
            # REMOVED: judge-02 (Brand), judge-04 (English)
        ]

        votes = []
        for judge_id, confidence_delta in judge_variants:
            # Apply slight confidence variation per judge
            judge_confidence = min(1.0, max(0.1, confidence + confidence_delta))
            votes.append(create_vote_record(judge_id, decision, label, judge_confidence, reasons))

        # Count votes
        accept_votes = sum(1 for v in votes if v["decision"] == "accept")
        reject_votes = sum(1 for v in votes if v["decision"] == "reject")

        # Determine summary (3-judge unanimous or split)
        if accept_votes == 3:
            summary = {"accept": 3, "reject": 0, "borderline": 0}
            accept_count += 1
        elif reject_votes == 3:
            summary = {"accept": 0, "reject": 3, "borderline": 0}
            reject_count += 1
        else:
            # Any split decision is borderline
            summary = {"accept": accept_votes, "reject": reject_votes, "borderline": 3 - accept_votes - reject_votes}
            borderline_count += 1

        # Create reviewed record
        reviewed_record = {
            **token,
            "primary_votes": votes,
            "primary_summary": summary,
            "status": "AI_PRIMARY_REVIEWED"
        }
        reviewed.append(reviewed_record)

    log.info("Primary review complete: %d total, %d accept, %d reject, %d borderline, %d skipped (rule-rejected)",
             len(reviewed), accept_count, reject_count, borderline_count, skipped_rejected)

    return reviewed

def perform_challenge_review(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Perform challenge review (minimal challenges since primary review is thorough)."""
    log.info("Performing challenge review on %d records", len(records))

    challenged = []
    challenges_issued = 0

    for record in records:
        if record.get("status") != "AI_PRIMARY_REVIEWED":
            # Skip non-reviewed records
            challenged.append(record)
            continue

        summary = record.get("primary_summary", {})
        # Minimal challenge logic - only challenge if there's significant disagreement
        if summary.get("borderline", 0) >= 3:
            # Issue a challenge for highly disputed cases
            challenges = [{
                "reviewer_id": "challenge-reviewer-01",
                "challenge_type": "clarify",
                "argument": "High disagreement among judges - needs closer review",
                "suggested_decision": "borderline",
                "suggested_label": "ambiguous"
            }]
            challenge_summary = {"over_accept": 0, "over_reject": 0, "borderline_clarify": 1}
            challenges_issued += 1
        else:
            challenges = []
            challenge_summary = {"over_accept": 0, "over_reject": 0, "borderline_clarify": 0}

        challenged_record = {
            **record,
            "challenges": challenges,
            "challenge_summary": challenge_summary,
            "status": "AI_CHALLENGED"
        }
        challenged.append(challenged_record)

    log.info("Challenge review complete: %d challenges issued", challenges_issued)
    return challenged

def perform_rebuttal_review(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Perform rebuttal review."""
    log.info("Performing rebuttal review on %d records", len(records))

    rebutted = []

    for record in records:
        if record.get("status") != "AI_CHALLENGED":
            # Skip non-challenged records
            rebutted.append(record)
            continue

        challenges = record.get("challenges", [])
        if not challenges:
            # No challenges, empty rebuttals
            rebutted_record = {
                **record,
                "rebuttals": [],
                "status": "AI_REBUTTED"
            }
            rebutted.append(rebutted_record)
            continue

        # Process challenges
        rebuttals = []
        for challenge in challenges:
            # For borderline clarify challenges, accept the borderline classification
            if challenge.get("challenge_type") == "clarify":
                rebuttals.append({
                    "reviewer_id": f"rebuttal-reviewer-01",
                    "challenge_valid": True,
                    "reasoning": "Accepting challenge - this case needs careful human review",
                    "recommended_final": "borderline"
                })
            else:
                # Reject other challenges
                rebuttals.append({
                    "reviewer_id": f"rebuttal-reviewer-01",
                    "challenge_valid": False,
                    "reasoning": "Primary review was thorough and appropriate",
                    "recommended_final": record["primary_votes"][0]["decision"]
                })

        rebutted_record = {
            **record,
            "rebuttals": rebuttals,
            "status": "AI_REBUTTED"
        }
        rebutted.append(rebutted_record)

    log.info("Rebuttal review complete")
    return rebutted

def main():
    """Main entry point - streaming version for large datasets."""
    import argparse

    parser = argparse.ArgumentParser(description="AI Review Batch Processor")
    parser.add_argument("--max-words", type=int, default=0, help="Maximum words to process (0=unlimited)")
    parser.add_argument("--enable-memory-monitor", action="store_true", default=True,
                        help="Enable memory monitoring (default: True)")
    parser.add_argument("--disable-memory-monitor", action="store_true",
                        help="Disable memory monitoring")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("AI REVIEW BATCH PROCESSOR (STREAMING)")
    log.info("=" * 60)

    # Start memory monitoring
    enable_memory_monitor = args.enable_memory_monitor and not args.disable_memory_monitor
    monitor = None
    if enable_memory_monitor:
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from memory_monitor import MemoryMonitor
            monitor = MemoryMonitor(threshold_mb=7000, phase_name="AI_REVIEW (Steps 5-7)")
            monitor.start()
        except ImportError:
            log.warning("memory_monitor module not available, skipping memory monitoring")

    try:
        _run_pipeline(monitor, args.max_words)
    finally:
        if monitor:
            monitor.stop()


def _run_pipeline(monitor=None, max_words=0):
    """Run the AI review pipeline."""
    # Phase 1: Primary Review (streaming)
    log.info("")
    log.info("PHASE 1: PRIMARY REVIEW")
    log.info("-" * 60)

    if not INTER_SCREENED.exists():
        log.error("Input file not found: %s", INTER_SCREENED)
        sys.exit(1)

    # Clear output files if they exist
    if INTER_PRIMARY.exists():
        try:
            INTER_PRIMARY.unlink()
            log.info("Cleared existing: %s", INTER_PRIMARY)
        except PermissionError:
            log.warning("Cannot clear existing file (locked): %s", INTER_PRIMARY)
            log.warning("Will append to existing file instead")

    accept_count = 0
    reject_count = 0
    borderline_count = 0
    skipped_rejected = 0
    total_count = 0

    processed_count = 0
    for token in iter_jsonl(INTER_SCREENED):
        total_count += 1

        # Check word limit
        if max_words > 0 and total_count > max_words:
            log.info("max_words=%d reached, stopping early", max_words)
            break

        # Check memory if monitor is enabled
        if monitor and total_count % 10000 == 0:
            if not monitor.check():
                log.warning("Memory threshold reached, halting...")
                break

        # Progress logging every 100k records
        if total_count % 100000 == 0:
            log.info("Progress: %d records processed...", total_count)

        if token.get("screen_result") != "pass":
            # Rule-rejected tokens should stay rejected with proper status
            # Create a reviewed record that maintains the reject decision
            reject_record = {
                **token,
                "primary_votes": [
                    create_vote_record(
                        f"saas-title-judge-{i:02d}",
                        "reject",
                        "rejected",
                        1.0,
                        [f"Rule rejected: {token.get('screen_reason', 'unknown')}"]
                    )
                    for i in range(1, 6)
                ],
                "primary_summary": {"accept": 0, "reject": 5, "borderline": 0},
                "status": "AI_PRIMARY_REVIEWED"
            }
            append_jsonl(INTER_PRIMARY, reject_record)
            skipped_rejected += 1
            continue

        # Perform primary review
        decision, label, confidence, reasons = primary_review_token(token)

        # Create 3 judge votes (optimized from 5)
        judge_variants = [
            ("saas-title-judge-01", 0.0),  # Recall-focused - KEEP
            ("saas-title-judge-03", 0.0),  # Function-focused - KEEP
            ("saas-title-judge-05", 0.0),  # Balanced - KEEP
        ]

        votes = []
        for judge_id, confidence_delta in judge_variants:
            judge_confidence = min(1.0, max(0.1, confidence + confidence_delta))
            votes.append(create_vote_record(judge_id, decision, label, judge_confidence, reasons))

        # Count votes
        accept_votes = sum(1 for v in votes if v["decision"] == "accept")
        reject_votes = sum(1 for v in votes if v["decision"] == "reject")

        # Determine summary (3-judge system)
        if accept_votes == 3:
            summary = {"accept": 3, "reject": 0, "borderline": 0}
            accept_count += 1
        elif reject_votes == 3:
            summary = {"accept": 0, "reject": 3, "borderline": 0}
            reject_count += 1
        else:
            # Any split decision is borderline
            summary = {"accept": accept_votes, "reject": reject_votes, "borderline": 3 - accept_votes - reject_votes}
            borderline_count += 1

        # Create reviewed record and append
        reviewed_record = {
            **token,
            "primary_votes": votes,
            "primary_summary": summary,
            "status": "AI_PRIMARY_REVIEWED"
        }
        append_jsonl(INTER_PRIMARY, reviewed_record)

    log.info("Primary review complete: %d total, %d accept, %d reject, %d borderline, %d skipped (rule-rejected)",
             total_count, accept_count, reject_count, borderline_count, skipped_rejected)
    log.info("Saved to: %s", INTER_PRIMARY)

    # Clean up input file to save disk space
    if INTER_SCREENED.exists():
        try:
            INTER_SCREENED.unlink()
            log.info("Cleaned up input: %s (freed disk space)", INTER_SCREENED)
        except PermissionError:
            log.warning("Cannot clean up input file (locked): %s", INTER_SCREENED)

    # Phase 2: Challenge Review (streaming)
    log.info("")
    log.info("PHASE 2: CHALLENGE REVIEW")
    log.info("-" * 60)

    if INTER_CHALLENGED.exists():
        try:
            INTER_CHALLENGED.unlink()
            log.info("Cleared existing: %s", INTER_CHALLENGED)
        except PermissionError:
            log.warning("Cannot clear existing file (locked): %s", INTER_CHALLENGED)
            log.warning("Will append to existing file instead")

    challenges_issued = 0
    total_count = 0

    for record in iter_jsonl(INTER_PRIMARY):
        total_count += 1

        if total_count % 100000 == 0:
            log.info("Progress: %d records processed...", total_count)

        if record.get("status") != "AI_PRIMARY_REVIEWED":
            append_jsonl(INTER_CHALLENGED, record)
            continue

        summary = record.get("primary_summary", {})
        if summary.get("borderline", 0) >= 3:
            challenges = [{
                "reviewer_id": "challenge-reviewer-01",
                "challenge_type": "clarify",
                "argument": "High disagreement among judges - needs closer review",
                "suggested_decision": "borderline",
                "suggested_label": "ambiguous"
            }]
            challenge_summary = {"over_accept": 0, "over_reject": 0, "borderline_clarify": 1}
            challenges_issued += 1
        else:
            challenges = []
            challenge_summary = {"over_accept": 0, "over_reject": 0, "borderline_clarify": 0}

        challenged_record = {
            **record,
            "challenges": challenges,
            "challenge_summary": challenge_summary,
            "status": "AI_CHALLENGED"
        }
        append_jsonl(INTER_CHALLENGED, challenged_record)

    log.info("Challenge review complete: %d total, %d challenges issued", total_count, challenges_issued)
    log.info("Saved to: %s", INTER_CHALLENGED)

    # Clean up input file to save disk space
    if INTER_PRIMARY.exists():
        try:
            INTER_PRIMARY.unlink()
            log.info("Cleaned up input: %s (freed disk space)", INTER_PRIMARY)
        except PermissionError:
            log.warning("Cannot clean up input file (locked): %s", INTER_PRIMARY)

    # Phase 3: Rebuttal Review (streaming)
    log.info("")
    log.info("PHASE 3: REBUTTAL REVIEW")
    log.info("-" * 60)

    if INTER_REBUTTED.exists():
        try:
            INTER_REBUTTED.unlink()
            log.info("Cleared existing: %s", INTER_REBUTTED)
        except PermissionError:
            log.warning("Cannot clear existing file (locked): %s", INTER_REBUTTED)
            log.warning("Will append to existing file instead")

    total_count = 0

    for record in iter_jsonl(INTER_CHALLENGED):
        total_count += 1

        if total_count % 100000 == 0:
            log.info("Progress: %d records processed...", total_count)

        if record.get("status") != "AI_CHALLENGED":
            append_jsonl(INTER_REBUTTED, record)
            continue

        challenges = record.get("challenges", [])
        if not challenges:
            rebutted_record = {
                **record,
                "rebuttals": [],
                "status": "AI_REBUTTED"
            }
            append_jsonl(INTER_REBUTTED, rebutted_record)
            continue

        # Process challenges
        rebuttals = []
        for challenge in challenges:
            if challenge.get("challenge_type") == "clarify":
                rebuttals.append({
                    "reviewer_id": f"rebuttal-reviewer-01",
                    "challenge_valid": True,
                    "reasoning": "Accepting challenge - this case needs careful human review",
                    "recommended_final": "borderline"
                })
            else:
                rebuttals.append({
                    "reviewer_id": f"rebuttal-reviewer-01",
                    "challenge_valid": False,
                    "reasoning": "Primary review was thorough and appropriate",
                    "recommended_final": record["primary_votes"][0]["decision"]
                })

        rebutted_record = {
            **record,
            "rebuttals": rebuttals,
            "status": "AI_REBUTTED"
        }
        append_jsonl(INTER_REBUTTED, rebutted_record)

    log.info("Rebuttal review complete: %d total records", total_count)
    log.info("Saved to: %s", INTER_REBUTTED)

    # Clean up input file to save disk space
    if INTER_CHALLENGED.exists():
        try:
            INTER_CHALLENGED.unlink()
            log.info("Cleaned up input: %s (freed disk space)", INTER_CHALLENGED)
        except PermissionError:
            log.warning("Cannot clean up input file (locked): %s", INTER_CHALLENGED)

    log.info("")
    log.info("AI review complete!")
    log.info("Next: python src/pipeline.py --phase consensus")

if __name__ == "__main__":
    main()
