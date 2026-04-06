# CLAUDE.md

## 프로젝트 정의
이 프로젝트는 `/input/` 경로의 대규모 영어 단어 목록 파일을 읽고, **SaaS 웹서비스 제목에 사용할 가능성이 있는 단일 영어 단어만 최대한 많이 추출**하여 `/output/`에 **AI 재입력용 구조화 결과(JSONL/JSON)** 와 **사람 검토용 결과(XLSX/CSV)** 를 함께 생성한다. 이 프로젝트는 **단어 조합을 생성하지 않는다**.

## 실행 모델 — 메인 Claude Code 세션 오케스트레이션
- **전체 파이프라인(Steps 1-12)은 메인 Claude Code 세션이 오케스트레이션한다.**
- 주요 실행 방법: 메인 Claude Code 세션에서 `orchestrator.py`와 `agent_executor.py` 사용
- AI 판정 단계(Steps 5-7, 12)는 메인 세션이 Agent tool을 사용하여 에이전트를 직접 호출한다.
- Python 스크립트는 파일 I/O·정규화·규칙 필터링·저장 전용이다.
- 단계별 실행은 개발/디버깅 용도로만 사용한다.
- 상세 실행 흐름: `docs/workflow-and-agents.md` §7 참조

## 절대 원칙
- 입력 설계서의 요구사항을 누락하지 말 것. 누락 우려가 있으면 `docs/` 문서를 먼저 확인하고 반영할 것.
- **회수율(Recall) 최우선**. SaaS 제목으로 쓸 가능성이 조금이라도 있으면 쉽게 버리지 말 것.
- `CLAUDE.md`를 넘어서는 세부 규칙은 `docs/` 문서를 기준으로 따를 것.
- **LLM 처리 영역과 스크립트 처리 영역 분리 규칙을 반드시 유지할 것.**
- QA는 별도 테스트 전용 소프트웨어를 만들지 말고 **실제 사용자와 동일한 엔트리포인트/파이프라인** 을 그대로 실행할 것.
- 주요 의미 판단 단계는 반드시 **주판정 → 반대검토 → 재반박 → 합의** 구조를 거칠 것.
- 결과물 생성 후 원본 설계 대비 **누락 0%** 를 `docs/omission-check.md` 기준으로 다시 확인할 것.

## 범위
### 포함
- `/input/` 파일 탐색
- `.txt`, `.jsonl`, `.txt.zst` 중심의 단어 목록 로드
- 정규화
- 규칙 기반 1차 스크리닝
- SaaS 제목 적합성 의미 판정
- 기능형/브랜드형/애매형 태깅
- 다중 에이전트 상호검증
- 최종 JSONL/JSON 저장
- 사람 검토용 XLSX/CSV 생성
- QA 재실행 및 QA 다중 검토

### 제외
- 2단어/3단어 조합 생성
- 검색량/경쟁도 조사
- 도메인 구매 가능 여부 확인
- 실제 SaaS 우선순위 결정
- 웹서비스 구현

## 우선순위
1. 설계서 요구 누락 방지
2. 회수율 유지
3. 출력 계약 준수
4. 실제 사용자 파이프라인과 동일한 QA 유지
5. 다중 에이전트 검증 구조 유지
6. 중간 산출물 파일화
7. 성능 및 비용 최적화
8. 코드 미관/대규모 리팩토링

## 입력 계약
- 기본 입력 경로: `/input/`
- 기본 지원 형식: `*.txt`, `*.jsonl`, `*.txt.zst`
- 확장 가능 형식: 단일 컬럼 `*.csv`
- 실측 입력: Wikipedia 전체 표제어 덤프 (`all_words_deduped.txt.zst`, 약 4,500만 줄, 이미 소문자·정렬)
- 각 줄은 단어가 아닌 Wikipedia 표제어(구/phrase)일 수 있음. 공백은 언더스코어(`_`)로 대체됨
- **정규화 단계에서 언더스코어 기준으로 분리 후 개별 단어 단위로 평가**해야 함
- 위키 접미사(`_(band)`, `_(disambiguation)` 등) 제거 필수
- 특수문자, 메타토큰, 비영어 문자 다수 포함
- 대용량이므로 스트리밍 처리 필수
- 처리 대상 확정 전 입력 누락/비지원 형식 여부를 검토할 것.

## 출력 계약
반드시 아래 산출물을 생성할 것.
- `/output/saas_words.jsonl` (병합 시에만 생성)
- `/output/rejected_words.jsonl` (병합 시에만 생성)
- `/output/run_summary.json` (병합 시에만 생성)
- `/output/batch_XXX/saas_words_batch_XXX.jsonl` (배치별 개별 출력)
- `/output/batch_XXX/rejected_words_batch_XXX.jsonl` (배치별 개별 출력)
- `/output/batch_XXX/run_summary_batch_XXX.json` (배치별 개별 출력)
- `/output/human_review/saas_words_review.xlsx`
- `/output/human_review/saas_words_review.csv`
- `/output/human_review/rejected_words_review.xlsx`
- `/output/intermediate/*`
- `/output/qa/qa_report.json`
- `/output/qa/qa_findings.jsonl`
- `/output/qa/qa_disagreements.jsonl`
- `/output/qa/qa_human_review.xlsx`

AI용 JSONL/JSON과 사람용 XLSX/CSV는 **동일한 원천 레코드** 에서 생성하고 내용 불일치를 허용하지 말 것.

**배치 처리 규칙**:
- 배치 크기: 100,000단어 단위로 처리 (`BATCH_SIZE = 100000`)
- 각 배치는 독립적인 `batch_XXX` 디렉토리에 결과 저장
- 파일명에 배치 번호 포함: `saas_words_batch_001.jsonl`
- 최종 병합은 사용자가 명시적으로 요청할 때만 수행 (`--phase merge`)

## 고정 워크플로우
1. 입력 파일 탐색
2. 파일 로드 및 압축 해제
3. 토큰 정규화
4. 규칙 기반 1차 스크리닝
5. AI 기반 1차 의미 판정
6. AI 기반 반대검토
7. AI 기반 재반박 및 보완판정
8. 합의 기반 최종 결정
9. JSONL/JSON 결과 저장
10. 사람 검토용 XLSX/CSV 생성
11. QA가 실사용 파이프라인 재실행
12. QA 다중 에이전트 검증
13. 누락 0% 재확인

## 판단과 코드의 역할 분리
| 업무 | 담당 |
|---|---|
| 파일 탐색, 로드, 압축 해제, 정규화, 규칙 기반 스크리닝, JSONL/JSON 저장, XLSX/CSV 생성, 집계 | 스크립트 |
| 입력 범위 검토, 정규화 과잉/과소 검토, 의미 판정, 반대검토, 재반박, 합의, 출력 적합성 검토, QA 의미 검증 | LLM/에이전트 |
| 실제 프로젝트 실행 | 실사용 파이프라인 |
| 자동 확정이 위험한 경계 사례 | review 또는 risk flag로 보존 |

추가 상세 규칙은 `docs/llm-vs-script-boundary.md` 를 따른다.

## 수정 원칙
- 기존 구조를 유지하면서 필요한 파일만 최소 범위로 수정할 것.
- 설계 의도와 출력 계약을 깨는 구조 개편 금지.
- 테스트 없이 핵심 로직 교체 금지.
- 회수율을 떨어뜨리는 “보수적 정리” 금지.
- 출력 헤더, 시트 구조, 파일명, JSONL 필드 구조를 임의 변경하지 말 것.
- 중간 산출물 없이 메모리 내에서만 판단을 연결하지 말 것. 단계별 결과는 파일로 남길 것.
- 비용 절감을 이유로 다중 검토 구조를 임의 삭제하지 말 것. 축소가 필요하면 설계서 범위 내에서만 조정할 것.

## 금지사항
- 단어 조합 생성 금지
- 검색량/시장성 판단 혼입 금지
- QA 전용 별도 소프트웨어 추가 금지
- 출력 포맷 임의 축소/변경 금지
- 명백히 애매한 케이스를 설명 없이 reject 처리 금지
- 중요 판단 결과를 로그 없이 덮어쓰기 금지
- 스키마 검증 없이 최종 파일 저장 금지
- 설계서에 없는 범위 확장 작업 선행 금지

## 구현 시 항상 확인할 문서
문서 안내는 README가 아니라 아래 문서 세트로 관리한다.
- `docs/project-contract.md`
- `docs/workflow-and-agents.md`
- `docs/output-and-review-files.md`
- `docs/qa-and-validation.md`
- `docs/failure-policy.md`
- `docs/llm-vs-script-boundary.md`
- `docs/omission-check.md`
- `docs/document-map.md`

## 빌드/실행/테스트 원칙
- 실제 명령은 프로젝트 구현에 맞게 추가하되, 최소한 **실행 명령 / 검증 명령 / QA 재실행 명령** 을 문서화할 것.
- 구현 후 아래 계열 명령은 반드시 제공할 것.
  - 의존성 설치
  - 본 실행
  - QA 실행
  - 결과 검증
- 명령이 아직 없다면 TODO로 남기지 말고 생성 대상에 포함할 것.

## 완료 기준
- 입력부터 QA까지 전체 파이프라인이 동작한다.
- 필수 출력 파일이 모두 생성된다.
- JSONL/JSON/XLSX/CSV 간 의미 불일치가 없다.
- 회수율 우선 정책이 반영된다.
- 다중 에이전트 의미 검토 구조가 살아 있다.
- QA가 실사용 파이프라인을 그대로 재실행한다.
- `docs/omission-check.md` 기준 원본 설계서 누락 0%가 확인된다.
