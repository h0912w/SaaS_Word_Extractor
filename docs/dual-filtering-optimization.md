# 이중 필터링 최적화 — 처리 시간 단축

## 개요

두 단계에서 필터링을 강화하여 불필요한 AI 판정을 최소화합니다:
1. **입력 노이즈 필터링** (Step 2): 명백한 노이즈를 입력 로드 시 제외
2. **Whitelist 최적화** (Step 4): 명백한 SaaS 단어를 AI 판정 스킵

## 필터링 파이프라인

```
입력 파일 (30만줄)
  │
  ├─→ [Step 2] 입력 노이즈 필터링
  │    ├─ 순수 숫자
  │    ├─ 순수 특수문자
  │    ├─ 1글자 단어
  │    ├─ 비영어 문자열
  │    └─ 과도한 반복 패턴
  │    ↓
  │    약 20-30% 노이즈 제외
  │
  ├─→ [Step 3] 정규화
  │
  ├─→ [Step 4] 규칙 스크리닝 + Whitelist
  │    ├─ Generic words (관사격사 등)
  │    ├─ Profanity
  │    ├─ 길이/반복 문자 규칙
  │    └─ Whititelist 단어 → auto-accept (AI 판정 스킵)
  │    ↓
  │    약 50-70% 추가 제외 + Whititelist 약 10-15% auto-accept
  │
  └─→ [Steps 5-7] AI 판정
       └─→ 나머지 약 15-30%만 AI 판정
```

## Step 2: 입력 노이즈 필터링

### 필터링 기준

| 기준 | 예시 | 제거 이유 |
|-----|------|----------|
| 순수 숫자 | `12345`, `999` | 단어로서 기능 불가 |
| 순수 특수문자 | `!!!`, `@@@`, `---` | 의미 없는 문자열 |
| 1글자 단어 | `a`, `I` | 단어로서 기능 불가 |
| 비영어 문자열 | `한글`, `日本語`, `한국어` | 영어 SaaS 불가 |
| 영어 알파벳 없음 | `123!@#`, `___---` | 영어 단어 아님 |
| 과도한 반복 | `aaaaa`, `bbbbb` | 노이즈 패턴 |
| 언더스코어만 | `_____` | 변수명/코드 조각 |
| 낮은 알파벳 비율 | 영어 < 30% | 노이즈 가능성 |

### 처리 효과

```
30만줄 입력
  ↓
약 20-30% 노이즈 제외 (6-9만줄)
  ↓
약 21-24만줄만 정상 로드
```

## Step 4: Whitelist 최적화

### Whitelist 카테고리

#### 1. SaaS Functional Words (150개)
```
sync, merge, deploy, track, build, parse, render, queue, route,
stream, api, sdk, cloud, data, code, database, analytics, dashboard,
payment, invoice, login, logout, authenticate, ...
```

#### 2. SaaS Brandable Words (133개)
```
forge, pulse, nexus, apex, orbit, nova, beacon, vault, spark,
craft, bolt, arc, ion, neon, helium, carbon, silicon, surge,
flame, flow, core, stack, mesh, grid, sonic, audio, visual, ...
```

### 처리 효과

```
정규화된 단어
  ↓
약 10-15% Whitelist auto-accept
  ↓
약 17-21만줄만 AI 판정 대상
```

## 최종 처리량 비교

| 단계 | 처리 대상 | 누적 |
|-----|----------|------|
| 입력 원본 | 300,000줄 | - |
| 노이즈 필터링 후 | 210,000~240,000줄 | 60,000~90,000줄 (20-30%) |
| 정규화 후 | 약 250,000단어 | - |
| Whitelist 적용 후 | 약 215,000~220,000단어 | 30,000~35,000단어 (10-15%) |
| **최종 AI 판정 대상** | **170,000~180,000단어** | **120,000~130,000단어 (40-45%)** |

## 예상 시간 단축

| 방식 | AI 판정 단어 | 예상 시간 |
|-----|-------------|----------|
| 기존 | ~210,000단어 | ~20분 |
| 이중 필터링 | ~175,000단어 | ~16분 (약 20% 단축) |

## 코드 구조

### 1. input_noise_filter.py (신규)
- `is_noise_token()` - 노이즈 판정 함수
- `filter_noise_tokens()` - 필터링 이터레이터

### 2. saas_whitelist.py (신규)
- `SAAS_WHITELIST` - 283개 명백한 SaaS 단어
- `is_whitelisted()` - Whitelist 확인 함수
- `get_whitelist_category()` - 카테고리 반환

### 3. input_loader.py (수정)
- 입력 로드 시 노이즈 필터 적용
- 필터링 통계 자동 로깅

### 4. rule_screener.py (수정)
- Whitelist 확인 추가
- Whitelist 단어는 `screen_result="whitelist"` 반환

### 5. agent_executor.py (수정)
- Whitelist 단어는 AI 판정 스킵
- 미리 accept 처리된 레코드 생성

## 사용 방법

이중 필터링은 **기본적으로 활성화**되어 있습니다.

```bash
# 기존과 동일하게 실행 (자동으로 이중 필터링 적용)
python src/batch_orchestrator.py --max-words 300000 --auto-merge
```

## 필터링 통계 확인

로그 출력에서 필터링 효과를 확인할 수 있습니다:

```
[Step 2] Loading files (streaming mode)
  → Read 100000 tokens, filtered 25000 noise (25.0%), loaded 75000 tokens

[Step 3-4] Normalization and screening (streaming mode)
  Total processed: 100000
  Whitelist: 15000, Passed: 35000, Rejected: 50000
  AI review skip rate: 15.0% (whitelist / total)
```

## 주의사항

1. **Recall(회수율) 유지**: 노이즈 필터링은 명백한 노이즈만 제외
2. **보수적 접근**: 의심스러운 경우는 AI 판정에 위임
3. **필터링 기준 모니터링**: 필터링이 과도하게 강해지지 않도록 주의
