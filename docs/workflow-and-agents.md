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
  ├─ [Step 1-4]  python src/pipeline.py --steps 1-4
  │               결과: output/intermediate/04_screened_tokens.jsonl
  │
  ├─ [Step 5]    Claude Code가 04_screened_tokens.jsonl 읽음
  │               서브에이전트(saas-title-judge-01..05) 호출
  │               결과: output/intermediate/05_primary_reviewed.jsonl 저장
  │
  ├─ [Step 6-8]  동일 패턴으로 challenge → rebuttal → consensus 수행
  │
  └─ [Step 9-10] python src/pipeline.py --steps 9-10
                  결과: output/saas_words.jsonl, output/human_review/*.xlsx
```

에이전트 명세는 `.claude/agents/<agent-id>.md` 파일에 정의한다.
Python 스크립트가 `anthropic` 패키지를 직접 임포트하여 API를 호출하는 패턴은 **금지**.

## 7. QA 실행 원칙

### 7.1 QA 항상 전체 파이프라인 실행
QA는 **항상 파이프라인의 처음부터 실행**해야 한다.

- 중간 단계부터 재개하면 안 된다
- 모든 QA 실행은 중간 산출물을 삭제하고 처음부터 시작한다
- 이는 전체 파이프라인의 무결성을 검증하기 위함이다

### 7.2 QA 실행 방법
```bash
# 전체 파이프라인 QA (처음부터 끝까지)
python src/qa_full_pipeline.py

# 제한된 단어 수로 QA 테스트
python src/qa_full_pipeline.py --max-words 10000

# 메모리 제한 설정
python src/qa_full_pipeline.py --max-memory-mb 4096
```

### 7.3 QA 단계별 메모리 모니터링
QA 실행 중 각 단계마다 메모리 사용량을 모니터링한다:
- Prep: 입력 탐색 → 로드 → 정규화 → 규칙 스크리닝
- Primary Review: AI 1차 판정
- Challenge Review: 반대검토
- Rebuttal Review: 재반백
- Consensus: 합의 집계 (**streaming 모드**로 메모리 최적화)
- Export: 결과 저장 + 자동 QA
- QA Analysis: 최종 QA 리포트 생성
