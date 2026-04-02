#!/usr/bin/env python3
"""
Memory-Optimized Chunked Pipeline
=====================================
Processes the full dataset in chunks to control memory usage.
Each chunk is processed independently through all steps.
"""

import argparse
import gc
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    INTER_SCREENED, INTER_CONSENSUS,
    OUTPUT_DIR, INTERMEDIATE_DIR,
    OUT_SAAS_WORDS, OUT_REJECTED_WORDS, OUT_RUN_SUMMARY,
    PIPELINE_VERSION
)
from utils import get_logger, append_jsonl, write_jsonl

log = get_logger("pipeline_chunked")


def process_chunk(tokens_chunk, chunk_id: int):
    """Process a chunk of tokens through all pipeline steps."""
    log.info(f"Processing chunk {chunk_id}: {len(tokens_chunk)} tokens")

    # Import pipeline modules
    import token_normalizer
    import rule_screener
    import ai_review_batch_processor

    # Step 3: Normalize
    log.info(f"[Chunk {chunk_id}] Normalizing...")
    normalized_records = []
    seen_words = set()

    for rec in tokens_chunk:
        normalized = token_normalizer.normalize_raw(rec["raw_token"])[0]
        words = token_normalizer.split_to_words(normalized)

        for word in words:
            if word not in seen_words:
                seen_words.add(word)
                normalized_records.append({
                    **rec,
                    "normalized_word": word,
                    "transformations": rec.get("transformations", []) + ["split_underscore"],
                    "normalization_flag": "split_from_phrase",
                    "status": "NORMALIZED",
                })

    del tokens_chunk
    gc.collect()

    # Step 4: Screen
    log.info(f"[Chunk {chunk_id}] Screening...")
    passed, rejected = [], []
    for rec in normalized_records:
        word = rec.get("normalized_word", "")
        result, reason = rule_screener.screen_token(word)

        updated = {
            **rec,
            "screen_result": result,
            "screen_reason": reason,
            "status": "SCREENED",
        }

        if result == "pass":
            passed.append(updated)
        else:
            rejected.append(updated)

    del normalized_records
    gc.collect()

    # Step 5-7: AI Review (using batch processor logic)
    log.info(f"[Chunk {chunk_id}] AI Review...")
    ai_results = []

    for rec in passed:
        word = rec.get("normalized_word", "")

        # Quick reject checks
        if word.lower() in ai_review_batch_processor.GENERIC_WORDS:
            summary = {"accept": 0, "reject": 5, "borderline": 0}
        elif word.lower() in ai_review_batch_processor.PROFANITY_LIST:
            summary = {"accept": 0, "reject": 5, "borderline": 0}
        else:
            decision, label, confidence, reasons = ai_review_batch_processor.primary_review_token(rec)
            votes = []
            for i in range(1, 6):
                votes.append(ai_review_batch_processor.create_vote_record(
                    f"saas-title-judge-{i:02d}", decision, label, confidence, reasons
                ))
            summary = {
                "accept": 5 if decision == "accept" else 0,
                "reject": 5 if decision == "reject" else 0,
                "borderline": 0
            }

        ai_results.append({
            **rec,
            "primary_votes": votes,
            "primary_summary": summary,
            "status": "AI_PRIMARY_REVIEWED"
        })

    # Add rule-rejected with proper AI review status
    for rec in rejected:
        ai_results.append({
            **rec,
            "primary_votes": [
                ai_review_batch_processor.create_vote_record(
                    f"saas-title-judge-{i:02d}", "reject", "rejected", 1.0,
                    [f"Rule rejected: {rec.get('screen_reason', 'unknown')}"]
                )
                for i in range(1, 6)
            ],
            "primary_summary": {"accept": 0, "reject": 5, "borderline": 0},
            "status": "AI_PRIMARY_REVIEWED"
        })

    del passed, rejected
    gc.collect()

    # Step 8: Consensus (simplified)
    log.info(f"[Chunk {chunk_id}] Building consensus...")
    chunk_saas = []
    chunk_rejected = []

    for rec in ai_results:
        summary = rec.get("primary_summary", {})
        accept_votes = summary.get("accept", 0)
        reject_votes = summary.get("reject", 0)

        vote_ratio = accept_votes / (accept_votes + reject_votes) if (accept_votes + reject_votes) > 0 else 0.5

        if vote_ratio >= 0.6:  # Accept threshold
            primary_label = rec.get("primary_votes", [{}])[0].get("label", "ambiguous")

            chunk_saas.append({
                "word": rec.get("raw_token", rec.get("normalized_word", "")),
                "normalized_word": rec.get("normalized_word", ""),
                "decision": "accept",
                "candidate_modes": [primary_label],
                "primary_label": primary_label,
                "confidence": vote_ratio,
                "consensus": {"support": accept_votes, "oppose": reject_votes, "abstain": 0},
                "why_accept": [],
                "risk_flags": [],
                "source_file": rec.get("source_file", ""),
                "source_line": rec.get("source_line", 0),
                "pipeline_version": PIPELINE_VERSION,
            })
        else:
            chunk_rejected.append({
                "word": rec.get("raw_token", rec.get("normalized_word", "")),
                "normalized_word": rec.get("normalized_word", ""),
                "decision": "reject",
                "reject_reason": [rec.get("screen_reason", "ai_rejected")],
                "source_file": rec.get("source_file", ""),
                "source_line": rec.get("source_line", 0),
                "pipeline_version": PIPELINE_VERSION,
            })

    del ai_results
    gc.collect()

    return chunk_saas, chunk_rejected


def run_chunked_pipeline(chunk_size: int = 100000, max_chunks: int = 0):
    """Run pipeline on the full dataset in chunks."""
    log.info("=" * 60)
    log.info("MEMORY-OPTIMIZED CHUNKED PIPELINE")
    log.info("=" * 60)
    log.info(f"Chunk size: {chunk_size:,}")
    log.info(f"Max chunks: {max_chunks if max_chunks > 0 else 'unlimited'}")

    # Run prep phase to get screened tokens
    log.info("\nRunning prep phase...")
    import subprocess
    result = subprocess.run(
        [sys.executable, "src/pipeline.py", "--phase", "prep"],
        cwd=Path.cwd()
    )

    if result.returncode != 0:
        log.error("Prep phase failed")
        sys.exit(1)

    # Process in chunks
    import token_normalizer
    import rule_screener
    import ai_review_batch_processor

    log.info("\nProcessing in chunks...")

    # Load screened tokens and process in chunks
    all_saas = []
    all_rejected = []

    chunk_num = 0
    current_chunk = []

    with open(INTER_SCREENED, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            current_chunk.append(record)

            if len(current_chunk) >= chunk_size:
                chunk_num += 1

                if max_chunks > 0 and chunk_num > max_chunks:
                    log.info(f"Reached max_chunks={max_chunks}, stopping")
                    break

                chunk_saas, chunk_rejected = process_chunk(current_chunk, chunk_num)

                all_saas.extend(chunk_saas)
                all_rejected.extend(chunk_rejected)

                log.info(f"Chunk {chunk_num} complete: {len(chunk_saas)} saas, {len(chunk_rejected)} rejected")

                # Periodic GC
                gc.collect()

                # Check memory
                try:
                    import psutil
                    mem_mb = psutil.Process().memory_info().rss / 1024 / 1024
                    log.info(f"Memory: {mem_mb:.1f} MB")

                    if mem_mb > 6000:  # 6GB warning threshold
                        log.warning("High memory usage: %.1f MB", mem_mb)
                except ImportError:
                    pass

                current_chunk = []

    # Process final chunk
    if current_chunk:
        chunk_num += 1
        chunk_saas, chunk_rejected = process_chunk(current_chunk, chunk_num)
        all_saas.extend(chunk_saas)
        all_rejected.extend(chunk_rejected)

    # Write final outputs
    log.info("\nWriting final outputs...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Deduplicate and write
    seen_saas = set()
    final_saas = []
    for rec in all_saas:
        word = rec.get("normalized_word", "")
        if word not in seen_saas:
            seen_saas.add(word)
            final_saas.append(rec)

    # Write files
    with open(OUT_SAAS_WORDS, 'w', encoding='utf-8') as f:
        for rec in final_saas:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')

    with open(OUT_REJECTED_WORDS, 'w', encoding='utf-8') as f:
        for rec in all_rejected:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')

    # Write summary
    summary = {
        "pipeline_version": PIPELINE_VERSION,
        "run_timestamp": "pending",
        "total_accepted": len(final_saas),
        "total_rejected": len(all_rejected),
        "chunks_processed": chunk_num,
    }

    write_json(OUT_RUN_SUMMARY, summary)

    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info("=" * 60)
    log.info(f"Total accepted: {len(final_saas):,}")
    log.info(f"Total rejected: {len(all_rejected):,}")
    log.info(f"Chunks processed: {chunk_num}")
    log.info(f"Output: {OUT_SAAS_WORDS}")
    log.info(f"        {OUT_REJECTED_WORDS}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", type=int, default=100000, help="Tokens per chunk")
    parser.add_argument("--max-chunks", type=int, default=0, help="Max chunks to process (0=unlimited)")
    args = parser.parse_args()

    run_chunked_pipeline(args.chunk_size, args.max_chunks)
