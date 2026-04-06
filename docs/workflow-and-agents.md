# 워크플로우 및 에이전트 상세

## 1. 전체 흐름
1. 입력 파일 탐색
2. 파일 로드 및 압축 해제
3. 정규화
4. 규칙 기반 1차 스크리닝
5. AI 기반 1차 의미 판정
6. AI 기반 반대검토
7. AI 기반 재반박 및 보완판정
8. 합의 기반 최종 결정
9. 결과 저장
10. 사람 검토용 XLSX/CSV 생성
11. QA 실사용 파이프라인 재현
12. QA 결과물 다중 에이전트 검증

## 2. 상태 전이
- `DISCOVERED`
- `LOADED`
- `NORMALIZED`
- `SCREENED`
- `AI_PRIMARY_REVIEWED`
- `AI_CHALLENGED`
- `CONSENSUS_DECIDED`
- `EXPORTED`
- `QA_RUNNING`
- `QA_MULTI_REVIEWED`
- `QA_PASSED` / `QA_FAILED`

## 3. 단계별 정의

### 단계 1. 입력 파일 탐색
- 목적: `/input/` 에서 처리 가능한 파일 탐색
- 코드: `input-discovery`
- AI 검토:
  - `input-scope-checker-a`
  - `input-scope-checker-b`
  - `input-scope-checker-c`
  - `input-consensus-coordinator`

### 단계 2. 파일 로드 및 압축 해제
- 목적: `.txt`, `.jsonl`, `.txt.zst` 를 스트림으로 로드
- 코드: `input-loader`
- AI 검토:
  - `load-health-reviewer-a`
  - `load-health-reviewer-b`
  - `load-health-reviewer-c`
  - `load-consensus-coordinator`

### 단계 3. 정규화
- 목적: 소문자화, 노이즈 분리 가능한 수준의 정리
- 코드: `token-normalizer`
- AI 검토:
  - `normalization-auditor-a`
  - `normalization-auditor-b`
  - `normalization-auditor-c`
  - `normalization-consensus-coordinator`

### 단계 4. 규칙 기반 1차 스크리닝
- 목적: 명백한 노이즈 제거 + 애매한 케이스 보존
- 코드: `rule-screener`
- AI 검토:
  - `recall-guardian-a`
  - `noise-guardian-b`
  - `edgecase-guardian-c`
  - `screening-consensus-coordinator`

### 단계 5. AI 기반 1차 의미 판정
- 목적: SaaS 제목 사용 가능성 1차 판정
- 코드: `primary-ai-review-runner`
- AI 판정:
  - `saas-title-judge-01`
  - `saas-title-judge-02`
  - `saas-title-judge-03`
  - `saas-title-judge-04`
  - `saas-title-judge-05`

### 단계 6. AI 기반 반대검토
- 목적: accept/reject 양쪽 반례 탐색
- 코드: `challenge-review-runner`
- AI 판정:
  - `challenge-reviewer-01`
  - `challenge-reviewer-02`
  - `challenge-reviewer-03`
  - `challenge-reviewer-04`
  - `challenge-reviewer-05`

### 단계 7. AI 기반 재반박 및 보완판정
- 목적: 과잉 reject 완화, 과잉 accept에 risk flag 부여
- 코드: `rebuttal-runner`
- AI 판정:
  - `rebuttal-reviewer-01`
  - `rebuttal-reviewer-02`
  - `rebuttal-reviewer-03`

### 단계 8. 합의 기반 최종 결정 (Streaming Mode)
- 목적: 단계 4~7 결과 종합
- 코드: `consensus-engine` (streaming)
- 실행 방식: **Streaming 모드** - 한 레코드씩 처리하여 메모리 사용량 최적화
- 메모리 최적화: 전체 데이터를 메모리에 로드하지 않고 순차 처리
- AI 판정:
  - `consensus-aggregator-primary`
  - `consensus-aggregator-recall-guardian`
  - `consensus-aggregator-noise-guardian`
  - `consensus-chief`

### 단계 9. 결과 저장
- 목적: JSONL/JSON 생성
- 코드: `result-writer`
- AI 검토:
  - `output-schema-auditor-a`
  - `output-schema-auditor-b`
  - `output-schema-auditor-c`
  - `output-consensus-coordinator`

### 단계 10. 사람 검토용 엑셀/CSV 생성
- 목적: 사람이 빠르게 검토 가능한 출력 생성
- 코드: `human-review-exporter`
- AI 검토:
  - `human-output-auditor-a`
  - `human-output-auditor-b`
  - `human-output-auditor-c`
  - `human-output-consensus-coordinator`

### 단계 11. QA의 실사용 파이프라인 재현
- 목적: 별도 QA 전용 소프트웨어 없이 실제 엔트리포인트 재실행
- 코드: 없음. 실사용 파이프라인 그대로 사용
- AI 검토:
  - `qa-runtime-operator`
  - `qa-runtime-observer-a`
  - `qa-runtime-observer-b`
  - `qa-runtime-chief`

### 단계 12. QA 결과물 다중 에이전트 검증
- 목적: QA 결과물의 recall / noise / semantic / output 무결성 검토
- 코드: `qa-report-collator`
- AI 검토:
  - `qa-recall-auditor-01`
  - `qa-recall-auditor-02`
  - `qa-noise-auditor-01`
  - `qa-noise-auditor-02`
  - `qa-semantic-auditor-01`
  - `qa-semantic-auditor-02`
  - `qa-output-auditor-01`
  - `qa-output-auditor-02`
  - `qa-chief-reviewer`

## 4. 프로젝트 구조
```text
/project-root
 ├── CLAUDE.md
 ├── /.claude
 │   ├── /skills
 │   └── /agents
 ├── /input
 ├── /output
 │   ├── /intermediate
 │   └── /qa
 └── /docs
```

## 5. 에이전트 구조 원칙
- 메인 오케스트레이터 + 단계별 리뷰 카운슬 + QA 카운슬 구조 유지
- 대용량 데이터는 파일 기반 전달
- 제어 메시지는 소량 인라인 전달 가능
- 모든 주요 의미판정 단계는 **주판정 → 반대검토 → 재반박 → 합의**

## 6. 실행 모델 — Claude Code CLI 기반

**에이전트 = Claude Code 서브에이전트** (Python API 호출 코드가 아님)
**CLI / 웹 / 데스크탑 / IDE 모든 환경에서 동일하게 작동**

```
Claude Code 세션 (오케스트레이터)
  │
  ├─ [Step 1-4]  python src/pipeline.py --phase prep --batch-size 100000
  │               결과: output/intermediate/04_screened_tokens.jsonl
  │
  ├─ [Step 5]    Claude Code가 04_screened_tokens.jsonl 읽음
  │               서브에이전트(saas-title-judge-01..03) 호출
  │               결과: output/intermediate/05_primary_reviewed.jsonl 저장
  │
  ├─ [Step 6-8]  동일 패턴으로 challenge → rebuttal → consensus 수행
  │
  ├─ [Batch]     python src/pipeline.py --phase batch
  │               결과: output/batch_XXX/saas_words_batch_XXX.jsonl
  │
  └─ [Merge]     python src/pipeline.py --phase merge (사용자 요청 시만)
                  결과: output/saas_words.jsonl, output/human_review/*.xlsx
```

에이전트 명세는 `.claude/agents/<agent-id>.md` 파일에 정의한다.
Python 스크립트가 `anthropic` 패키지를 직접 임포트하여 API를 호출하는 패턴은 **금지**.

## 7. 전체 자동 파이프라인 실행

### 7.1 메인 Claude Code 세션 오케스트레이션 (권장 방식)

**중요**: 이 파이프라인은 메인 Claude Code 세션이 오케스트레이터 역할을 수행합니다.
AI 판정 단계(Steps 5, 6, 7, 12)는 메인 세션이 Agent tool을 사용하여 직접 에이전트를 호출합니다.

#### 소규모 데이터 (10만개 이하)

```python
# 메인 Claude Code 세션에서 실행
from src.orchestrator import run_full_pipeline_orchestrated
from src.agent_executor import call_step5_agents, call_step6_agents, call_step7_agents, call_qa_agents

# 에이전트 호출 함수 정의
def agent_caller(step, input_path, output_path, *args):
    if step == "step5":
        call_step5_agents(input_path, output_path)
    elif step == "step6":
        call_step6_agents(input_path, output_path)
    elif step == "step7":
        call_step7_agents(input_path, output_path)
    elif step == "qa":
        call_qa_agents(input_path, output_path)

# 전체 파이프라인 실행
result = run_full_pipeline_orchestrated(agent_caller=agent_caller)

if result["success"]:
    print("Pipeline completed successfully!")
else:
    print(f"Pipeline failed: {result.get('error')}")
```

#### 대규모 데이터 (10만개 초과)

**30만개 처리 요청 → 자동으로 10만개씩 3배치로 나누어 전체 파이프라인 실행**

```python
# 메인 Claude Code 세션에서 실행
from src.batch_orchestrator import run_batch_pipeline
from src.agent_executor import call_step5_agents, call_step6_agents, call_step7_agents, call_qa_agents

# 에이전트 호출 함수 정의
def agent_caller(step, input_path, output_path, *args):
    if step == "step5":
        call_step5_agents(input_path, output_path)
    elif step == "step6":
        call_step6_agents(input_path, output_path)
    elif step == "step7":
        call_step7_agents(input_path, output_path)
    elif step == "qa":
        call_qa_agents(input_path, output_path)

# 30만개 처리 → 자동으로 10만개씩 3배치 처리
result = run_batch_pipeline(
    agent_caller=agent_caller,
    max_words=300000,      # 처리할 총 단어 수
    auto_merge=True        # 완료 후 자동 병합
)

if result["success"]:
    print(f"All batches completed!")
    print(f"Batches: {', '.join(map(str, result['batches_completed']))}")
    print(f"Total words: {result['total_words_processed']}")
```

**자동 배치 처리 작동 방식:**
- 30만개 요청 → 자동으로 3개 배치로 분할 (각 10만개)
- 배치 1: lines 1-100,000 → 전체 파이프라인 실행 → `output/batch_001/`
- 배치 2: lines 100,001-200,000 → 전체 파이프라인 실행 → `output/batch_002/`
- 배치 3: lines 200,001-300,000 → 전체 파이프라인 실행 → `output/batch_003/`
- 완료 후 자동 병합 → `output/saas_words.jsonl` (전체 30만개 결과)

### 7.2 실행 흐름

```
메인 Claude Code 세션 (오케스트레이터)
  │
  ├─ [PHASE 1] Steps 1-4: Input → Load → Normalize → Screen
  │   └─ python src/pipeline.py --phase prep
  │
  ├─ [PHASE 2] Step 5: AI Primary Review
  │   └─ call_step5_agents() → Agent tool로 saas-title-judge 호출
  │
  ├─ [PHASE 3] Step 6: AI Challenge Review
  │   └─ call_step6_agents() → Agent tool로 challenge-reviewer 호출
  │
  ├─ [PHASE 4] Step 7: AI Rebuttal Review
  │   └─ call_step7_agents() → Agent tool로 rebuttal-reviewer 호출
  │
  ├─ [PHASE 5] Step 8: Consensus Aggregation
  │   └─ python src/pipeline.py --phase consensus
  │
  ├─ [PHASE 6] Steps 9-10: JSONL/JSON + XLSX/CSV Export
  │   └─ python src/pipeline.py --phase export
  │
  └─ [PHASE 7] Steps 11-12: QA Analysis
      └─ call_qa_agents() → Agent tool로 qa-reviewer 호출
```

### 7.3 단계별 실행 (개발/디버깅용)

각 단계를 별도로 실행할 수도 있습니다:

```bash
# Steps 1-4: 준비 단계
python src/pipeline.py --phase prep

# Step 8: 합의 집계 (Steps 5-7 완료 후)
python src/pipeline.py --phase consensus

# Steps 9-10: 결과 내보내기
python src/pipeline.py --phase export

# Step 12: QA 리포트 조립
python src/pipeline.py --phase qa
```

### 7.4 배치 처리 방식 (100K 단위)
데이터는 100,000단어 단위(배치)로 처리되며, 각 배치는 독립적으로 결과를 저장합니다:
- 배치 크기: `BATCH_SIZE = 100,000` (config.py)
- 배치 출력: `/output/batch_XXX/` 디렉토리에 별도 저장
- 파일명: `saas_words_batch_XXX.jsonl`, `rejected_words_batch_XXX.jsonl`
- 자동 병합: **수행하지 않음** (사용자 명령 시에만 병합)
- 병합 명령: `python src/pipeline.py --phase merge`

### 7.4 QA 단계별 메모리 모니터링
QA 실행 중 각 단계마다 메모리 사용량을 모니터링한다:
- Prep: 입력 탐색 → 로드 → 정규화 → 규칙 스크리닝
- Primary Review: AI 1차 판정
- Challenge Review: 반대검토
- Rebuttal Review: 재반백
- Consensus: 합의 집계 (**streaming 모드**로 메모리 최적화)
- Export: 결과 저장 + 자동 QA
- QA Analysis: 최종 QA 리포트 생성
