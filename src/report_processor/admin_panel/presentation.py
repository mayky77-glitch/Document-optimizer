"""Privacy-safe presentation records for jobs and processing artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path

_ISSUE_PRESENTATION = {
    "UNIT_CONFLICT": ("unit_conflict", "red"),
    "UNCHANGED_VALUE": ("unchanged_value", "yellow"),
    "VALUE_UNCHANGED": ("unchanged_value", "yellow"),
    "NO_VALUE_CHANGE": ("unchanged_value", "yellow"),
    "TOTAL_DISCREPANCY": ("cost_threshold", "orange"),
    "TOLERANCE_EXCEEDED": ("cost_threshold", "orange"),
    "QUANTITY_COST_INCONSISTENT": ("cost_threshold", "orange"),
    "SIGN_CONFLICT": ("cost_threshold", "orange"),
    "NEGATIVE_VALUE": ("cost_threshold", "orange"),
    "HIERARCHY_COST_MISMATCH": ("hierarchy_review", "orange"),
    "HIERARCHY_MISSING_DIRECT_CHILD_COST": ("hierarchy_review", "orange"),
    "HIERARCHY_DUPLICATE_POSITION": ("hierarchy_review", "orange"),
    "HIERARCHY_POSITION_GAP": ("hierarchy_review", "orange"),
    "AMBIGUOUS": ("manual_review", "blue"),
    "UNMATCHED": ("manual_review", "blue"),
}
_DEFAULT_PRESENTATION = ("manual_review", "blue")
_UNCHANGED_CODES = {"UNCHANGED_VALUE", "VALUE_UNCHANGED", "NO_VALUE_CHANGE"}
_ABSOLUTE_PATH = re.compile(r"(?<![\w])(?:/[^\s,;]+|[A-Za-z]:\\[^\s,;]+)")


def job_payload(job: object) -> dict[str, object]:
    """Serialize only frozen, client-facing fields from a job or fake mapping."""

    if isinstance(job, Mapping):
        job_id = _required_text(job.get("job_id"), "job_id")
        status = _required_text(job.get("status"), "status")
        output = {
            "job_id": job_id,
            "stage": _required_text(job.get("stage"), "stage"),
            "status": status,
            "summary": _public_mapping(job.get("summary")),
            "discrepancies": _public_records(job.get("discrepancies")),
            "suggestions": _public_records(job.get("suggestions")),
            "download_url": _download_url(job.get("download_url"), job_id),
        }
        if "mode" in job:
            output["mode"] = _public_text(job.get("mode"))
        if "decisions" in job:
            output["decisions"] = _public_records(job.get("decisions"))
        return output

    job_id = _required_text(getattr(job, "job_id", None), "job_id")
    return {
        "job_id": job_id,
        "stage": _required_text(getattr(job, "stage", None), "stage"),
        "mode": _public_text(getattr(job, "mode", "")),
        "status": _required_text(getattr(job, "status", None), "status"),
        "summary": _public_mapping(getattr(job, "summary", {})),
        "discrepancies": _public_records(getattr(job, "discrepancies", ())),
        "suggestions": _public_records(getattr(job, "suggestions", ())),
        "decisions": _public_records(getattr(job, "decisions", ())),
        "download_url": (
            f"/api/jobs/{job_id}/result" if bool(getattr(job, "result_available", False)) else None
        ),
    }


def processing_presentation(
    result: object,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    """Extract controlled summary, discrepancy and RAG suggestion records."""

    artifacts = getattr(result, "artifacts", {})
    if not isinstance(artifacts, Mapping):
        artifacts = {}
    report = artifacts.get("quality_report")
    summary = _summary_record(getattr(report, "summary", None))
    summary.update(
        {
            "state": _enum_value(getattr(result, "state", "UNKNOWN")),
            "exit_code": _integer(getattr(result, "exit_code", -1)),
            "warning_count": len(tuple(getattr(result, "warnings", ()) or ())),
            "error_count": len(tuple(getattr(result, "errors", ()) or ())),
        }
    )
    discrepancies = [_issue_record(issue) for issue in tuple(getattr(report, "issues", ()) or ())]
    discrepancies.extend(
        _issue_record(issue) for issue in tuple(artifacts.get("hierarchy_issues", ()) or ())
    )
    existing_codes = {str(item["code"]) for item in discrepancies}
    for warning in tuple(getattr(result, "warnings", ()) or ()):
        warning_code = _enum_value(warning).upper()
        if warning_code in _UNCHANGED_CODES and warning_code not in existing_codes:
            discrepancies.append(
                {
                    "discrepancy_id": _controlled_id("warning", warning_code),
                    "code": warning_code,
                    "category": "unchanged_value",
                    "color": "yellow",
                    "severity": "warning",
                    "message": "Исходное значение представлено без изменения.",
                }
            )
        elif warning_code.startswith("HIERARCHY_") and warning_code not in existing_codes:
            discrepancies.append(
                {
                    "discrepancy_id": _controlled_id("warning", warning_code),
                    "code": warning_code,
                    "category": "hierarchy_review",
                    "color": "orange",
                    "severity": "warning",
                    "message": "Иерархия позиций требует проверки перед публикацией.",
                }
            )
    source_labels = _source_labels(artifacts.get("normalized"))
    target_labels = _target_labels(artifacts.get("matches"))
    suggestions = [
        record
        for suggestion in tuple(artifacts.get("stage_relation_suggestions", ()) or ())
        for record in _suggestion_records(suggestion, source_labels, target_labels)
    ]
    if artifacts.get("stage_rag_requires_manual_review") is True and not suggestions:
        discrepancies.append(
            {
                "discrepancy_id": _controlled_id("rag-model-unavailable"),
                "code": "RAG_MODEL_UNAVAILABLE",
                "category": "manual_review",
                "color": "blue",
                "severity": "manual_review",
                "message": "Семантическая связь требует ручной проверки.",
            }
        )
    return summary, discrepancies, suggestions


def journal_payload(job: object) -> bytes:
    """Build a path-free, controlled-ID review journal."""

    payload = job_payload(job)
    payload.pop("download_url", None)
    payload["statement"] = (
        "Решения оператора записаны отдельно и не изменяют авторитетное сопоставление Block 12."
    )
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _summary_record(summary: object) -> dict[str, object]:
    if summary is None:
        return {}
    if is_dataclass(summary):
        return {
            field.name: _public_scalar(getattr(summary, field.name)) for field in fields(summary)
        }
    if isinstance(summary, Mapping):
        return _public_mapping(summary)
    return {}


def _issue_record(issue: object) -> dict[str, object]:
    code = _enum_value(getattr(issue, "code", "MANUAL_REVIEW")).upper()
    category, color = _ISSUE_PRESENTATION.get(code, _DEFAULT_PRESENTATION)
    issue_id = _public_text(getattr(issue, "issue_id", "")) or _controlled_id(
        code, getattr(issue, "message", "")
    )
    record = {
        "discrepancy_id": _controlled_id(issue_id),
        "code": code,
        "category": category,
        "color": color,
        "severity": _enum_value(getattr(issue, "severity", "manual_review")),
        "message": _public_text(getattr(issue, "message", "Требуется проверка.")),
    }
    if code.startswith("HIERARCHY_"):
        # Numbering code is a controlled source identifier needed to repair the workbook.
        record["position_code"] = _public_text(getattr(issue, "position_code", None))
        record["parent_amount"] = _public_scalar(getattr(issue, "parent_amount", None))
        record["direct_children_amount"] = _public_scalar(
            getattr(issue, "direct_children_amount", None)
        )
        record["delta"] = _public_scalar(getattr(issue, "delta", None))
        record["tolerance"] = _public_scalar(getattr(issue, "tolerance", None))
    return record


def _suggestion_records(
    suggestion: object,
    source_labels: Mapping[str, str],
    target_labels: Mapping[str, str],
) -> list[dict[str, object]]:
    target = _public_text(getattr(suggestion, "target_identity", "target"))
    candidates = tuple(getattr(suggestion, "candidates", ()) or ())
    records: list[dict[str, object]] = []
    for candidate in candidates:
        source = _public_text(getattr(candidate, "source_identity", "source"))
        candidate_ref = _controlled_id("candidate", source)
        records.append(
            {
                "suggestion_id": _controlled_id("suggestion", target, source),
                "target_ref": _controlled_id("target", target),
                "target_label": target_labels.get(target, "Целевой этап"),
                "candidate_ref": candidate_ref,
                "candidate_label": source_labels.get(source, "Предложенный этап"),
                "score": _finite_float(getattr(candidate, "score", 0.0)),
                "requires_manual_review": True,
                "auto_accepted": False,
                "effect": "review_journal_only",
            }
        )
    return records


def _source_labels(normalized: object) -> dict[str, str]:
    rows = tuple(getattr(normalized, "rows", ()) or ())
    labels: dict[str, str] = {}
    for row in rows:
        identity = _public_text(getattr(row, "source_row_id", ""))
        label = _public_text(
            getattr(row, "work_name", None)
            or getattr(row, "position_code", None)
            or "Предложенный этап"
        )
        if identity:
            labels[identity] = label
    return labels


def _target_labels(matches: object) -> dict[str, str]:
    rows = tuple(matches or ()) if isinstance(matches, Sequence) else ()
    labels: dict[str, str] = {}
    for match in rows:
        identity = _public_text(getattr(match, "result_id", ""))
        target = getattr(match, "target_row", None)
        label = _public_text(
            getattr(target, "stage", None) or getattr(target, "work_name", None) or "Целевой этап"
        )
        if identity:
            labels[identity] = label
    return labels


def _public_records(value: object) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_public_mapping(item) for item in value if isinstance(item, Mapping)]


def _public_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {
        _public_text(key): _public_value(item)
        for key, item in value.items()
        if isinstance(key, str)
    }


def _public_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _public_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_public_value(item) for item in value]
    return _public_scalar(value)


def _public_scalar(value: object) -> object:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return _finite_float(value)
    if isinstance(value, Path):
        return "[private]"
    return _public_text(_enum_value(value))


def _public_text(value: object, limit: int = 500) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return _ABSOLUTE_PATH.sub("[private]", text)[:limit]


def _required_text(value: object, field_name: str) -> str:
    text = _public_text(value, 200)
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _download_url(value: object, job_id: str) -> str | None:
    expected = f"/api/jobs/{job_id}/result"
    return expected if value == expected else None


def _enum_value(value: object) -> str:
    return str(value.value if isinstance(value, Enum) else value)


def _integer(value: object) -> int:
    raw = value.value if isinstance(value, Enum) else value
    return int(raw) if isinstance(raw, int) else -1


def _finite_float(value: object) -> float:
    number = float(value)
    return number if number == number and abs(number) != float("inf") else 0.0


def _controlled_id(*parts: object) -> str:
    encoded = "\x1f".join(str(part) for part in parts).encode("utf-8", "replace")
    return hashlib.sha256(encoded).hexdigest()[:24]
