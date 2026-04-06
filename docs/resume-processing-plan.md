# 이어서 처리 (Resume Processing) Plan

## 문제 정의

- 입력 파일: 28,108,856줄 (약 2800만 줄)
- 한 번 실행 시: 200만 줄 처리 (약 40분 소요)
- 전체 완료: 약 14번 실행 필요 (약 10시간)

**필요한 기능:**
- 클로드 코드를 껐다 켜도 이어서 처리
- 어디까지 처리했는지 기록
- 입력 파일이 바뀌면 처음부터 다시 시작

## 해결 방법

### 1. 진행 상황 저장 파일

**파일:** `output/progress/resume_state.json`

```json
{
  "input_file": "input/all_words_deduped.txt",
  "input_file_size": 523413131,
  "input_file_hash": "abc123...",
  "total_lines": 28108856,
  "last_processed_line": 2000000,
  "next_start_line": 2000001,
  "chunks_completed": [
    {
      "chunk_number": 1,
      "start_line": 1,
      "end_line": 2000000,
      "completed_at": "2026-04-03T13:08:18Z"
    }
  ],
  "status": "ready_for_next_chunk",
  "last_updated": "2026-04-03T13:15:41Z"
}
```

### 2. 입력 파일 변경 감지

- 파일명 확인
- 파일 크기 확인
- (선택) 파일 해시 확인 (SHA-256)

### 3. Pipeline.py 수정

**새로운 옵션:**
```bash
# 첫 실행: 100만 줄 처리 (줄 1 ~ 1,000,000)
python src/pipeline.py --phase prep --max-words 2000000

# 재실행: resume_state.json 확인 후 자동으로 다음 100만 줄 처리
python src/pipeline.py --phase prep --resume-auto

# 또는 명시적으로 청크 단위 실행
python src/pipeline.py --phase chunk --process-next
```

### 4. 작동 방식

1. **첫 실행:**
   - `resume_state.json` 생성
   - 입력 파일명, 크기, 전체 줄 수 기록
   - 200만 줄 처리 후 `last_processed_line = 2000000` 저장

2. **재실행 (클로드 코드 재시작 후):**
   - `resume_state.json` 확인
   - 입력 파일명/크기 비교 → 다르면 초기화
   - `next_start_line` 부터 다시 시작

3. **완료:**
   - `last_processed_line >= total_lines` 이면 완료
   - `status = "completed"`

## 구현 단계

### Phase 1: 파일 생성 및 검증
- [ ] `resume_state.json` 구조 정의
- [ ] 입력 파일 변경 감지 로직
- [ ] 줄 수 계산 로직

### Phase 2: Pipeline.py 통합
- [ ] `--resume-auto` 옵션 추가
- [ ] `input_loader.py`에 시작 줄 지정 기능
- [ ] 진행 상황 자동 저장

### Phase 3: 테스트
- [ ] 소규모 테스트 (1000줄)
- [ ] 파일 변경 감지 테스트
- [ ] 재시작 후 이어서 처리 테스트

## 사용 예시

```bash
# 첫 실행
python src/pipeline.py --phase prep --max-words 2000000
# → resume_state.json 생성 (last_processed_line: 1000000)

# 클로드 코드 재시작 후...
python src/pipeline.py --phase prep --resume-auto
# → 자동으로 줄 2000001부터 시작

# 상태 확인
python src/pipeline.py --status
# → 현재 진행 상황 출력

# 처음부터 다시 시작 (파일 변경 후)
python src/pipeline.py --phase prep --reset
```

## 주의사항

1. **중간 파일 누적:** 각 청크별 중간 파일이 `output/intermediate/`에 쌓임
   - 해결: 청크 완료 후 중간 파일 정리 또는 청크별 디렉토리 분리

2. **결과 병합:** 각 청크의 결과를 최종적으로 병합 필요
   - `saas_words.jsonl` = 청크 1 + 청크 2 + ...
   - `rejected_words.jsonl` = 청크 1 + 청크 2 + ...

3. **AI 판정 청크 처리:** AI 판정 단계도 청크 단위로 나누어야 함
   - 각 청크별로 Steps 5-7 수행
   - 최종에 전체 결과 병합
