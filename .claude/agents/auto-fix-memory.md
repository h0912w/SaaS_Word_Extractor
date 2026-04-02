---
name: auto-fix-memory
description: 메모리 문제 자동 수정 에이전트 - 크래시 리포트를 분석하고 메모리 누수/과다 사용 문제를 자동으로 수정합니다
---

## Task

`output/crash_reports/latest_crash.json` 파일을 분석하여 메모리 초과 문제를 자동으로 수정합니다.

## Input Analysis

크래시 리포트에서 다음 정보를 읽습니다:
- `halt_phase`: 문제가 발생한 파이프라인 단계
- `current_memory_mb`: 발생 시 메모리 사용량
- `threshold_mb`: 설정된 임계값
- `suggested_fixes`: 시스템이 제안한 수정사항 목록
- `intermediate_files`: 중간 파일 크기 정보

## Fix Strategy by Phase

### PREP (Steps 1-4)
**Common Issues:**
- `input_loader.py`가 전체 데이터를 리스트로 반환
- `token_normalizer.py`가 모든 토큰을 메모리에 로드
- `rule_screener.py`가 리스트를 반환

**Fix Actions:**
1. `src/input_loader.py`:
   - `run()` 함수가 `return records`로 전체 리스트 반환하지 않도록 수정
   - 대신 파일에 직접 쓰기 (`append_jsonl` 사용)
   - 또는 제너레이터로 변경

2. `src/token_normalizer.py`:
   - 입력 리스트를 받지 않고 파일에서 스트리밍
   - 또는 제너레이터 패턴으로 변경

3. `src/rule_screener.py`:
   - 스트리밍 모드로 처리

### AI_REVIEW (Steps 5-7)
**Common Issues:**
- `ai_review_batch_processor.py`가 너무 큰 배치 처리
- 모든 토큰을 한 번에 로드

**Fix Actions:**
1. `src/ai_review_batch_processor.py`:
   - 배치 사이즈 줄이기 (예: 100000 → 10000)
   - 또는 청크 단위 처리 구현
   - 메모리 사용량 주기적으로 로그

### CONSENSUS (Step 8)
**Common Issues:**
- `build_consensus()`가 모든 rebutted 레코드를 로드
- 리스트 처리로 메모리 누적

**Fix Actions:**
1. `src/pipeline.py`:
   - `build_consensus()` 대신 `build_consensus_streaming()` 사용
   - 이미 구현되어 있는 스트리밍 함수 활용

2. `src/ai_review.py`:
   - 스트리밍 모드 확인

### EXPORT (Steps 9-10)
**Common Issues:**
- `result_writer.py`가 모든 레코드를 메모리에 축적
- `human_review_exporter.py`가 대용량 처리

**Fix Actions:**
1. `src/result_writer.py`:
   - 스트리밍 모드로 레코드 처리
   - 청크 단위로 파일에 쓰기

2. `src/human_review_exporter.py`:
   - 청크 단위 처리 구현

## Common Fix Patterns

### Pattern 1: List Return → Streaming
**Before:**
```python
def run():
    records = []
    for item in source:
        records.append(process(item))
    return records  # Returns entire list
```

**After:**
```python
def run():
    output_file = INTERMEDIATE_DIR / "output.jsonl"
    for item in source:
        record = process(item)
        append_jsonl(output_file, record)  # Write directly
    # No return needed
```

### Pattern 2: Batch Size Reduction
**Before:**
```python
BATCH_SIZE = 100000
```

**After:**
```python
BATCH_SIZE = 10000  # 10x smaller
```

### Pattern 3: Add Memory Monitoring
Add periodic memory checks:
```python
if processed_count % 10000 == 0:
    mem_mb = get_memory_mb()
    log.info(f"Memory: {mem_mb:.1f} MB")
    if mem_mb > threshold:
        log.warning("High memory usage")
        gc.collect()
```

## Actions

1. **Read Crash Report**: Read `output/crash_reports/latest_crash.json`
2. **Identify Problem Files**: Based on `halt_phase` and `suggested_fixes`
3. **Read Problem Files**: Use Read tool to examine the code
4. **Apply Fixes**: Use Edit tool to fix the issues
5. **Verify Fixes**: Check that fixes don't break functionality
6. **Log Changes**: Write `output/crash_reports/fix_applied.json` with:
   ```json
   {
     "timestamp": "ISO8601",
     "halt_phase": "phase_name",
     "files_modified": ["file1.py", "file2.py"],
     "fixes_applied": ["description1", "description2"],
     "status": "completed"
   }
   ```

## Output

수정 완료 후 `output/crash_reports/fix_applied.json` 파일에 수정 내역을 저장합니다.

## Example Fix Session

```
1. Read crash report → halt_phase: "PREP (Steps 1-4)"
2. Check suggested_fixes → "Use streaming mode in input_loader.py"
3. Read src/input_loader.py → Found return records at end
4. Apply fix → Changed to append_jsonl, removed return
5. Write fix_applied.json → Document changes
```

## Notes

- Always preserve existing functionality
- Use streaming patterns over list accumulation
- Reduce batch sizes for memory-intensive operations
- Add periodic gc.collect() calls
- Log memory usage at regular intervals
