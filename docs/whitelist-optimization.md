# Whitelist 최적화 — 처리 시간 단축

## 개요

Step 4 스크리닝 단계에서 **명백한 SaaS 단어**를 미리 accept하여 AI 판정(Steps 5-7)을 건너뛰도록 최적화합니다.

## Whitelist 구조

### Whitelist에 포함되는 단어

#### 1. 명백한 SaaS 기능어 (150+개)
```
sync, merge, deploy, track, build, parse, render, queue, route,
stream, api, sdk, cloud, data, code, tech, database, analytics,
dashboard, payment, invoice, login, logout, authenticate, ...
```

#### 2. 명백한 SaaS 브랜드형 (130+개)
```
forge, pulse, nexus, apex, orbit, nova, beacon, vault, spark,
craft, bolt, arc, ion, neon, helium, carbon, silicon, surge,
flame, flow, core, stack, mesh, grid, sonic, audio, visual, ...
```

### Whitelist 통계
- **총 단어 수**: 283개
- **Functional**: 150개
- **Brandable**: 133개

## 처리 흐름

### 기존 방식
```
Step 4 (스크리닝) → 모든 단어 pass → Step 5-7 (AI 판정)
```

### Whitelist 최적화 방식
```
Step 4 (스크리닝) → Whitelist 단어 auto-accept → AI 판정 스킵
                     ↓
               나머지 단어만 → Step 5-7 (AI 판정)
```

## 코드 수정 사항

### 1. saas_whitelist.py (신규)
- Whitelist 단어 정의
- `is_whitelisted()` 함수
- `get_whitelist_category()` 함수

### 2. rule_screener.py (수정)
```python
# W1 – Whitelist check (최우선)
if is_whitelisted(word):
    return "whitelist", f"saas_{category}"
```

### 3. agent_executor.py (수정)
```python
# Whitelist 단어는 AI 판정 스킵
if rec.get("screen_result") == "whitelist":
    # 미리 accept 처리
    append_jsonl(output_path, whitelisted_record)
    continue
```

## 예상 효과

### 30만개 처리 시간 비교

| 방식 | AI 판정 단어 수 | 예상 시간 |
|-----|----------------|----------|
| 기존 | ~21만개 | ~20분 |
| Whitelist 적용 | ~17만개 | ~16분 (약 20% 단축) |

### Whitelist 적용 전/후

| 배치 | 스크리닝 통과 | Whitelist 적용 | AI 판정 대상 |
|-----|-------------|----------------|-------------|
| 배치 1 | 103,343개 | ~30,000개 | ~73,000개 |
| 배치 2 | 84,446개 | ~25,000개 | ~59,000개 |
| 배치 3 | 25,240개 | ~7,500개 | ~17,000개 |

## 사용 방법

Whitelist 최적화는 **기본적으로 활성화**되어 있습니다.

```bash
# 기존과 동일하게 실행
python src/batch_orchestrator.py --max-words 300000 --auto-merge
```

## Whititelist 확장 가이드

단어를 Whitelist에 추가하려면 `src/saas_whitelist.py`에 단어를 추가하세요:

```python
# 기능어 추가
SAAS_FUNCTIONAL_WORDS = {
    ...,
    "new_feature_word",  # 새로운 기능어
}

# 브랜드형 추가
SAAS_BRANDABLE_WORDS = {
    ...,
    "new_brand_word",  # 새로운 브랜드형
}
```

## 주의사항

1. **Recall(회수율) 우선**: Whitelist는 명백한 SaaS 단어만 포함
2. **의심스러운 단어는 제외**: 애매한 단어는 AI 판정에 위임
3. **주기적 검토**: Whitelist 기준이 너무 느슨해지지 않도록 관리 필요
