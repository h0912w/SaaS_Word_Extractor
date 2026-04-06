# 전체 파이프라인 스텝 정리 (이중 필터링 최적화 적용)

## 개요

SaaS Word Extractor는 **30만개 단어 처리**를 **10만개씩 3배치**로 나누어 **전체 파이프라인(Steps 1-12)**를 반복합니다.

**이중 필터링 최적화**가 적용되어 처리 시간을 약 40-45% 단축합니다:
1. **입력 노이즈 필터링** (Step 2): 명백한 노이즈 20-30% 제외
2. **Whitelist 최적화** (Step 4): 명백한 SaaS 단어 10-15% auto-accept

## 배치 처리 구조

```
30만개 요청
  │
  ├─→ 배치 1 (lines 1-100,000)
  │     └─→ 전체 파이프라인 Steps 1-12 실행
  │        └─→ output/batch_001/
  │
  ├─→ 배치 2 (lines 100,001-200,000)
  │     └─→ 전체 파이프라인 Steps 1-12 실행
  │        └─→ output/batch_002/
  │
  └─→ 배치 3 (lines 200,001-300,000)
        └─→ 전체 파이프라인 Steps 1-12 실행
           └─→ output/batch_003/

최종 병합 → output/saas_words.jsonl (전체 202,289개)
```

## 전체 스텝 상세

### Step 1: 입력 파일 탐색
- **담당**: Python 스크립트
- **기능**: `/input/` 디렉토리에서 지원 파일 형식 탐색
- **지원 형식**: `.txt`, `.jsonl`, `.txt.zst`
- **출력**: `output/intermediate/01_discovered_files.json`

### Step 2: 파일 로드 및 압축 해제 (+입력 노이즈 필터링)
- **담당**: Python 스크립트
- **기능**: 대용량 파일 스트리밍 로드 + 명백한 노이즈 필터링
- **노이즈 필터 기준**:
  - 순수 숫자 (12345)
  - 순수 특수문자 (!!!, @@@)
  - 1글자 단어
  - 비영어 문자열 (한글, 日本語 등)
  - 영어 알파벳 없는 문자열
  - 과도한 반복 패턴 (aaaaa)
  - 언더스코어만 있는 문자열
- **예상 효과**: 약 20-30% 노이즈 제외
- **출력**: `output/intermediate/02_loaded_tokens.jsonl`

### Step 3: 토큰 정규화
- **담당**: Python 스크립트
- **기능**:
  - 소문자 변환
  - 특수문자 제거
  - 언더스코어 기준 분리 (`cloud_data` → `cloud`, `data`)
  - 위키 접미사 제거 (`_(band)`, `_(disambiguation)` 등)
- **출력**: 정규화된 토큰 (메모리 내 처리)

### Step 4: 규칙 기반 1차 스크리닝 (+Whitelist 최적화)
- **담당**: Python 스크립트
- **거부 기준**:
  - 길이: 2~30자 범위 밖
  - 반복 문자: 3회 이상 (`aaa`, `bbb` 등)
  - Generic words: 관사격사, 전치사, 접속사, 조건사
  - Profanity: 부적절한 단어
  - 기타: 비영어, 노이즈
- **Whitelist auto-accept**:
  - 283개 명백한 SaaS 단어 (functional + brandable)
  - Whitelist 단어는 `screen_result="whitelist"`로 표시
  - AI 판정(Steps 5-7) 스킵
- **예상 효과**: 약 10-15% auto-accept (AI 판정 스킵)
- **출력**: `output/intermediate/04_screened_tokens.jsonl`

### Step 5: AI 기반 1차 의미 판정
- **담당**: Claude 에이전트 (`saas-title-judge`)
- **기능**: SaaS 제목 적합성 판정
- **레이블 분류**:
  - `functional`: 기능형 (sync, merge, deploy 등)
  - `brandable`: 브랜드형 (forge, pulse, nexus 등)
  - `ambiguous`: 애매형 (둘 다 가능)
- **출력**: `output/intermediate/05_primary_reviewed.jsonl`

### Step 6: AI 기반 반대검토
- **담당**: Claude 에이전트 (`challenge-reviewer`)
- **기능**: over-reject/over-accept 탐지
- **검토 유형**:
  - `over_reject`: 거부된 단어 중 SaaS 가능성 있는 것
  - `over_accept`: 승인된 단어 중 노이즈인 것
- **출력**: `output/intermediate/06_challenged.jsonl`

### Step 7: AI 기반 재반백 및 보완판정
- **담당**: Claude 에이전트 (`rebuttal-reviewer`)
- **기능**: 이의 타당성 검토 및 최종 권고
- **원칙**: 회수율 우선 (불확실하면 accept)
- **출력**: `output/intermediate/07_rebutted.jsonl`

### Step 8: 합의 기반 최종 결정
- **담당**: Python 스크립트
- **기능**: 투표 집계 및 최종 결정
- **결정 로직**:
  - `vote_ratio >= 0.67`: accept
  - `vote_ratio >= 0.50`: borderline → accept with risk flag
  - `vote_ratio < 0.50`: reject
- **출력**: `output/intermediate/08_consensus.jsonl`

### Step 9: JSONL/JSON 결과 저장
- **담당**: Python 스크립트
- **기능**: 최종 결과 스키마 검증 및 저장
- **출력**:
  - `output/saas_words.jsonl`
  - `output/rejected_words.jsonl`
  - `output/run_summary.json`

### Step 10: 사람 검토용 XLSX/CSV 생성
- **담당**: Python 스크립트
- **기능**: 사람이 빠르게 검토할 수 있는 엑셀 파일 생성
- **출력**:
  - `output/human_review/saas_words_review.xlsx`
  - `output/human_review/saas_words_review.csv`
  - `output/human_review/rejected_words_review.xlsx`

### Step 11: QA 실사용 파이프라인 재현
- **담당**: Python 스크립트
- **기능**: 별도 QA 전용 소프트웨어 없이 실제 엔트리포인트 재실행
- **진행方式**: 전체 파이프라인을 처음부터 다시 실행

### Step 12: QA 다중 에이전트 검증
- **담당**: Claude 에이전트 (`qa-reviewer`)
- **기능**: 최종 출력물 품질 검증
- **검증 항목**:
  - Recall 감사 (wrongly rejected 단어 탐지)
  - Noise 감사 (wrongly accepted 노이즈 탐지)
  - Semantic 감사 (레이블 정확성 검증)
  - Output 감사 (통계적 이상 탐지)
- **출력**: `output/qa/qa_report.json`

## 실행 방식

### 단일 배치 실행 (10만개 이하)

```bash
python src/batch_orchestrator.py --max-words 100000
```

### 다중 배치 실행 (10만개 초과)

```bash
# 30만개 처리 → 자동으로 10만개씩 3배치 처리
python src/batch_orchestrator.py --max-words 300000 --auto-merge
```

### 배치별 수동 실행

```bash
# 배치 1: lines 1-100,000
python src/pipeline.py --phase prep --batch-start 1 --max-words 100000
# (Steps 5-10 자동 실행 후)

# 배치 2: lines 100,001-200,000
python src/pipeline.py --phase prep --batch-start 100001 --max-words 100000
# (Steps 5-10 자동 실행 후)

# 배치 3: lines 200,001-300,000
python src/pipeline.py --phase prep --batch-start 200001 --max-words 100000
# (Steps 5-10 자동 실행 후)
```

## 담당 영역 구분

| 단계 | 담당 | 설명 |
|-----|------|------|
| Steps 1-4 | Python 스크립트 | 파일 I/O, 정규화, 규칙 스크리닝 |
| Steps 5-7 | Claude 에이전트 | 의미 판정, 반대검토, 재반백 |
| Step 8 | Python 스크립트 | 투표 집계 알고리즘 |
| Steps 9-10 | Python 스크립트 | 파일 저장, 엑셀 생성 |
| Steps 11-12 | Claude 에이전트 | QA 검증 |

## 처리 결과 (30만개 테스트)

| 배치 | SaaS 단어 | 거부 단어 | 승인율 |
|-----|----------|----------|--------|
| 배치 1 | 97,408 | 5,935 | 94.3% |
| 배치 2 | 80,192 | 4,254 | 95.0% |
| 배치 3 | 24,689 | 551 | 97.8% |
| **합계** | **202,289** | **10,740** | **94.9%** |
