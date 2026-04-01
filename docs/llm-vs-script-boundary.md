# LLM 처리 영역과 스크립트 처리 영역 상세

## 0. 실행 모델 — 반드시 먼저 읽을 것

이 프로젝트의 AI 판정은 **현재 실행 중인 Claude Code 세션(대화)** 이 직접 수행한다.
Python 스크립트 안에서 `ANTHROPIC_API_KEY` 환경변수를 설정하거나
`anthropic` Python 패키지로 인라인 API 호출을 하는 것은 불필요하며 금지된다.
이 규칙은 **CLI / 웹(claude.ai/code) / 데스크탑 / IDE 확장 모든 환경에서 동일**하다.

| 구분 | 담당 | 비고 |
|---|---|---|
| 파일 탐색·로드·정규화·규칙 스크리닝·JSONL 저장·XLSX 생성 | Python 스크립트 | `python src/pipeline.py` 로 실행 |
| 의미 판정·반대검토·재반박·합의·QA 의미 검증 | **Claude Code (현재 세션)** | CLI가 중간 파일을 읽고 직접 판정 |
| 서브에이전트 정의 | `.claude/agents/*.md` 파일 | Python 클래스가 아닌 에이전트 명세 |

**잘못된 패턴 (금지)**:
```python
# 절대 금지 — Python 스크립트 내 직접 API 호출
import anthropic
client = anthropic.Anthropic()  # API키 필요, Claude Code 내에서는 불필요
```

**올바른 패턴**:
```
1. python src/pipeline.py --steps 1-4   ← 스크립트가 처리
2. Claude Code가 output/intermediate/04_screened_tokens.jsonl 읽기
3. Claude Code가 의미 판정 수행 후 output/intermediate/05_primary_reviewed.jsonl 저장
4. python src/pipeline.py --steps 9-10  ← 스크립트가 처리
```

---

## 1. 스크립트가 처리할 것
- 파일 탐색
- 압축 해제
- 스트리밍 로드
- 토큰 소문자화 및 정규화 규칙 적용
- 명백한 노이즈 1차 제거
- JSONL / JSON 저장
- XLSX / CSV 생성
- 통계 집계
- 중간 산출물 파일화
- QA용 결과 수집 및 리포트 파일 조립

## 2. LLM / 에이전트가 처리할 것
- 입력 범위/적합성 검토
- 정규화가 과잉/과소인지 검토
- 단어가 SaaS 제목용으로 살아남아야 하는지 의미 판정
- 기능형 / 브랜드형 / 애매형 분류
- 1차 판정 반례 탐색
- reject 완화 또는 accept 경고 플래그 부여
- 최종 합의
- 출력이 후속 AI 입력용으로 적합한지 검토
- QA 의미 검증

## 3. 사용자 확인 또는 review 로 남겨야 하는 것
- 자동 확정 신뢰도가 낮은 경계 사례
- 다수 에이전트 의견 충돌이 큰 사례
- 의미는 있지만 SaaS 제목 적합성이 약한 사례
- 노이즈인지 브랜드 후보인지 애매한 토큰

## 4. 금지
- 스크립트가 해야 할 파일 처리/저장/정규화 로직을 LLM 응답 의존으로 대체하지 말 것
- 의미 판단이 필요한 문제를 규칙만으로 과감하게 reject 하지 말 것
- LLM 판단 결과를 구조화 저장 없이 휘발성으로만 사용하지 말 것
