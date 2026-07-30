from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from report_processor.domain.statuses import MetadataWarning, RevisionExtractionStatus


@dataclass(frozen=True, slots=True)
class DocumentRevision:
    number: int | None
    label: str | None
    status: str
    is_final: bool
    is_approved: bool
    is_draft: bool


@dataclass(frozen=True, slots=True)
class RevisionExtractionResult:
    value: DocumentRevision | None
    status: str
    candidates: tuple[DocumentRevision, ...]
    warnings: tuple[str, ...] = ()


_REVISION_RE = re.compile(
    r"(?<![а-яa-z0-9])(?:ред(?:акция)?|rev(?:ision)?|версия|v)\s*[.]?\s*(?P<number>\d+)(?!\d)",
    re.IGNORECASE,
)
_FINAL_RE = re.compile(
    r"(?<![а-яa-z])(?:итог|финал|final|окончательн(?:ый|ая|ое)|"
    r"завершенн(?:ый|ая|ое)|завершённ(?:ый|ая|ое))(?![а-яa-z])",
    re.IGNORECASE,
)
_APPROVED_RE = re.compile(
    r"(?<![а-яa-z])(?:согл|согласовано|"
    r"согласованн(?:ый|ая|ое)|approved)(?![а-яa-z])",
    re.IGNORECASE,
)
_DRAFT_RE = re.compile(
    r"(?<![а-яa-z])(?:черновик|draft|"
    r"предварительн(?:ый|ая|ое)|рабоч(?:ий|ая|ее))(?![а-яa-z])",
    re.IGNORECASE,
)


def extract_document_revision(value: object) -> RevisionExtractionResult:
    if value is None:
        return _not_found()
    text = unicodedata.normalize("NFKC", str(value)).replace("ё", "е").lower()
    number_matches = list(_REVISION_RE.finditer(text))
    numbers = tuple(dict.fromkeys(int(match.group("number")) for match in number_matches))
    is_final = bool(_FINAL_RE.search(text))
    is_approved = bool(_APPROVED_RE.search(text))
    is_draft = bool(_DRAFT_RE.search(text))
    marker_conflict = is_draft and (is_final or is_approved)

    if len(numbers) > 1:
        candidates = tuple(
            _build_revision(number, None, is_final, is_approved, is_draft) for number in numbers
        )
        return RevisionExtractionResult(
            value=None,
            status=RevisionExtractionStatus.MULTIPLE_REVISION_CANDIDATES,
            candidates=candidates,
            warnings=(str(MetadataWarning.CONFLICTING_VERSION_MARKERS),) if marker_conflict else (),
        )

    if not numbers and not any((is_final, is_approved, is_draft)):
        return _not_found()

    number = numbers[0] if numbers else None
    label = (
        number_matches[0].group(0)
        if number_matches
        else _status_label(is_final, is_approved, is_draft)
    )
    revision = _build_revision(number, label, is_final, is_approved, is_draft)
    status = (
        RevisionExtractionStatus.CONFLICTING_VERSION_MARKERS
        if marker_conflict
        else RevisionExtractionStatus.OK
    )
    return RevisionExtractionResult(
        value=revision,
        status=status,
        candidates=(revision,),
        warnings=(str(MetadataWarning.CONFLICTING_VERSION_MARKERS),) if marker_conflict else (),
    )


def _build_revision(
    number: int | None,
    label: str | None,
    is_final: bool,
    is_approved: bool,
    is_draft: bool,
) -> DocumentRevision:
    if is_draft and (is_final or is_approved):
        status = "CONFLICTING"
    elif is_final:
        status = "FINAL"
    elif is_approved:
        status = "APPROVED"
    elif is_draft:
        status = "DRAFT"
    elif number is not None:
        status = "NUMBERED"
    else:
        status = "UNSPECIFIED"
    return DocumentRevision(
        number=number,
        label=label,
        status=status,
        is_final=is_final,
        is_approved=is_approved,
        is_draft=is_draft,
    )


def _status_label(is_final: bool, is_approved: bool, is_draft: bool) -> str | None:
    labels = []
    if is_final:
        labels.append("final")
    if is_approved:
        labels.append("approved")
    if is_draft:
        labels.append("draft")
    return "+".join(labels) or None


def _not_found() -> RevisionExtractionResult:
    return RevisionExtractionResult(
        value=None,
        status=RevisionExtractionStatus.REVISION_NOT_FOUND,
        candidates=(),
    )
