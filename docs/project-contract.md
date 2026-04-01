# 프로젝트 계약 상세

## 1. 핵심 목적
- `/input/` 의 대규모 영어 단어 목록에서 **SaaS 제목용 단일 영어 단어 후보**를 최대 회수율로 추출한다.
- 후속 AI가 바로 재사용할 수 있는 구조화 출력과 사람이 검토하기 쉬운 출력 둘 다 생성한다.
- 단어 조합 생성은 본 프로젝트 범위 밖이다.

## 2. 포함 / 제외 범위
### 포함
- 입력 파일 탐색 및 적재
- 압축 해제
- 줄 단위 토큰 로드
- 정규화 및 사전 필터링
- SaaS 제목용 가능성 판정
- 기능형 / 브랜드형 / 애매형 태깅
- 채택 / 제외 결과 저장
- 다중 에이전트 상호검증
- QA 파이프라인 실행 및 검증

### 제외
- 2단어, 3단어, 4단어 조합 생성
- 도메인 구매 가능 여부 확인
- 검색량 / 경쟁도 조사
- 실제 SaaS 우선순위 결정
- 웹서비스 개발

## 3. 입력 계약 상세
### 입력 경로
- 기본 경로: `/input/`

### 지원 형식
- `*.txt`
- `*.jsonl`
- `*.txt.zst`
- 향후 확장: `*.csv` 단일 컬럼

### 입력 특성 (실측 기반 — all_words_deduped.txt.zst 기준)
- 줄 단위 항목 목록 (약 4,500만 줄 추정)
- **Wikipedia 전체 표제어 덤프**: 대부분의 줄이 단어가 아닌 구(phrase)
- **공백은 언더스코어(`_`)로 대체** 되어 있음 (e.g. `forge_welding`, `pulse_(band)`)
- **이미 전부 소문자** 처리된 상태
- **알파벳 오름차순 정렬** (기호 → 숫자 → 알파벳 순)
- 기호·숫자로만 된 줄, 위키 표제어 접미사(`_(band)`, `_(disambiguation)` 등), 비영어 문자 다수 포함
- 매우 대용량 — 스트리밍 처리 필수
- **단일 SaaS 단어 추출을 위해 언더스코어 분리 및 개별 단어화 처리 필요**
  - 예: `forge_welding` → `forge`, `welding` 각각 평가
  - 예: `nexus_(band)` → wiki 접미사 제거 → `nexus` 단일 단어 평가
  - 분리 후 중복 제거(dedupe) 필수

## 4. 출력 계약 상세
### 주 출력
1. `/output/saas_words.jsonl`
2. `/output/rejected_words.jsonl`
3. `/output/run_summary.json`
4. `/output/human_review/saas_words_review.xlsx`
5. `/output/human_review/saas_words_review.csv`
6. `/output/human_review/rejected_words_review.xlsx`
7. `/output/intermediate/`
8. `/output/qa/qa_report.json`
9. `/output/qa/qa_findings.jsonl`
10. `/output/qa/qa_disagreements.jsonl`
11. `/output/qa/qa_human_review.xlsx`

### 산출물 원칙
- AI용 JSONL/JSON과 사람용 XLSX/CSV는 같은 원천 레코드에서 파생되어야 한다.
- 파일 간 의미 불일치 허용 금지.
- 단계별 중간 산출물은 `/output/intermediate/` 에 저장한다.
- QA 관련 산출물은 `/output/qa/` 로 분리한다.

## 5. 용어 정의
- **SaaS 제목용 단어**: 웹서비스 제목, 기능명, 툴명, 제품명 구성요소로 사용할 가능성이 있는 단일 영어 단어
- **기능형(functional)**: convert, merge, sync처럼 기능을 직접 설명
- **브랜드형(brandable)**: forge, pulse, nexus처럼 제품명 구성요소로 사용 가능
- **애매형(ambiguous)**: 단독 의미는 약하지만 후속 조합 단계에서 쓸 가능성이 있는 단어
- **다중 더블체크**: 복수 AI 에이전트가 독립적으로 검토하고 합의하는 구조
- **주판정 / 반대검토 / 합의**: 의미판정 기본 구조

## 6. 고정 제약조건
- 회수율 최우선
- 단어 조합 생성 금지
- 불필요 단어 제거
- AI 친화 출력 + 사람 친화 출력 병행
- QA 전용 별도 코드 금지
- QA도 다중 검증 필수
- 중간 결과 파일화 우선

## 7. 사람 친화 출력 원칙
- 엑셀은 필터, 정렬, 고정 헤더, 시트 분리를 기본 적용한다.
- `accepted_words`, `borderline_words`, `rejected_words`, `summary`, `qa_findings` 시트 구성을 우선 고려한다.
- 수동 검토용 `manual_note`, `manual_override`, `review_priority` 컬럼을 포함 가능하다.
