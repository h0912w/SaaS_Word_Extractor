"""
Input Noise Filter — 입력 파일 로드 시 노이즈 필터링

Step 2(파일 로드) 단계에서 명백한 노이즈를 사전에 제거하여
불 불필요한 단어가 들어오는 것을 방지합니다.

필터링 기준:
1. 순수 숫자 (제외)
2. 순수 특수문자 (제외)
3. 1글자 단어 (제외)
4. 비영어 문자열 (제외)
5. 의미 없는 문자 조합 (제외)
"""

import re
from typing import Iterator, Optional

from utils import get_logger

log = get_logger("input_noise_filter")


# 필터링 정규식
PURE_NUMBER_RE = re.compile(r'^\d+$')  # 순수 숫자
PURE_SPECIAL_RE = re.compile(r'^[^\w\s]+$')  # 순수 특수문자
NON_ENGLISH_RE = re.compile(r'[^\x00-\x7F]+')  # 비영어(ASCII 외) 문자 포함
NON_ALPHA_RE = re.compile(r'^[^a-zA-Z]+$')  # 영어 알파벳 없음
REPEAT_PATTERN_RE = re.compile(r'^(.)\1{4,}$')  # 5회 이상 반복


def is_noise_token(token: str) -> tuple[bool, str]:
    """
    토큰이 노이즈인지 확인합니다.

    Args:
        token: 확인할 토큰

    Returns:
        (is_noise, reason) - is_noise가 True이면 필터링 대상
    """
    if not token:
        return True, "empty_token"

    # 1. 순수 숫자
    if PURE_NUMBER_RE.match(token):
        return True, "pure_number"

    # 2. 순수 특수문자
    if PURE_SPECIAL_RE.match(token):
        return True, "pure_special"

    # 3. 1글자 단어 (영어 단어 최소 길이)
    if len(token) < 2:
        return True, "too_short"

    # 4. 비영어 문자열 포함
    if NON_ENGLISH_RE.search(token):
        return True, "contains_non_english"

    # 5. 영어 알파벳이 전혀 없음
    if NON_ALPHA_RE.match(token):
        return True, "no_alphabetic_chars"

    # 6. 과도한 반복 패턴 (aaaaa, !!!!!)
    if REPEAT_PATTERN_RE.match(token):
        return True, "excessive_repetition"

    # 7. 밑줄표로만 구성된 경우 (또는 언더스코어 문제)
    if token.count('_') > 3 and token.replace('_', '') == '':
        return True, "only_underscores"

    # 8. 혼합 문자열이지만 영어 비율이 너무 낮음
    alpha_ratio = sum(1 for c in token if c.isalpha()) / len(token)
    if alpha_ratio < 0.3:
        return True, "low_alpha_ratio"

    return False, None


def filter_noise_tokens(tokens: Iterator[str]) -> Iterator[tuple[str, dict]]:
    """
    토큰 스트림에서 노이즈를 필터링합니다.

    Args:
        tokens: 토큰 이터레이터

    Yields:
        (token, metadata) 튜플 - 노이즈는 건너뜀
    """
    total_count = 0
    pass_count = 0
    noise_count = 0

    for token in tokens:
        total_count += 1
        is_noise, reason = is_noise_token(token)

        if is_noise:
            noise_count += 1
            # 노이즈 토큰은 건너뜀
            continue

        pass_count += 1
        yield token, {"original_index": total_count}

    # 로그 출력
    log.info("Noise filtering complete:")
    log.info("  Total tokens: %d", total_count)
    log.info("  Passed: %d (%.1f%%)", pass_count, 100 * pass_count / max(total_count, 1))
    log.info("  Filtered (noise): %d (%.1f%%)", noise_count, 100 * noise_count / max(total_count, 1))

    # 필터링 통계 저장
    return {
        "total_tokens": total_count,
        "passed_tokens": pass_count,
        "noise_tokens": noise_count,
        "noise_rate": noise_count / max(total_count, 1)
    }
