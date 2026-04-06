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
# AI agent counts (optimized for 24h processing)
# ---------------------------------------------------------------------------
PRIMARY_JUDGE_COUNT = 3  # Reduced from 5 (keep: Recall, Function, Balanced)
CHALLENGE_REVIEWER_COUNT = 2  # Reduced from 5 (keep: Recall Guardian, Noise Detector)
REBUTTAL_REVIEWER_COUNT = 1  # Reduced from 3 (keep: Balance Arbitrator)

# Number of words fed to each AI agent call at once
AI_BATCH_SIZE = int(os.environ.get("AI_BATCH_SIZE", "200"))  # Increased from 100 to 200

# ---------------------------------------------------------------------------
# Parallel processing configuration
# ---------------------------------------------------------------------------
PARALLEL_WORKERS = int(os.environ.get("PARALLEL_WORKERS", "4"))  # Number of parallel workers
PARALLEL_ENABLED = os.environ.get("PARALLEL_ENABLED", "true").lower() == "true"  # Enable/disable parallel processing

# ---------------------------------------------------------------------------
# Batch processing configuration
# ---------------------------------------------------------------------------
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100000"))  # 100K words per batch
PROGRESS_DIR = OUTPUT_DIR / "progress"  # Progress tracking directory

# ---------------------------------------------------------------------------
# Rule screener thresholds
# ---------------------------------------------------------------------------
MIN_WORD_LENGTH = 2       # chars after normalization
MAX_WORD_LENGTH = 30      # chars after normalization
MIN_ALPHA_RATIO = 0.5     # minimum fraction of alphabetic characters

# ---------------------------------------------------------------------------
# Consensus thresholds (optimized for 3-judge system)
# ---------------------------------------------------------------------------
# vote_score = accept_votes / total_effective_votes
ACCEPT_SCORE_THRESHOLD = 0.67    # >= 2/3 → accept (increased from 0.50)
BORDERLINE_SCORE_THRESHOLD = 0.50  # >= 1.5/3 → borderline (increased from 0.35)
RISK_FLAG_THRESHOLD = 0.67        # < 2/3 but accepted → add risk flag (decreased from 0.70)
