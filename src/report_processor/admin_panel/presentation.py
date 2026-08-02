"""Privacy-safe presentation records for jobs and processing artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path

from .review_presentation import (
    issue_contexts,
    manual_review_groups,
    public_context,
    suggestion_contexts,
    suggestion_review_groups,
)

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
    review_state = getattr(job, "review_state", None)
    if review_state is not None:
        return _authoritative_review_payload(job, review_state)
    source_issues = _source_issues(getattr(job, "source_issues", ()))
    if isinstance(job, Mapping):
        job_id = _required_text(job.get("job_id"), "job_id")
        discrepancies, decisions = (
            _public_records(job.get("discrepancies")),
            _public_records(job.get("decisions")),
        )
        output: dict[str, object] = {
            "job_id": job_id,
            "stage": _required_text(job.get("stage"), "stage"),
            "status": _required_text(job.get("status"), "status"),
            "summary": _public_mapping(job.get("summary")),
            "discrepancies": passive_discrepancies(discrepancies),
            "manual_review_groups": manual_review_groups(discrepancies, decisions),
            "suggestion_review_groups": suggestion_review_groups(
                _public_records(job.get("suggestions")), decisions
            ),
            "suggestions": _public_records(job.get("suggestions")),
            "download_url": _download_url(job.get("download_url"), job_id),
        }
        if "mode" in job:
            output["mode"] = _public_text(job.get("mode"))
        if "decisions" in job:
            output["decisions"] = decisions
        return output
    job_id = _required_text(getattr(job, "job_id", None), "job_id")
    discrepancies = _public_records(getattr(job, "discrepancies", ()))
    decisions = _public_records(getattr(job, "decisions", ()))
    return {
        "job_id": job_id,
        "stage": _required_text(getattr(job, "stage", None), "stage"),
        "mode": _public_text(getattr(job, "mode", "")),
        "status": _required_text(getattr(job, "status", None), "status"),
        "summary": _public_mapping(getattr(job, "summary", {})),
        "discrepancies": passive_discrepancies(discrepancies),
        "manual_review_groups": manual_review_groups(discrepancies, decisions),
        "suggestion_review_groups": suggestion_review_groups(
            _public_records(getattr(job, "suggestions", ())), decisions
        ),
        "suggestions": _public_records(getattr(job, "suggestions", ())),
        "decisions": decisions,
        "download_url": f"/api/jobs/{job_id}/result"
        if bool(getattr(job, "result_available", False))
        else None,
        "source_issues": source_issues,
    }


def _authoritative_review_payload(job: object, state: object) -> dict[str, object]:
    from .reconciliation_batch_presentation import reconciliation_batch_payload
    from .reconciliation_review_presentation import reconciliation_review_payload

    unresolved_groups = state.unresolved_groups()
    groups = reconciliation_review_payload(
        unresolved_groups, state.rows, state.effective_decisions()
    )
    for group in groups:
        members = group.get("members")
        group["display_name"] = (
            members[0].get("display_name")
            if isinstance(members, list) and members
            else "Группа строк"
        )
    payload = {
        "job_id": _required_text(getattr(job, "job_id", None), "job_id"),
        "status": _required_text(getattr(job, "status", None), "status"),
        "review_groups": groups,
        "review_categories": [
            {"category_id": category_id, "label": _public_text(label, 200)}
            for category_id, label in sorted(state.categories.items())
        ],
        "unresolved_review_count": len(unresolved_groups),
        "review_can_apply": not state.unresolved_row_ids(),
        "source_issues": _source_issues(getattr(job, "source_issues", ())),
        "download_url": f"/api/jobs/{job.job_id}/result"
        if bool(getattr(job, "result_available", False))
        else None,
    }
    # ``review_groups`` remains a small compatibility view for the existing
    # controls.  New consumers use the complete package schema below.
    payload.update(reconciliation_batch_payload(state))
    return payload


def _source_issues(values: object) -> list[dict[str, object]]:
    if not isinstance(values, (list, tuple)):
        return []
    result = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        basename = _public_text(value.get("basename"), 200)
        comment = _public_text(value.get("comment"), 240)
        repair_hint = _public_text(value.get("repair_hint"), 240)
        can_continue = value.get("can_continue") is True
        if basename and comment and repair_hint:
            result.append(
                {
                    "basename": basename,
                    "comment": comment,
                    "repair_hint": repair_hint,
                    "can_continue": can_continue,
                }
            )
    return result


def passive_discrepancies(discrepancies: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for item in discrepancies:
        if _public_text(item.get("severity")) == "manual_review":
            continue
        record = dict(item)
        record.pop("discrepancy_id", None)
        key = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        grouped.setdefault(key, {"record": dict(item), "count": 0})["count"] += 1
    output = []
    for key in sorted(grouped):
        record, count = dict(grouped[key]["record"]), int(grouped[key]["count"])
        if count > 1:
            record["count"] = count
        output.append(record)
    return output


def processing_presentation(
    result: object,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
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
    contexts = issue_contexts(artifacts)
    discrepancies = [
        _issue_record(issue, contexts.get(_public_text(getattr(issue, "issue_id", "")), {}))
        for issue in tuple(getattr(report, "issues", ()) or ())
    ]
    discrepancies.extend(
        _issue_record(issue, contexts.get(_public_text(getattr(issue, "issue_id", "")), {}))
        for issue in tuple(artifacts.get("hierarchy_issues", ()) or ())
    )
    existing_codes = {str(item["code"]) for item in discrepancies}
    for warning in tuple(getattr(result, "warnings", ()) or ()):
        code = _enum_value(warning).upper()
        if code in _UNCHANGED_CODES and code not in existing_codes:
            discrepancies.append(
                _warning_record(
                    code,
                    "unchanged_value",
                    "yellow",
                    "Исходное значение представлено без изменения.",
                )
            )
        elif code.startswith("HIERARCHY_") and code not in existing_codes:
            discrepancies.append(
                _warning_record(
                    code,
                    "hierarchy_review",
                    "orange",
                    "Иерархия позиций требует проверки перед публикацией.",
                )
            )
    source_labels, target_labels = (
        _source_labels(artifacts.get("normalized")),
        _target_labels(artifacts.get("matches")),
    )
    contexts = suggestion_contexts(artifacts)
    suggestions = [
        record
        for suggestion in tuple(artifacts.get("stage_relation_suggestions", ()) or ())
        for record in _suggestion_records(suggestion, source_labels, target_labels, contexts)
    ]
    if artifacts.get("stage_rag_requires_manual_review") is True and not suggestions:
        discrepancies.append(
            _warning_record(
                "RAG_MODEL_UNAVAILABLE",
                "manual_review",
                "blue",
                "Семантическая связь требует ручной проверки.",
                severity="manual_review",
            )
        )
    return summary, discrepancies, suggestions


def journal_payload(job: object) -> bytes:
    payload = job_payload(job)
    payload.pop("download_url", None)
    payload["statement"] = (
        "Решения оператора записаны отдельно и не изменяют авторитетное сопоставление Block 12."
    )
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _warning_record(
    code: str, category: str, color: str, message: str, *, severity: str = "warning"
) -> dict[str, object]:
    return {
        "discrepancy_id": _controlled_id("warning", code),
        "code": code,
        "category": category,
        "color": color,
        "severity": severity,
        "message": message,
    }


def _summary_record(summary: object) -> dict[str, object]:
    if is_dataclass(summary):
        return {
            field.name: _public_scalar(getattr(summary, field.name)) for field in fields(summary)
        }
    return _public_mapping(summary) if isinstance(summary, Mapping) else {}


def _issue_record(issue: object, context: Mapping[str, object]) -> dict[str, object]:
    code = _enum_value(getattr(issue, "code", "MANUAL_REVIEW")).upper()
    category, color = _ISSUE_PRESENTATION.get(code, _DEFAULT_PRESENTATION)
    issue_id = _public_text(getattr(issue, "issue_id", "")) or _controlled_id(
        code, getattr(issue, "message", "")
    )
    record: dict[str, object] = {
        "discrepancy_id": _controlled_id(issue_id),
        "code": code,
        "category": category,
        "color": color,
        "severity": _enum_value(getattr(issue, "severity", "manual_review")),
        "message": _public_text(getattr(issue, "message", "Требуется проверка.")),
    }
    if context:
        record["context"] = public_context(context)
    return record


def _suggestion_records(
    suggestion: object,
    source_labels: Mapping[str, str],
    target_labels: Mapping[str, str],
    contexts: Mapping[tuple[str, str], Mapping[str, object]],
) -> list[dict[str, object]]:
    target = _public_text(getattr(suggestion, "target_identity", "target"))
    return [
        {
            "suggestion_id": _controlled_id("suggestion", target, source),
            "target_ref": _controlled_id("target", target),
            "target_label": target_labels.get(target, "Целевой этап"),
            "candidate_ref": _controlled_id("candidate", source),
            "candidate_label": source_labels.get(source, "Предложенный этап"),
            "score": _finite_float(getattr(candidate, "score", 0.0)),
            "requires_manual_review": True,
            "auto_accepted": False,
            "effect": "review_journal_only",
            "context": public_context(contexts.get((target, source), {})),
        }
        for candidate in tuple(getattr(suggestion, "candidates", ()) or ())
        if (source := _public_text(getattr(candidate, "source_identity", "source")))
    ]


def _source_labels(normalized: object) -> dict[str, str]:
    return {
        _public_text(getattr(row, "source_row_id", "")): _public_text(
            getattr(row, "work_name", None)
            or getattr(row, "position_code", None)
            or "Предложенный этап"
        )
        for row in tuple(getattr(normalized, "rows", ()) or ())
        if _public_text(getattr(row, "source_row_id", ""))
    }


def _target_labels(matches: object) -> dict[str, str]:
    return {
        _public_text(getattr(match, "result_id", "")): _public_text(
            getattr(getattr(match, "target_row", None), "stage", None)
            or getattr(getattr(match, "target_row", None), "work_name", None)
            or "Целевой этап"
        )
        for match in (tuple(matches or ()) if isinstance(matches, Sequence) else ())
        if _public_text(getattr(match, "result_id", ""))
    }


def _public_records(value: object) -> list[dict[str, object]]:
    return (
        [_public_mapping(item) for item in value if isinstance(item, Mapping)]
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
        else []
    )


def _public_mapping(value: object) -> dict[str, object]:
    return (
        {
            _public_text(key): _public_value(item)
            for key, item in value.items()
            if isinstance(key, str)
        }
        if isinstance(value, Mapping)
        else {}
    )


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
    return _ABSOLUTE_PATH.sub("[private]", str(value or "").replace("\x00", "").strip())[:limit]


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
    value = value.value if isinstance(value, Enum) else value
    return int(value) if isinstance(value, int) else -1


def _finite_float(value: object) -> float:
    number = float(value)
    return number if number == number and abs(number) != float("inf") else 0.0


def _controlled_id(*parts: object) -> str:
    return hashlib.sha256(
        "\x1f".join(str(part) for part in parts).encode("utf-8", "replace")
    ).hexdigest()[:24]
