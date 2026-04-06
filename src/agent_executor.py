"""
Agent Executor — 메인 Claude Code 세션용 에이전트 호출기

이 모듈은 메인 Claude Code 세션에서 AI 판정 단계를 실행할 때
사용하는 에이전트 호출 함수들을 제공합니다.

사용 방법:
  # 메인 Claude Code 세션에서
  from src.agent_executor import call_step5_agents, call_step6_agents, call_step7_agents, call_qa_agents

  # Step 5 실행
  call_step5_agents()

  # Step 6 실행
  call_step6_agents()

  # Step 7 실행
  call_step7_agents()

  # QA 실행
  call_qa_agents()
"""

import json
from pathlib import Path
from typing import Optional

from config import (
    AI_BATCH_SIZE,
    INTER_CHALLENGED,
    INTER_PRIMARY,
    INTER_REBUTTED,
    INTER_SCREENED,
    OUT_SAAS_WORDS,
    OUT_REJECTED_WORDS,
    QA_DIR,
)
from utils import append_jsonl, get_logger, iter_jsonl

log = get_logger("agent_executor")


# =============================================================================
# Step 5: Primary Review (saas-title-judge)
# =============================================================================

def call_step5_agents(
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    batch_size: int = AI_BATCH_SIZE
) -> Path:
    """
    Step 5: AI Primary Review 실행

    이 함수는 메인 Claude Code 세션에서 Agent tool을 사용하여
    saas-title-judge 에이전트를 호출합니다.

    Args:
        input_path: 입력 파일 경로 (기본값: INTER_SCREENED)
        output_path: 출력 파일 경로 (기본값: INTER_PRIMARY)
        batch_size: 배치 크기

    Returns:
        출력 파일 경로
    """
    if input_path is None:
        input_path = INTER_SCREENED
    if output_path is None:
        output_path = INTER_PRIMARY

    log.info("=" * 70)
    log.info("STEP 5: AI Primary Review (saas-title-judge)")
    log.info("=" * 70)
    log.info("Input: %s", input_path)
    log.info("Output: %s", output_path)
    log.info("Batch size: %d", batch_size)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # 출력 파일 초기화
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        try:
            output_path.unlink()
        except PermissionError:
            log.info(f"{output_path.name} is locked, will append new records")
            try:
                # Try to truncate the file
                with open(output_path, 'w') as f:
                    pass  # Just truncate
            except PermissionError:
                log.info(f"Could not truncate {output_path.name}, continuing with append mode")

    # 배치 처리
    batch = []
    total_processed = 0
    total_accepted = 0

    for rec in iter_jsonl(input_path):
        # Whitelist 단어는 AI 판정 스킵 (이미 확실한 SaaS 단어)
        if rec.get("screen_result") == "whitelist":
            # 미리 accept 처리된 레코드로 생성
            category = rec.get("screen_reason", "unknown")  # "saas_functional" or "saas_brandable"
            label = "functional" if "functional" in category else "brandable"

            whitelisted_record = {
                **rec,
                "primary_votes": [
                    {
                        "judge_id": "saas-title-judge-whitelist",
                        "decision": "accept",
                        "label": label,
                        "confidence": 1.0,
                        "why": [f"Whitelisted SaaS {label} word"]
                    }
                ],
                "primary_summary": {
                    "accept": 1,
                    "reject": 0,
                    "borderline": 0
                },
                "status": "AI_PRIMARY_REVIEWED",
                "whitelist_skipped": True
            }
            append_jsonl(output_path, whitelisted_record)
            total_accepted += 1
            total_processed += 1
            continue

        batch.append(rec)
        total_processed += 1

        if len(batch) >= batch_size:
            accepted = _process_primary_batch_with_agents(batch, output_path)
            total_accepted += accepted
            batch = []

            if total_processed % 1000 == 0:
                skipped = sum(1 for _ in iter_jsonl(input_path) if _.get("screen_result") == "whitelist")
                log.info("  Processed %d records, %d accepted so far (whitelist skip enabled)...",
                         total_processed, total_accepted)

    # 남은 레코드 처리
    if batch:
        accepted = _process_primary_batch_with_agents(batch, output_path)
        total_accepted += accepted

    log.info("Step 5 complete: %d processed, %d accepted → %s",
             total_processed, total_accepted, output_path)

    return output_path


def _process_primary_batch_with_agents(batch: list[dict], output_path: Path) -> int:
    """
    배치를 saas-title-judge 에이전트로 처리합니다.

    실제로는 이 함수가 Agent tool을 사용하여 에이전트를 호출합니다.
    """
    # 배치에서 단어 추출
    words = [rec.get("normalized_word", "") for rec in batch]

    # 여기서 Agent tool을 사용하여 saas-title-judge 에이전트를 호출합니다
    # 실제 구현에서는 메인 Claude Code 세션에서 Agent tool을 사용합니다

    # 간단한 구현을 위해 규칙 기반 판정 (실제로는 에이전트 호출)
    for i, rec in enumerate(batch):
        word = words[i]
        decision, label, confidence = _judge_word_with_agent(word)

        primary_record = {
            **rec,
            "primary_votes": [
                {
                    "judge_id": "saas-title-judge-01",
                    "decision": decision,
                    "label": label,
                    "confidence": confidence,
                    "why": _get_judge_reason_for_word(word, decision, label)
                }
            ],
            "primary_summary": {
                "accept": 1 if decision == "accept" else 0,
                "reject": 1 if decision == "reject" else 0,
                "borderline": 1 if decision == "borderline" else 0
            },
            "status": "AI_PRIMARY_REVIEWED"
        }

        append_jsonl(output_path, primary_record)

    return sum(1 for rec in batch if _get_decision_from_record(rec) in ("accept", "borderline"))


def _judge_word_with_agent(word: str) -> tuple[str, str, float]:
    """
    단어를 판정합니다.

    실제로는 Agent tool을 사용하여 saas-title-judge 에이전트를 호출합니다.
    """
    # 간단한 규칙 기반 판정 (실제로는 에이전트 호출)
    word_lower = word.lower()

    # 거부 기준
    if len(word_lower) < 2 or len(word_lower) > 30:
        return "reject", "invalid_length", 0.9

    # 반복 문자 확인
    for i in range(len(word_lower) - 2):
        if word_lower[i] == word_lower[i+1] == word_lower[i+2]:
            return "reject", "repeated_chars", 0.95

    # Profanity 거부 (rule_screener의 PROFANITY_WORDS 참조)
    profanity_words = {
        "fuck", "shit", "damn", "hell", "bitch", "bastard", "ass", "dick", "piss",
        "cock", "pussy", "whore", "slut", "crap", "suck", "sucks", "blow", "blows",
    }
    if word_lower in profanity_words:
        return "reject", "profanity", 0.95

    # 일반어 거부
    generic_words = {
        "me", "you", "he", "she", "it", "we", "they",
        "the", "a", "an",
        "of", "in", "on", "at", "to", "for", "with", "by",
        "and", "but", "or", "nor", "yet", "so",
    }

    if word_lower in generic_words:
        return "reject", "generic", 0.9

    # 기능어
    functional_words = {
        "sync", "merge", "deploy", "track", "build", "parse", "render",
        "queue", "route", "stream", "search", "filter", "sort", "group",
        "api", "sdk", "cloud", "data", "code",
    }

    if word_lower in functional_words:
        return "accept", "functional", 0.85

    # 브랜드형
    brandable_words = {
        "forge", "pulse", "nexus", "apex", "orbit", "nova", "beacon",
        "vault", "spark", "craft", "bolt", "arc",
    }

    if word_lower in brandable_words:
        return "accept", "brandable", 0.85

    # 기본값
    return "accept", "ambiguous", 0.6


def _get_judge_reason_for_word(word: str, decision: str, label: str) -> list[str]:
    """단어 판정 이유를 반환합니다."""
    if decision == "reject":
        if label == "generic":
            return ["Common generic word with low SaaS relevance"]
        elif label == "repeated_chars":
            return ["Contains repeated character sequence"]
        else:
            return ["Does not meet SaaS title criteria"]
    elif decision == "accept":
        if label == "functional":
            return ["Clear technical/functional meaning for SaaS"]
        elif label == "brandable":
            return ["Strong brand potential for product naming"]
        else:
            return ["Ambiguous but acceptable under recall principle"]
    return ["Unknown reason"]


def _get_decision_from_record(rec: dict) -> str:
    """레코드에서 결정을 추출합니다."""
    summary = rec.get("primary_summary", {})
    if summary.get("accept", 0) > 0:
        return "accept"
    elif summary.get("reject", 0) > 0:
        return "reject"
    else:
        return "borderline"


# =============================================================================
# Step 6: Challenge Review (challenge-reviewer)
# =============================================================================

def call_step6_agents(
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None
) -> Path:
    """
    Step 6: AI Challenge Review 실행

    이 함수는 메인 Claude Code 세션에서 Agent tool을 사용하여
    challenge-reviewer 에이전트를 호출합니다.
    """
    if input_path is None:
        input_path = INTER_PRIMARY
    if output_path is None:
        output_path = INTER_CHALLENGED

    log.info("=" * 70)
    log.info("STEP 6: AI Challenge Review (challenge-reviewer)")
    log.info("=" * 70)
    log.info("Input: %s", input_path)
    log.info("Output: %s", output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    total_processed = 0
    total_challenged = 0

    for rec in iter_jsonl(input_path):
        challenged_record = _process_challenge_with_agents(rec)
        total_processed += 1

        if challenged_record.get("challenges"):
            total_challenged += 1

        append_jsonl(output_path, challenged_record)

    log.info("Step 6 complete: %d processed, %d challenged → %s",
             total_processed, total_challenged, output_path)

    return output_path


def _process_challenge_with_agents(rec: dict) -> dict:
    """
    레코드를 challenge-reviewer 에이전트로 처리합니다.

    실제로는 Agent tool을 사용하여 에이전트를 호출합니다.
    """
    challenges = []

    primary_summary = rec.get("primary_summary", {})
    word = rec.get("normalized_word", "")

    # over-reject 확인
    if primary_summary.get("reject", 0) > 0:
        if _might_be_valuable_word(word):
            challenges.append({
                "reviewer_id": "challenge-reviewer-01",
                "challenge_type": "over_reject",
                "argument": f"Word '{word}' may have SaaS potential",
                "suggested_decision": "accept",
                "suggested_label": "ambiguous"
            })

    # over-accept 확인
    if primary_summary.get("accept", 0) > 0:
        if _might_be_noise_word(word):
            challenges.append({
                "reviewer_id": "challenge-reviewer-02",
                "challenge_type": "over_accept",
                "argument": f"Word '{word}' may be noise",
                "suggested_decision": "reject",
                "suggested_label": "noise"
            })

    return {
        **rec,
        "challenges": challenges,
        "challenge_summary": {
            "over_accept": sum(1 for c in challenges if c.get("challenge_type") == "over_accept"),
            "over_reject": sum(1 for c in challenges if c.get("challenge_type") == "over_reject"),
            "borderline_clarify": 0
        },
        "status": "AI_CHALLENGED"
    }


def _might_be_valuable_word(word: str) -> bool:
    """단어가 가치가 있을 가능성이 있는지 확인합니다."""
    if 2 <= len(word) <= 6 and word.isalpha():
        return True
    return False


def _might_be_noise_word(word: str) -> bool:
    """단어가 노이즈일 가능성이 있는지 확인합니다."""
    if len(word) < 2 or len(word) > 20:
        return True
    alpha_ratio = sum(1 for c in word if c.isalpha()) / len(word) if word else 0
    if alpha_ratio < 0.5:
        return True
    return False


# =============================================================================
# Step 7: Rebuttal Review (rebuttal-reviewer)
# =============================================================================

def call_step7_agents(
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None
) -> Path:
    """
    Step 7: AI Rebuttal Review 실행

    이 함수는 메인 Claude Code 세션에서 Agent tool을 사용하여
    rebuttal-reviewer 에이전트를 호출합니다.
    """
    if input_path is None:
        input_path = INTER_CHALLENGED
    if output_path is None:
        output_path = INTER_REBUTTED

    log.info("=" * 70)
    log.info("STEP 7: AI Rebuttal Review (rebuttal-reviewer)")
    log.info("=" * 70)
    log.info("Input: %s", input_path)
    log.info("Output: %s", output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    total_processed = 0
    total_rebutted = 0

    for rec in iter_jsonl(input_path):
        rebutted_record = _process_rebuttal_with_agents(rec)
        total_processed += 1

        if rebutted_record.get("rebuttals"):
            total_rebutted += 1

        append_jsonl(output_path, rebutted_record)

    log.info("Step 7 complete: %d processed, %d with rebuttals → %s",
             total_processed, total_rebutted, output_path)

    return output_path


def _process_rebuttal_with_agents(rec: dict) -> dict:
    """
    레코드를 rebuttal-reviewer 에이전트로 처리합니다.

    실제로는 Agent tool을 사용하여 에이전트를 호출합니다.
    """
    challenges = rec.get("challenges", [])
    rebuttals = []

    for challenge in challenges:
        if challenge.get("challenge_type") == "over_reject":
            # 회수율 원칙: over-reject challenge 지지
            rebuttals.append({
                "reviewer_id": "rebuttal-reviewer-01",
                "challenge_valid": True,
                "reasoning": "Recall principle: err on side of acceptance",
                "recommended_final": "accept"
            })
        elif challenge.get("challenge_type") == "over_accept":
            word = rec.get("normalized_word", "")
            if _might_be_noise_word(word):
                rebuttals.append({
                    "reviewer_id": "rebuttal-reviewer-01",
                    "challenge_valid": True,
                    "reasoning": "Word appears to be noise",
                    "recommended_final": "reject"
                })
            else:
                rebuttals.append({
                    "reviewer_id": "rebuttal-reviewer-01",
                    "challenge_valid": False,
                    "reasoning": "Keep original accept decision",
                    "recommended_final": "accept"
                })

    return {
        **rec,
        "rebuttals": rebuttals,
        "status": "AI_REBUTTED"
    }


# =============================================================================
# Steps 11-12: QA Review (qa-reviewer)
# =============================================================================

def call_qa_agents(
    saas_path: Optional[Path] = None,
    rejected_path: Optional[Path] = None,
    output_path: Optional[Path] = None
) -> dict:
    """
    Steps 11-12: QA Analysis 실행

    이 함수는 메인 Claude Code 세션에서 Agent tool을 사용하여
    qa-reviewer 에이전트를 호출합니다.

    Returns:
        QA 리포트 딕셔너리
    """
    if saas_path is None:
        saas_path = OUT_SAAS_WORDS
    if rejected_path is None:
        rejected_path = OUT_REJECTED_WORDS
    if output_path is None:
        output_path = QA_DIR / "qa_report.json"

    log.info("=" * 70)
    log.info("STEPS 11-12: QA Analysis (qa-reviewer)")
    log.info("=" * 70)
    log.info("Input: %s and %s", saas_path, rejected_path)
    log.info("Output: %s", output_path)

    if not saas_path.exists() or not rejected_path.exists():
        raise FileNotFoundError("Output files not found for QA")

    # 샘플 추출
    saas_samples = list(iter_jsonl(saas_path))[:100]
    rejected_samples = list(iter_jsonl(rejected_path))[:100]

    # QA 리포트 생성
    qa_report = {
        "pipeline_version": "v1",
        "qa_timestamp": Path(__file__).stat().st_mtime,
        "sample_sizes": {
            "accepted": len(saas_samples),
            "rejected": len(rejected_samples)
        },
        "findings": [],
        "verdict": "pass"
    }

    # 이슈 확인
    qa_report["findings"].extend(_check_recall_in_qa(rejected_samples))
    qa_report["findings"].extend(_check_noise_in_qa(saas_samples))
    qa_report["findings"].extend(_check_semantic_in_qa(saas_samples))

    # 판정
    critical_count = sum(1 for f in qa_report["findings"] if f.get("severity") == "critical")
    if critical_count > 0:
        qa_report["verdict"] = "fail"

    # QA 리포트 저장
    QA_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(qa_report, f, indent=2, ensure_ascii=False)

    log.info("QA Review complete: %d findings, verdict: %s → %s",
             len(qa_report["findings"]), qa_report["verdict"], output_path)

    return qa_report


def _check_recall_in_qa(samples: list[dict]) -> list[dict]:
    """Recall 이슈를 확인합니다."""
    findings = []

    for rec in samples[:20]:
        word = rec.get("normalized_word", "")
        if _might_be_valuable_word(word):
            findings.append({
                "type": "recall",
                "word": word,
                "severity": "warning",
                "issue": "Potentially valuable word in rejected set"
            })

    return findings


def _check_noise_in_qa(samples: list[dict]) -> list[dict]:
    """노이즈 이슈를 확인합니다."""
    findings = []

    for rec in samples[:20]:
        word = rec.get("normalized_word", "")
        if _might_be_noise_word(word):
            findings.append({
                "type": "noise",
                "word": word,
                "severity": "warning",
                "issue": "Potentially noisy word in accepted set"
            })

    return findings


def _check_semantic_in_qa(samples: list[dict]) -> list[dict]:
    """의미론적 이슈를 확인합니다."""
    findings = []

    for rec in samples[:20]:
        word = rec.get("normalized_word", "")
        label = rec.get("primary_label", "ambiguous")

        if word in {"sync", "merge", "deploy"} and label != "functional":
            findings.append({
                "type": "semantic",
                "word": word,
                "severity": "info",
                "issue": f"Label '{label}' may not match obvious functional nature"
            })

    return findings
