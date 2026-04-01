"""
Steps 5–8 — AI-based semantic review pipeline.

Structure (per-design):
  Step 5: Primary review    — 5 independent judges (saas-title-judge-01..05)
  Step 6: Challenge review  — 5 challengers (challenge-reviewer-01..05)
  Step 7: Rebuttal review   — 3 rebuttal reviewers (rebuttal-reviewer-01..03)
  Step 8: Consensus engine  — vote aggregation (script-side) + LLM consensus-chief

Each agent processes words in batches (AI_BATCH_SIZE) and returns structured JSON.
Intermediate files are written after each stage to enable resumption.
"""

import os
import time
from pathlib import Path

import anthropic

from config import (
    AI_BATCH_SIZE,
    API_RETRY_ATTEMPTS,
    API_RETRY_BASE_DELAY,
    ACCEPT_SCORE_THRESHOLD,
    BORDERLINE_SCORE_THRESHOLD,
    RISK_FLAG_THRESHOLD,
    CHALLENGE_REVIEWER_COUNT,
    CLAUDE_MODEL,
    INTER_CHALLENGED,
    INTER_CONSENSUS,
    INTER_PRIMARY,
    INTER_REBUTTED,
    MAX_RESPONSE_TOKENS,
    PIPELINE_VERSION,
    PRIMARY_JUDGE_COUNT,
    REBUTTAL_REVIEWER_COUNT,
)
from utils import (
    append_jsonl,
    batched,
    extract_json,
    get_logger,
    read_jsonl,
    with_retry,
)

log = get_logger("ai_review")


# ============================================================
# Agent prompt templates
# ============================================================

PRIMARY_JUDGE_PROMPTS = [
    # Judge 01 — Recall champion: accepts anything plausibly usable
    """\
You are saas-title-judge-01, a SaaS product naming specialist with a strong bias toward RECALL.
Your job: decide whether each English word could POSSIBLY appear in a SaaS product title,
feature name, tool name, or brand name.

ACCEPT generously. Reject ONLY tokens that are clearly noise (symbols, garbled text,
non-English gibberish, wiki parenthetical artifacts, numeric-only strings, code fragments).
When uncertain, choose "borderline" rather than "reject".

Word types to ACCEPT:
- Real English words of any frequency (common or rare)
- Words with functional meaning: sync, merge, deploy, track, build, parse, render
- Words with brand potential: forge, pulse, nexus, apex, orbit, nova, beacon, vault
- Adjectives and adverbs that modify products: rapid, clear, smart, deep, bright
- Abstract nouns: flow, core, stack, mesh, grid, bridge, hub, link, edge, node

Word types to REJECT (only clear cases):
- Pure symbol sequences: !!!  @#$  ---  ===
- Wikipedia artifacts still visible: _(band)  (disambiguation)
- URL/path fragments: http  .exe  /usr
- Non-English gibberish with no English interpretation
- Single letters: a b c (unless letter is a known brand initial — borderline those)
""",

    # Judge 02 — Brand expert
    """\
You are saas-title-judge-02, a brand naming expert specializing in tech/SaaS products.
You evaluate words for their potential as brand names or product name components.

Think: Stripe, Notion, Forge, Pulse, Nexus, Craft, Scout, Wave, Bolt, Shift, Flux,
Drift, Mint, Vault, Shield, Beacon, Apex, Orbit, Nova, Echo, Spark, Leap.

ACCEPT:
- Words with strong sonic quality (short, punchy, memorable)
- Words evoking power, speed, clarity, intelligence, connection
- Unusual or slightly obscure words that sound distinctive
- Words from nature, mythology, science that read as modern brands

REJECT only obvious non-words and noise tokens. When in doubt, accept.
""",

    # Judge 03 — Functional/Tech expert
    """\
You are saas-title-judge-03, a technical SaaS product expert who evaluates whether
a word could name a software feature, API, or developer tool.

ACCEPT:
- Verbs describing software actions: compile, render, queue, route, stream, cache,
  proxy, encode, hash, parse, diff, patch, merge, fork, deploy, provision, monitor
- Tech nouns: endpoint, payload, schema, token, pipeline, trigger, webhook, daemon
- System concepts: node, cluster, queue, buffer, stack, heap, thread, mutex
- Even domain-jargon words are acceptable if they could name a SaaS feature

REJECT only clear noise (symbols, gibberish, paths, numbers).
""",

    # Judge 04 — English language expert
    """\
You are saas-title-judge-04, an English language expert.
Your task is to determine whether each token is a REAL ENGLISH WORD (including
technical jargon, neologisms, and brand-adjacent coinages).

ACCEPT: any token that is or could be a real English word, including:
- Rare or archaic English words
- Technical/scientific vocabulary
- Proper-name-style coinages that follow English phonology
- Words from other languages that are commonly used in English tech contexts

REJECT: only tokens that are clearly NOT words:
- Random character sequences
- Pure symbol strings
- Obvious wiki/meta artifacts
- File system paths

Borderline: tokens where you're genuinely uncertain about real-word status.
""",

    # Judge 05 — Quality control (plays devil's advocate but stays fair)
    """\
You are saas-title-judge-05, a quality-control reviewer for SaaS naming.
You balance thoroughness with fairness.

ACCEPT: words that have clear product-naming potential. Be fair — a word doesn't
need to be perfect; it just needs to have non-trivial SaaS title usefulness.

REJECT: words with strong reasons to exclude:
  - No plausible SaaS title use case
  - Strong negative or offensive connotation making it brand-unsafe
  - So generic it adds no value (but err on the side of accepting)
  - Clearly noise/non-word tokens

BORDERLINE: words where the case is genuinely 50/50.
Remember: recall is more important than precision at this stage.
""",
]

CHALLENGE_REVIEWER_PROMPTS = [
    # Challenger 01 — Recall champion: argues for keeping borderline/rejected words
    """\
You are challenge-reviewer-01, a recall guardian.
Your job: find words in the primary results that were INCORRECTLY REJECTED
(false negatives). Argue for keeping words that have any SaaS title potential.

Focus on:
- Words marked "reject" that could be brand names or feature names
- Words marked "borderline" that should clearly be "accept"
- Cases where judges may have been too conservative
""",

    # Challenger 02 — Noise detector: argues against noise that slipped through
    """\
You are challenge-reviewer-02, a noise detector.
Your job: find words in the primary results that were INCORRECTLY ACCEPTED
(false positives). Focus on tokens that are actually noise disguised as words.

Focus on:
- Accepted tokens that are actually wiki artifacts, code fragments, or meta-tokens
- Tokens with suspicious patterns that judges missed
- Tokens that look like words but have no plausible SaaS use
""",

    # Challenger 03 — Brand skeptic
    """\
You are challenge-reviewer-03, a brand quality guardian.
Your job: identify words that may have been accepted/rejected incorrectly
from a pure brand-quality perspective.

Challenge:
- Over-rejections: obscure but genuinely brandable words
- Over-acceptances: words with serious brand liabilities (offensive, confusing,
  already saturated as brand names)
""",

    # Challenger 04 — Functional verifier
    """\
You are challenge-reviewer-04, a functional-word specialist.
Your job: ensure functional SaaS verbs and tech nouns are correctly handled.

Challenge:
- Over-rejections: technical terms that clearly name SaaS features/tools
- Over-acceptances: claimed "functional" words that have no real tech meaning
""",

    # Challenger 05 — Borderline arbitrator
    """\
You are challenge-reviewer-05, a borderline arbitrator.
Your job: review all "borderline" decisions and determine which way they should go.

For each borderline word:
- If it should clearly be "accept": challenge as over-cautious
- If it should clearly be "reject": challenge as over-generous
- If it's genuinely borderline: leave it alone (don't challenge)
""",
]

REBUTTAL_REVIEWER_PROMPTS = [
    # Rebuttal 01 — Recall defender
    """\
You are rebuttal-reviewer-01, a recall defender.
Your job: review challenges and determine which ones are valid.

For challenges arguing FOR rejection (over-accept challenges):
  Be skeptical. Uphold "recall over precision". Dismiss challenges unless
  the evidence is very compelling (the word is clearly noise or brand-toxic).

For challenges arguing FOR acceptance (over-reject challenges):
  Accept these challenges readily. Err on the side of preserving words.
""",

    # Rebuttal 02 — Noise defender
    """\
You are rebuttal-reviewer-02, a noise quality defender.
Your job: review challenges and protect output quality.

For challenges arguing FOR rejection (over-accept challenges):
  Accept valid noise-detection challenges. Remove genuinely noisy tokens.

For challenges arguing FOR acceptance (over-reject challenges):
  Be skeptical about accepting noise. Maintain rejection if the evidence
  for being noise is strong.
""",

    # Rebuttal 03 — Synthesizer / balanced arbiter
    """\
You are rebuttal-reviewer-03, a balanced arbiter.
Your job: review all challenges and rebuttals and make a final synthesized recommendation.

Balance recall (keep useful words) against precision (remove noise).
For unclear cases, recommend "borderline" (which maps to accept with risk flag
in the final pipeline).
""",
]

CONSENSUS_CHIEF_PROMPT = """\
You are consensus-chief, the final arbiter in the SaaS word extraction pipeline.
You receive the aggregated vote tallies for each word and make the final decision.

Your goals:
1. Maximise recall — borderline cases should lean toward accept.
2. Remove genuine noise — clear noise/non-words should be rejected.
3. Flag risky accepts — accepted words with meaningful opposition get a risk flag.

Decision rules:
- vote_ratio = accept_votes / (accept_votes + reject_votes), ignoring abstentions
- vote_ratio >= 0.50 → "accept" (add "accept_with_risk" risk_flag if ratio < 0.70)
- 0.35 <= vote_ratio < 0.50 → "borderline" (treated as accept_with_risk)
- vote_ratio < 0.35 → "reject"

For each word, return your final label (functional/brandable/ambiguous) and
brief why_accept or reject_reason list.
"""


# ============================================================
# AIReviewer class
# ============================================================

class AIReviewer:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it before running the pipeline."
            )
        self.client = anthropic.Anthropic(api_key=api_key)

    # ----------------------------------------------------------
    # Low-level API call with retry
    # ----------------------------------------------------------

    def _call(self, system: str, user: str, agent_id: str) -> dict:
        """Make one API call; return parsed JSON response dict."""

        def _attempt():
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=MAX_RESPONSE_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = response.content[0].text
            return extract_json(text)

        return with_retry(
            _attempt,
            attempts=API_RETRY_ATTEMPTS,
            base_delay=API_RETRY_BASE_DELAY,
            logger=log,
        )

    # ----------------------------------------------------------
    # Step 5 — Primary review (5 judges)
    # ----------------------------------------------------------

    def run_primary_review(
        self, screened_records: list[dict], resume: bool = False
    ) -> list[dict]:
        if resume and INTER_PRIMARY.exists():
            log.info("Resuming primary review from %s", INTER_PRIMARY)
            return read_jsonl(INTER_PRIMARY)

        if INTER_PRIMARY.exists():
            INTER_PRIMARY.unlink()

        # Deduplicate by normalized_word for AI processing (then re-attach)
        word_to_records: dict[str, list[dict]] = {}
        for rec in screened_records:
            w = rec.get("normalized_word", "")
            word_to_records.setdefault(w, []).append(rec)

        unique_words = list(word_to_records.keys())
        log.info("Primary review: %d unique words across %d judges",
                 len(unique_words), PRIMARY_JUDGE_COUNT)

        # word → list of per-judge verdicts
        word_judgments: dict[str, list[dict]] = {w: [] for w in unique_words}

        for judge_idx, system_prompt in enumerate(PRIMARY_JUDGE_PROMPTS, start=1):
            judge_id = f"saas-title-judge-{judge_idx:02d}"
            log.info("Running %s …", judge_id)

            for batch_num, batch in enumerate(batched(unique_words, AI_BATCH_SIZE), start=1):
                word_list = "\n".join(f"{i+1}. {w}" for i, w in enumerate(batch))
                user_msg = (
                    f"Evaluate these {len(batch)} words for SaaS title suitability.\n"
                    f"Return ONLY valid JSON, no explanation outside JSON.\n\n"
                    f"Words:\n{word_list}\n\n"
                    f"Response format:\n"
                    f'{{"judgments": [{{"word": "...", "decision": "accept|reject|borderline", '
                    f'"label": "functional|brandable|ambiguous|null", '
                    f'"confidence": 0.0, "why": ["reason"]}}]}}'
                )

                try:
                    result = self._call(system_prompt, user_msg, judge_id)
                    judgments = result.get("judgments", [])
                except Exception as exc:
                    log.error("%s batch %d failed: %s — using default borderline",
                              judge_id, batch_num, exc)
                    judgments = [
                        {"word": w, "decision": "borderline", "label": "ambiguous",
                         "confidence": 0.5, "why": ["agent_error"]}
                        for w in batch
                    ]

                # Map judgments back to words (by position or by word field)
                judgment_map = {j.get("word", ""): j for j in judgments}
                for w in batch:
                    verdict = judgment_map.get(w)
                    if verdict is None:
                        # Judge skipped this word — use borderline fallback
                        verdict = {
                            "word": w, "decision": "borderline", "label": "ambiguous",
                            "confidence": 0.5, "why": ["no_response_from_judge"],
                        }
                    verdict["judge_id"] = judge_id
                    word_judgments[w].append(verdict)

        # Build output records (one per original screened record)
        results = []
        for rec in screened_records:
            w = rec.get("normalized_word", "")
            primary_votes = word_judgments.get(w, [])
            accept_n = sum(1 for v in primary_votes if v.get("decision") == "accept")
            reject_n = sum(1 for v in primary_votes if v.get("decision") == "reject")
            border_n = sum(1 for v in primary_votes if v.get("decision") == "borderline")

            updated = {
                **rec,
                "primary_votes": primary_votes,
                "primary_summary": {
                    "accept": accept_n,
                    "reject": reject_n,
                    "borderline": border_n,
                },
                "status": "AI_PRIMARY_REVIEWED",
            }
            append_jsonl(INTER_PRIMARY, updated)
            results.append(updated)

        log.info("Primary review complete → %s", INTER_PRIMARY)
        return results

    # ----------------------------------------------------------
    # Step 6 — Challenge review (5 challengers)
    # ----------------------------------------------------------

    def run_challenge_review(
        self, primary_results: list[dict], resume: bool = False
    ) -> list[dict]:
        if resume and INTER_CHALLENGED.exists():
            log.info("Resuming challenge review from %s", INTER_CHALLENGED)
            return read_jsonl(INTER_CHALLENGED)

        if INTER_CHALLENGED.exists():
            INTER_CHALLENGED.unlink()

        # Deduplicate for AI processing
        seen: dict[str, dict] = {}
        for rec in primary_results:
            w = rec.get("normalized_word", "")
            if w not in seen:
                seen[w] = rec

        unique_words = list(seen.keys())
        log.info("Challenge review: %d unique words across %d challengers",
                 len(unique_words), CHALLENGE_REVIEWER_COUNT)

        # word → list of challenges from all reviewers
        word_challenges: dict[str, list[dict]] = {w: [] for w in unique_words}

        for rev_idx, system_prompt in enumerate(CHALLENGE_REVIEWER_PROMPTS, start=1):
            reviewer_id = f"challenge-reviewer-{rev_idx:02d}"
            log.info("Running %s …", reviewer_id)

            for batch in batched(unique_words, AI_BATCH_SIZE):
                # Build compact primary summary for this batch
                batch_summaries = []
                for w in batch:
                    rec = seen[w]
                    ps = rec.get("primary_summary", {})
                    batch_summaries.append(
                        f"{w}: accept={ps.get('accept',0)} "
                        f"reject={ps.get('reject',0)} "
                        f"borderline={ps.get('borderline',0)}"
                    )
                summary_text = "\n".join(batch_summaries)

                user_msg = (
                    f"Review these primary judgments for words that may need reconsideration.\n"
                    f"Return ONLY valid JSON. Only include words you have a challenge for.\n\n"
                    f"Primary results (word: accept/reject/borderline vote counts):\n"
                    f"{summary_text}\n\n"
                    f"Response format:\n"
                    f'{{"challenges": [{{"word": "...", '
                    f'"original_lean": "accept|reject|borderline", '
                    f'"challenge_type": "over_accept|over_reject|borderline_clarify", '
                    f'"argument": "...", '
                    f'"suggested_decision": "accept|reject|borderline", '
                    f'"suggested_label": "functional|brandable|ambiguous|null"}}]}}'
                )

                try:
                    result = self._call(system_prompt, user_msg, reviewer_id)
                    challenges = result.get("challenges", [])
                except Exception as exc:
                    log.error("%s batch failed: %s — skipping batch challenges", reviewer_id, exc)
                    challenges = []

                for ch in challenges:
                    w = ch.get("word", "")
                    if w in word_challenges:
                        ch["reviewer_id"] = reviewer_id
                        word_challenges[w].append(ch)

        # Attach challenges to records
        results = []
        for rec in primary_results:
            w = rec.get("normalized_word", "")
            challenges = word_challenges.get(w, [])
            updated = {
                **rec,
                "challenges": challenges,
                "challenge_summary": {
                    "over_accept": sum(1 for c in challenges if c.get("challenge_type") == "over_accept"),
                    "over_reject": sum(1 for c in challenges if c.get("challenge_type") == "over_reject"),
                    "borderline_clarify": sum(1 for c in challenges if c.get("challenge_type") == "borderline_clarify"),
                },
                "status": "AI_CHALLENGED",
            }
            append_jsonl(INTER_CHALLENGED, updated)
            results.append(updated)

        log.info("Challenge review complete → %s", INTER_CHALLENGED)
        return results

    # ----------------------------------------------------------
    # Step 7 — Rebuttal review (3 rebuttal reviewers)
    # ----------------------------------------------------------

    def run_rebuttal_review(
        self, challenged_results: list[dict], resume: bool = False
    ) -> list[dict]:
        if resume and INTER_REBUTTED.exists():
            log.info("Resuming rebuttal review from %s", INTER_REBUTTED)
            return read_jsonl(INTER_REBUTTED)

        if INTER_REBUTTED.exists():
            INTER_REBUTTED.unlink()

        # Only process words that actually have challenges
        words_with_challenges = [
            r for r in challenged_results
            if r.get("challenges")
        ]
        # Deduplicate
        seen: dict[str, dict] = {}
        for rec in words_with_challenges:
            w = rec.get("normalized_word", "")
            if w not in seen:
                seen[w] = rec

        unique_contested = list(seen.keys())
        log.info("Rebuttal review: %d contested words across %d rebuttal reviewers",
                 len(unique_contested), REBUTTAL_REVIEWER_COUNT)

        word_rebuttals: dict[str, list[dict]] = {w: [] for w in unique_contested}

        for rev_idx, system_prompt in enumerate(REBUTTAL_REVIEWER_PROMPTS, start=1):
            reviewer_id = f"rebuttal-reviewer-{rev_idx:02d}"
            log.info("Running %s …", reviewer_id)

            for batch in batched(unique_contested, AI_BATCH_SIZE):
                batch_info = []
                for w in batch:
                    rec = seen[w]
                    ps = rec.get("primary_summary", {})
                    chs = rec.get("challenges", [])
                    ch_texts = "; ".join(
                        f"{c.get('challenge_type','?')}({c.get('reviewer_id','?')}): {c.get('argument','')[:80]}"
                        for c in chs
                    )
                    batch_info.append(
                        f"Word: {w} | Primary: accept={ps.get('accept',0)} reject={ps.get('reject',0)} "
                        f"borderline={ps.get('borderline',0)} | Challenges: {ch_texts}"
                    )
                info_text = "\n".join(batch_info)

                user_msg = (
                    f"Evaluate these challenges to primary judgments.\n"
                    f"Return ONLY valid JSON. Only include words where you have a rebuttal.\n\n"
                    f"Contested words:\n{info_text}\n\n"
                    f"Response format:\n"
                    f'{{"rebuttals": [{{"word": "...", '
                    f'"challenge_valid": true|false, '
                    f'"reasoning": "...", '
                    f'"recommended_final": "accept|reject|borderline"}}]}}'
                )

                try:
                    result = self._call(system_prompt, user_msg, reviewer_id)
                    rebuttals = result.get("rebuttals", [])
                except Exception as exc:
                    log.error("%s batch failed: %s — skipping", reviewer_id, exc)
                    rebuttals = []

                for rb in rebuttals:
                    w = rb.get("word", "")
                    if w in word_rebuttals:
                        rb["reviewer_id"] = reviewer_id
                        word_rebuttals[w].append(rb)

        results = []
        for rec in challenged_results:
            w = rec.get("normalized_word", "")
            rebuttals = word_rebuttals.get(w, [])
            updated = {
                **rec,
                "rebuttals": rebuttals,
                "status": "AI_REBUTTED",
            }
            append_jsonl(INTER_REBUTTED, updated)
            results.append(updated)

        log.info("Rebuttal review complete → %s", INTER_REBUTTED)
        return results

    # ----------------------------------------------------------
    # Step 8 — Consensus engine (vote aggregation + LLM consensus-chief)
    # ----------------------------------------------------------

    def run_consensus(
        self, rebutted_results: list[dict], resume: bool = False
    ) -> list[dict]:
        if resume and INTER_CONSENSUS.exists():
            log.info("Resuming consensus from %s", INTER_CONSENSUS)
            return read_jsonl(INTER_CONSENSUS)

        if INTER_CONSENSUS.exists():
            INTER_CONSENSUS.unlink()

        # ------ vote aggregation (script side) ------
        aggregated = _aggregate_votes(rebutted_results)

        # ------ LLM consensus-chief for contested cases ------
        # Only send words where vote_ratio is close to a boundary (0.3–0.7)
        contested = [a for a in aggregated if 0.30 <= a["vote_ratio"] <= 0.70]
        log.info("Consensus: %d total, %d contested → sending to consensus-chief",
                 len(aggregated), len(contested))

        chief_overrides: dict[str, dict] = {}
        if contested:
            unique_contested = {}
            for a in contested:
                w = a["normalized_word"]
                if w not in unique_contested:
                    unique_contested[w] = a

            for batch in batched(list(unique_contested.keys()), AI_BATCH_SIZE):
                batch_info = []
                for w in batch:
                    a = unique_contested[w]
                    batch_info.append(
                        f"word={w} accept_votes={a['accept_votes']} "
                        f"reject_votes={a['reject_votes']} "
                        f"vote_ratio={a['vote_ratio']:.2f}"
                    )
                info_text = "\n".join(batch_info)

                user_msg = (
                    f"Make final accept/reject/borderline decisions for these contested words.\n"
                    f"Return ONLY valid JSON.\n\n"
                    f"Words with vote tallies:\n{info_text}\n\n"
                    f"Response format:\n"
                    f'{{"decisions": [{{"word": "...", '
                    f'"final_decision": "accept|reject|borderline", '
                    f'"label": "functional|brandable|ambiguous|null", '
                    f'"why": ["reason1"]}}]}}'
                )

                try:
                    result = self._call(CONSENSUS_CHIEF_PROMPT, user_msg, "consensus-chief")
                    decisions = result.get("decisions", [])
                    for d in decisions:
                        w = d.get("word", "")
                        if w:
                            chief_overrides[w] = d
                except Exception as exc:
                    log.error("consensus-chief batch failed: %s — using vote-based decision", exc)

        # ------ Build final consensus records ------
        results = []
        # Group by normalized_word to avoid per-source-line duplication
        # (multiple source lines can share the same normalized word)
        seen_words: dict[str, dict] = {}

        for agg in aggregated:
            w = agg["normalized_word"]
            override = chief_overrides.get(w)

            if override:
                final_decision = override.get("final_decision", agg["base_decision"])
                label = override.get("label", agg.get("primary_label"))
                why_accept = override.get("why", agg.get("why_accept_hints", []))
            else:
                final_decision = agg["base_decision"]
                label = agg.get("primary_label")
                why_accept = agg.get("why_accept_hints", [])

            # Normalise borderline → accept_with_risk (recall principle)
            risk_flags = list(agg.get("risk_flags", []))
            if final_decision == "borderline":
                final_decision = "accept"
                if "borderline_promoted" not in risk_flags:
                    risk_flags.append("borderline_promoted")

            # Low-confidence accept gets a risk flag
            if final_decision == "accept" and agg["vote_ratio"] < RISK_FLAG_THRESHOLD:
                if "low_consensus" not in risk_flags:
                    risk_flags.append("low_consensus")

            consensus_record = {
                **agg["source_record"],
                "decision": final_decision,
                "primary_label": label,
                "candidate_modes": [label] if label else [],
                "confidence": round(agg["vote_ratio"], 3),
                "consensus": {
                    "support": agg["accept_votes"],
                    "oppose": agg["reject_votes"],
                    "abstain": agg["abstain_votes"],
                },
                "why_accept": why_accept if final_decision == "accept" else [],
                "reject_reason": agg.get("reject_reason_hints", []) if final_decision == "reject" else [],
                "risk_flags": risk_flags,
                "chief_override": override is not None,
                "status": "CONSENSUS_DECIDED",
            }
            append_jsonl(INTER_CONSENSUS, consensus_record)
            results.append(consensus_record)

        accept_n = sum(1 for r in results if r["decision"] == "accept")
        reject_n = sum(1 for r in results if r["decision"] == "reject")
        log.info("Consensus complete: %d accept, %d reject → %s",
                 accept_n, reject_n, INTER_CONSENSUS)
        return results


# ============================================================
# Vote aggregation helper (pure script logic)
# ============================================================

def _aggregate_votes(rebutted_results: list[dict]) -> list[dict]:
    """
    For each record, count effective votes from all three review stages
    and compute a vote_ratio = accept_votes / (accept + reject).
    Returns one aggregation dict per record.
    """
    aggregated = []

    for rec in rebutted_results:
        accept_v = 0
        reject_v = 0
        abstain_v = 0
        why_accept_hints: list[str] = []
        reject_reason_hints: list[str] = []
        risk_flags: list[str] = []

        # --- Primary votes ---
        for vote in rec.get("primary_votes", []):
            d = vote.get("decision", "borderline")
            if d == "accept":
                accept_v += 1
                why_accept_hints.extend(vote.get("why", [])[:2])
            elif d == "reject":
                reject_v += 1
                reject_reason_hints.extend(vote.get("why", [])[:2])
            else:
                # borderline counts as 0.5 each
                accept_v += 0.5
                reject_v += 0.5
                abstain_v += 1

        # --- Challenges (each challenger casts an effective half-vote) ---
        for ch in rec.get("challenges", []):
            ct = ch.get("challenge_type", "")
            sd = ch.get("suggested_decision", "")
            if ct == "over_reject" or sd == "accept":
                accept_v += 0.5
            elif ct == "over_accept" or sd == "reject":
                reject_v += 0.5
            else:
                abstain_v += 1

        # --- Rebuttals (each rebuttal casts a half-vote for the recommendation) ---
        for rb in rec.get("rebuttals", []):
            rf = rb.get("recommended_final", "borderline")
            valid = rb.get("challenge_valid", False)
            if rf == "accept":
                accept_v += 0.5
            elif rf == "reject":
                reject_v += 0.5
            else:
                abstain_v += 1

        total_decisive = accept_v + reject_v
        if total_decisive == 0:
            vote_ratio = 0.5  # no decisive votes → borderline
            abstain_v += 1
        else:
            vote_ratio = accept_v / total_decisive

        # Determine base decision
        if vote_ratio >= ACCEPT_SCORE_THRESHOLD:
            base_decision = "accept"
        elif vote_ratio >= BORDERLINE_SCORE_THRESHOLD:
            base_decision = "borderline"
        else:
            base_decision = "reject"

        # Choose primary label from plurality of accept votes
        label_counts: dict[str, int] = {}
        for vote in rec.get("primary_votes", []):
            lb = vote.get("label")
            if lb and vote.get("decision") in ("accept", "borderline"):
                label_counts[lb] = label_counts.get(lb, 0) + 1
        primary_label = max(label_counts, key=label_counts.get) if label_counts else "ambiguous"

        aggregated.append({
            "normalized_word": rec.get("normalized_word", ""),
            "source_record": rec,
            "accept_votes": round(accept_v, 2),
            "reject_votes": round(reject_v, 2),
            "abstain_votes": round(abstain_v, 2),
            "vote_ratio": round(vote_ratio, 4),
            "base_decision": base_decision,
            "primary_label": primary_label,
            "why_accept_hints": list(dict.fromkeys(why_accept_hints))[:5],
            "reject_reason_hints": list(dict.fromkeys(reject_reason_hints))[:5],
            "risk_flags": risk_flags,
        })

    return aggregated
