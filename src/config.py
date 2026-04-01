"""
Pipeline configuration — all constants and tunable parameters in one place.
Environment variables override defaults where noted.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
INTERMEDIATE_DIR = OUTPUT_DIR / "intermediate"
HUMAN_REVIEW_DIR = OUTPUT_DIR / "human_review"
QA_DIR = OUTPUT_DIR / "qa"

# Intermediate file names (step-numbered for clarity)
INTER_DISCOVERED = INTERMEDIATE_DIR / "01_discovered_files.json"
INTER_LOADED = INTERMEDIATE_DIR / "02_loaded_tokens.jsonl"
INTER_NORMALIZED = INTERMEDIATE_DIR / "03_normalized_tokens.jsonl"
INTER_SCREENED = INTERMEDIATE_DIR / "04_screened_tokens.jsonl"
INTER_PRIMARY = INTERMEDIATE_DIR / "05_primary_reviewed.jsonl"
INTER_CHALLENGED = INTERMEDIATE_DIR / "06_challenged.jsonl"
INTER_REBUTTED = INTERMEDIATE_DIR / "07_rebutted.jsonl"
INTER_CONSENSUS = INTERMEDIATE_DIR / "08_consensus.jsonl"

# Final output files
OUT_SAAS_WORDS = OUTPUT_DIR / "saas_words.jsonl"
OUT_REJECTED_WORDS = OUTPUT_DIR / "rejected_words.jsonl"
OUT_RUN_SUMMARY = OUTPUT_DIR / "run_summary.json"
OUT_SAAS_REVIEW_XLSX = HUMAN_REVIEW_DIR / "saas_words_review.xlsx"
OUT_SAAS_REVIEW_CSV = HUMAN_REVIEW_DIR / "saas_words_review.csv"
OUT_REJECTED_REVIEW_XLSX = HUMAN_REVIEW_DIR / "rejected_words_review.xlsx"
OUT_QA_REPORT = QA_DIR / "qa_report.json"
OUT_QA_FINDINGS = QA_DIR / "qa_findings.jsonl"
OUT_QA_DISAGREEMENTS = QA_DIR / "qa_disagreements.jsonl"
OUT_QA_HUMAN_REVIEW_XLSX = QA_DIR / "qa_human_review.xlsx"

# ---------------------------------------------------------------------------
# Pipeline version
# ---------------------------------------------------------------------------
PIPELINE_VERSION = "v1"

# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_RESPONSE_TOKENS = 8192
API_RETRY_ATTEMPTS = 3
API_RETRY_BASE_DELAY = 2.0  # seconds; doubles each retry

# ---------------------------------------------------------------------------
# AI agent counts (design requirement: do not reduce without design approval)
# ---------------------------------------------------------------------------
PRIMARY_JUDGE_COUNT = 5
CHALLENGE_REVIEWER_COUNT = 5
REBUTTAL_REVIEWER_COUNT = 3

# Number of words fed to each AI agent call at once
AI_BATCH_SIZE = int(os.environ.get("AI_BATCH_SIZE", "50"))

# ---------------------------------------------------------------------------
# Rule screener thresholds
# ---------------------------------------------------------------------------
MIN_WORD_LENGTH = 2       # chars after normalization
MAX_WORD_LENGTH = 30      # chars after normalization
MIN_ALPHA_RATIO = 0.5     # minimum fraction of alphabetic characters

# ---------------------------------------------------------------------------
# Consensus thresholds
# ---------------------------------------------------------------------------
# vote_score = accept_votes / total_effective_votes
ACCEPT_SCORE_THRESHOLD = 0.50    # >= this → accept (or accept_with_risk)
BORDERLINE_SCORE_THRESHOLD = 0.35  # >= this → borderline; < this → reject
RISK_FLAG_THRESHOLD = 0.70        # < this (but accepted) → add risk flag
