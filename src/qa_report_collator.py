"""
Step 12 — QA report collator (script side).

Claude Code 세션이 QA 판정 파일을 직접 작성한 후
이 모듈이 최종 QA 리포트를 조립한다.

Claude Code가 작성하는 QA 판정 파일 (output/qa/ 디렉토리):
  qa_recall_findings.jsonl    — recall-auditor-01/02 결과
  qa_noise_findings.jsonl     — noise-auditor-01/02 결과
  qa_semantic_findings.jsonl  — semantic-auditor-01/02 결과
  qa_output_findings.jsonl    — output-auditor-01/02 결과
  qa_chief_verdict.json       — qa-chief-reviewer 최종 판정

이 모듈이 생성하는 최종 파일:
  output/qa/qa_report.json
  output/qa/qa_findings.jsonl
  output/qa/qa_disagreements.jsonl
  output/qa/qa_human_review.xlsx
"""

import datetime
import json
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from config import (
    OUT_QA_DISAGREEMENTS,
    OUT_QA_FINDINGS,
    OUT_QA_HUMAN_REVIEW_XLSX,
    OUT_QA_REPORT,
    QA_DIR,
    PIPELINE_VERSION,
)
from utils import get_logger, read_jsonl, write_json, write_jsonl

log = get_logger("qa_report_collator")

# ---------------------------------------------------------------------------
# QA 판정 파일 경로 (Claude Code 세션이 직접 작성)
# ---------------------------------------------------------------------------

QA_RECALL_FILE = QA_DIR / "qa_recall_findings.jsonl"
QA_NOISE_FILE = QA_DIR / "qa_noise_findings.jsonl"
QA_SEMANTIC_FILE = QA_DIR / "qa_semantic_findings.jsonl"
QA_OUTPUT_FILE = QA_DIR / "qa_output_findings.jsonl"
QA_CHIEF_FILE = QA_DIR / "qa_chief_verdict.json"


# ---------------------------------------------------------------------------
# Collator
# ---------------------------------------------------------------------------

def _load_findings(path: Path, audit_type: str) -> list[dict]:
    if not path.exists():
        log.warning("QA findings file not found: %s", path)
        return []
    records = read_jsonl(path)
    for r in records:
        r.setdefault("audit_type", audit_type)
    log.info("  Loaded %d %s findings", len(records), audit_type)
    return records


def _load_chief_verdict() -> dict:
    if not QA_CHIEF_FILE.exists():
        log.warning("Chief verdict file not found: %s", QA_CHIEF_FILE)
        return {
            "qa_verdict": "unknown",
            "top_findings": [],
            "recommendations": ["Chief verdict file missing — run QA judgment first"],
            "critical_count": 0,
            "warning_count": 0,
            "info_count": 0,
        }
    with open(QA_CHIEF_FILE, encoding="utf-8") as f:
        return json.load(f)


def _write_human_review(all_findings: list[dict], report: dict) -> None:
    wb = openpyxl.Workbook()

    _HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    _HEADER_FONT = Font(color="FFFFFF", bold=True)

    # Sheet 1 — all findings
    ws_f = wb.active
    ws_f.title = "qa_findings"
    cols = ["auditor", "audit_type", "word", "issue",
            "argument", "severity", "current_label", "suggested_label", "detail"]
    ws_f.append(cols)
    for row in all_findings:
        ws_f.append([str(row.get(c, "")) for c in cols])
    for cell in ws_f[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
    ws_f.freeze_panes = "A2"
    ws_f.auto_filter.ref = ws_f.dimensions

    # Sheet 2 — qa_report summary
    ws_r = wb.create_sheet("qa_report")
    ws_r.append(["Key", "Value"])
    for cell in ws_r[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
    for k, v in report.items():
        ws_r.append([k, json.dumps(v) if isinstance(v, (list, dict)) else v])
    ws_r.column_dimensions["A"].width = 30
    ws_r.column_dimensions["B"].width = 60

    OUT_QA_HUMAN_REVIEW_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_QA_HUMAN_REVIEW_XLSX)
    log.info("Wrote %s", OUT_QA_HUMAN_REVIEW_XLSX)


def run() -> None:
    """
    Assemble all QA judgment files written by Claude Code session
    into the final QA output files.
    """
    log.info("Collecting QA findings …")

    recall_findings   = _load_findings(QA_RECALL_FILE,   "recall")
    noise_findings    = _load_findings(QA_NOISE_FILE,    "noise")
    semantic_findings = _load_findings(QA_SEMANTIC_FILE, "semantic")
    output_findings   = _load_findings(QA_OUTPUT_FILE,   "output")

    all_findings = recall_findings + noise_findings + semantic_findings + output_findings

    disagreements = [
        f for f in all_findings
        if f.get("severity") in ("medium", "high")
    ]

    chief_verdict = _load_chief_verdict()

    qa_report = {
        "pipeline_version": PIPELINE_VERSION,
        "qa_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "total_findings": len(all_findings),
        "total_disagreements": len(disagreements),
        "finding_breakdown": {
            "recall":   len(recall_findings),
            "noise":    len(noise_findings),
            "semantic": len(semantic_findings),
            "output":   len(output_findings),
        },
        **chief_verdict,
    }

    write_jsonl(OUT_QA_FINDINGS, all_findings)
    write_jsonl(OUT_QA_DISAGREEMENTS, disagreements)
    write_json(OUT_QA_REPORT, qa_report)
    _write_human_review(all_findings, qa_report)

    log.info(
        "QA report complete: verdict=%s  findings=%d  disagreements=%d",
        chief_verdict.get("qa_verdict", "?"),
        len(all_findings),
        len(disagreements),
    )
