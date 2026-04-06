# Auto Pipeline Guide — 메인 Claude Code 세션 오케스트레이션

## 개요

이 문서는 **메인 Claude Code 세션이 전체 파이프라인(Steps 1-12)을 자동으로 실행**하는 방법을 설명합니다.

## 실행 모델

```
메인 Claude Code 세션 (오케스트레이터)
  │
  ├─ [Step 1-4]  python src/pipeline.py --phase prep
  │               결과: output/intermediate/04_screened_tokens.jsonl
  │
  ├─ [Step 5]    메인 세션이 Agent tool로 saas-title-judge 호출
  │               결과: output/intermediate/05_primary_reviewed.jsonl
  │
  ├─ [Step 6]    메인 세션이 Agent tool로 challenge-reviewer 호출
  │               결과: output/intermediate/06_challenged.jsonl
  │
  ├─ [Step 7]    메인 세션이 Agent tool로 rebuttal-reviewer 호출
  │               결과: output/intermediate/07_rebutted.jsonl
  │
  ├─ [Step 8]    python src/pipeline.py --phase consensus
  │               결과: output/intermediate/08_consensus.jsonl
  │
  ├─ [Step 9-10] python src/pipeline.py --phase export
  │               결과: output/saas_words.jsonl, output/human_review/*.xlsx
  │
  └─ [Step 11-12] 메인 세션이 Agent tool로 qa-reviewer 호출
                  결과: output/qa/qa_report.json
```

## 메인 세션 실행 절차

### 1. 준비 단계 (Steps 1-4)

먼저 메인 세션에서 Python 스크립트를 실행합니다:

```python
# 메인 Claude Code 세션에서 실행
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "src/pipeline.py", "--phase", "prep"],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    print(f"Prep phase failed: {result.stderr}")
    sys.exit(1)
```

또는 Bash tool을 사용합니다:

```bash
python src/pipeline.py --phase prep
```

### 2. 1차 판정 (Step 5)

메인 세션이 Agent tool을 사용하여 saas-title-judge 에이전트를 호출합니다:

```python
# output/intermediate/04_screened_tokens.jsonl을 읽고
# Agent tool을 사용하여 saas-title-judge 에이전트 호출
# 결과를 output/intermediate/05_primary_reviewed.jsonl에 저장
```

### 3. 반대검토 (Step 6)

```python
# output/intermediate/05_primary_reviewed.jsonl을 읽고
# Agent tool을 사용하여 challenge-reviewer 에이전트 호출
# 결과를 output/intermediate/06_challenged.jsonl에 저장
```

### 4. 재반백 (Step 7)

```python
# output/intermediate/06_challenged.jsonl을 읽고
# Agent tool을 사용하여 rebuttal-reviewer 에이전트 호출
# 결과를 output/intermediate/07_rebutted.jsonl에 저장
```

### 5. 합의 집계 (Step 8)

```bash
python src/pipeline.py --phase consensus
```

### 6. 결과 내보내기 (Steps 9-10)

```bash
python src/pipeline.py --phase export
```

### 7. QA 검증 (Steps 11-12)

```python
# output/saas_words.jsonl과 output/rejected_words.jsonl을 읽고
# Agent tool을 사용하여 qa-reviewer 에이전트 호출
# 결과를 output/qa/qa_report.json에 저장
```

## 전체 자동화 실행

메인 Claude Code 세션에서 위 모든 단계를 순차적으로 실행하는 방법은:

1. **사용자가 메인 세션에 "전체 파이프라인 실행"을 요청**
2. **메인 세션이 각 단계를 순차적으로 실행**
3. **AI 판정 단계에서 Agent tool을 사용하여 에이전트 호출**

이 방식의 장점:
- 사용자 개입 없이 전체 파이프라인이 자동으로 실행
- AI 판정은 에이전트를 통해 수행되므로 정확도 보장
- 메모리 효율성을 위해 Python 스크립트와 에이전트가 협력
