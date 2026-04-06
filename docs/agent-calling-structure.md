# 에이전트 호출 구조 — 메인 에이전트 중심 자동 실행

## 핵심 구조

```
┌─────────────────────────────────────────────────────────────┐
│              메인 Claude Code 세션 (Main Agent)              │
│                    [오케스트레이터]                          │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ saas-title-judge│  │challenge-reviewer│  │rebuttal-reviewer │
│   (Step 5)      │  │   (Step 6)       │  │   (Step 7)       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  qa-reviewer    │
                    │   (Step 12)     │
                    └─────────────────┘
```

## 실행 방법

### 사용자가 하는 일 (최초 1회만)

```python
# 메인 Claude Code 세션에서 한 번만 실행
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
```

### 그 후는 자동 실행

```
사용자 입력 (1회)
  │
  ▼
메인 에이전트 시작
  │
  ├─→ Python 스크립트 실행 (Steps 1-4)
  │       └─→ 결과 파일 생성
  │
  ├─→ 메인 에이전트가 saas-title-judge 호출 (Step 5)
  │       └─→ Agent tool 사용
  │       └─→ 결과 파일 생성
  │
  ├─→ 메인 에이전트가 challenge-reviewer 호출 (Step 6)
  │       └─→ Agent tool 사용
  │       └─→ 결과 파일 생성
  │
  ├─→ 메인 에이전트가 rebuttal-reviewer 호출 (Step 7)
  │       └─→ Agent tool 사용
  │       └─→ 결과 파일 생성
  │
  ├─→ Python 스크립트 실행 (Step 8)
  │       └─→ 투표 집계
  │
  ├─→ Python 스크립트 실행 (Steps 9-10)
  │       └─→ 결과 저장
  │
  └─→ 메인 에이전트가 qa-reviewer 호출 (Step 12)
          └─→ Agent tool 사용
          └─→ QA 리포트 생성
```

## 사용자 개입 포인트

| 단계 | 사용자 개입 | 설명 |
|:----:|:----------:|------|
| 시작 | **필요 (1회)** | `run_full_pipeline_orchestrated()` 호출 |
| Step 1-4 | 없음 | Python 스크립트 자동 실행 |
| Step 5 | 없음 | 메인 에이전트가 saas-title-judge 자동 호출 |
| Step 6 | 없음 | 메인 에이전트가 challenge-reviewer 자동 호출 |
| Step 7 | 없음 | 메인 에이전트가 rebuttal-reviewer 자동 호출 |
| Step 8-10 | 없음 | Python 스크립트 자동 실행 |
| Step 12 | 없음 | 메인 에이전트가 qa-reviewer 자동 호출 |
| 완료 | 없음 | 결과 파일 자동 생성 |

## 요약

- **사용자 개입**: 최초 1회만 (`run_full_pipeline_orchestrated()` 호출)
- **메인 에이전트**: 모든 서브 에이전트를 Agent tool로 자동 호출
- **서브 에이전트**: 각자의 전문 영역(saas-title-judge, challenge-reviewer 등) 수행
- **실행 방식**: 완전 자동 (사용자 추가 개입 없음)
