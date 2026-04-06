# 출력 형식 및 사람 검토용 파일 상세

## 1. AI용 출력

### 배치별 개별 출력 (기본)
- `/output/batch_001/saas_words_batch_001.jsonl`
- `/output/batch_001/rejected_words_batch_001.jsonl`
- `/output/batch_001/run_summary_batch_001.json`
- `/output/batch_002/saas_words_batch_002.jsonl`
- ...

### 최종 병합 출력 (사용자 요청 시)
- `/output/saas_words.jsonl` - 모든 배치의 SaaS 단어 병합
- `/output/rejected_words.jsonl` - 모든 배치의 거부 단어 병합
- `/output/run_summary.json` - 전체 집계

### `saas_words_batch_XXX.jsonl` 권장 스키마
```json
{"word":"merge","normalized_word":"merge","decision":"accept","candidate_modes":["functional","brandable"],"confidence":0.82,"consensus":{"support":8,"oppose":1,"abstain":1},"why_accept":["usable_in_tool_title","clear_english","high_reuse_potential"],"risk_flags":[],"source_file":"all_words_deduped.txt.zst","source_line":12345,"pipeline_version":"v2","batch_number":1}
```

### `rejected_words_batch_XXX.jsonl` 권장 스키마
```json
{"word":"!!!_(band)","normalized_word":"band","decision":"reject","consensus":{"support":1,"oppose":8,"abstain":1},"reject_reason":["noisy_token","encyclopedic_artifact"],"source_file":"all_words_deduped.txt.zst","source_line":3,"pipeline_version":"v2","batch_number":1}
```

### `run_summary_batch_XXX.json`
포함 항목 예시:
- batch_number
- 전체 입력 수 (이 배치)
- 정규화 후 수 (이 배치)
- pre_accept / review_needed / pre_reject 분포 (이 배치)
- 최종 accept / reject 분포 (이 배치)
- 태그 분포
- risk flag 분포
- 사용된 합의 정책
- 에이전트 버전
- 실행 시각
- 오류/스킵 통계

## 2. 사람 검토용 출력
### 기본 원칙
- 필터 적용
- 정렬 가능
- 헤더 고정
- 시트 분리
- 긴 텍스트 줄바꿈
- review_priority 기준 기본 정렬 가능

### `saas_words_review.xlsx` 권장 시트
1. `accepted_words`
2. `borderline_words`
3. `rejected_words`
4. `summary`
5. `qa_findings`

### `accepted_words` 권장 컬럼
- `word`
- `normalized_word`
- `decision`
- `primary_label`
- `candidate_modes`
- `confidence`
- `consensus_support`
- `consensus_oppose`
- `consensus_abstain`
- `why_accept`
- `risk_flags`
- `review_priority`
- `source_file`
- `source_line`
- `pipeline_version`
- `manual_note`
- `manual_override`

### `rejected_words_review.xlsx` 권장 컬럼
- `word`
- `normalized_word`
- `decision`
- `reject_reason`
- `consensus_support`
- `consensus_oppose`
- `consensus_abstain`
- `source_file`
- `source_line`
- `pipeline_version`
- `manual_note`

## 3. 일관성 규칙
- 사람용 파일은 JSONL 원천 레코드에서 직접 생성할 것.
- 사람이 보는 컬럼과 AI용 필드 의미가 달라지면 안 된다.
- QA 결과 핵심 요약은 summary 또는 qa_findings 시트에 노출한다.

## 4. 배치 처리 규칙
- 배치 크기: 100,000단어 단위 처리
- 배치별 파일명: `batch_XXX` 디렉토리, `*_batch_XXX.jsonl` 파일명
- 자동 병합 금지: 배치 완료 후 자동으로 병합하지 않음
- 병합 명령: `python src/pipeline.py --phase merge`로만 수행
- 배치 추적: `output/progress/` 디렉토리에서 진행 상황 관리
