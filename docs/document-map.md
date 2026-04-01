# 문서 맵 및 참조 순서

이 프로젝트는 `README.md` 없이 운영한다. 문서 안내와 참조 순서는 이 문서와 `CLAUDE.md`에서 관리한다.

## 문서 역할
- `CLAUDE.md`: Claude Code가 세션 시작 시 먼저 읽어야 하는 핵심 운영 기준서
- `docs/project-contract.md`: 프로젝트 목적, 범위, 입력/출력 계약, 제약조건, 용어 정의
- `docs/workflow-and-agents.md`: 단계별 워크플로우, 상태 전이, 에이전트/스킬 구조
- `docs/output-and-review-files.md`: JSONL/JSON/XLSX/CSV 출력 구조와 사람 검토용 파일 규칙
- `docs/qa-and-validation.md`: QA 원칙, 단계별 검증 기준, QA 승인 조건
- `docs/failure-policy.md`: 재시도, 에스컬레이션, 스킵 정책, 합의 규칙
- `docs/llm-vs-script-boundary.md`: LLM/스크립트/리뷰 대상 경계 규칙
- `docs/omission-check.md`: 원본 설계서 대비 누락 0% 점검표

## 권장 참조 순서
1. `CLAUDE.md`
2. `docs/project-contract.md`
3. `docs/workflow-and-agents.md`
4. `docs/output-and-review-files.md`
5. `docs/qa-and-validation.md`
6. `docs/failure-policy.md`
7. `docs/llm-vs-script-boundary.md`
8. `docs/omission-check.md`
9. `docs/document-map.md`

## 운영 원칙
- README를 별도로 두지 않는다.
- 문서 안내성 정보는 `CLAUDE.md` 또는 `docs/` 문서에 포함한다.
- 새 보조 문서를 추가할 경우 이 문서와 `CLAUDE.md`의 참조 목록을 함께 갱신한다.
