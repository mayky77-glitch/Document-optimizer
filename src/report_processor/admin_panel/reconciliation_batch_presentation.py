"""Privacy-safe public projection of reconciliation decision packages."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .reconciliation_review_presentation import reconciliation_review_group_payload
from .reconciliation_state import ReconciliationReviewState


def reconciliation_batch_payload(state: ReconciliationReviewState) -> dict[str, object]:
    """Shape only opaque IDs, controlled group values and short Russian strings."""
    packages = []
    families = (
        {family.family_id: family for family in state.grouping.families} if state.grouping else {}
    )
    for package in state.grouping.packages if state.grouping else ():
        direct = state.package_decisions.get(package.package_id)
        package_groups = _groups(state, package.member_group_ids)
        manually_changed = _manually_changed(state, package.member_group_ids)
        has_exceptions = bool(package.exception_reasons)
        category = package.package_key[0] or None
        queue = _queue(package.safe, category)
        family_payloads = [
            _family_payload(state, families[family_id]) for family_id in package.family_ids
        ]
        packages.append(
            {
                "package_id": package.package_id,
                "version": package.version,
                "queue": queue,
                "label": _package_label(queue),
                "proposed_category_id": category,
                "selected_category_id": direct.target_category if direct else None,
                "action": direct.action.value if direct else None,
                "mode": direct.mode.value if direct and direct.mode else package.package_key[1],
                "family_count": _number(len(package.family_ids)),
                "group_count": _number(len(package.member_group_ids)),
                "row_count": _number(sum(len(group.member_ids) for group in package_groups)),
                "exception_count": _number(len(package.exception_reasons)),
                "quantity": _total(state, package.member_group_ids, "quantity"),
                "cost": _total(state, package.member_group_ids, "cost"),
                "reason": _package_reason(queue),
                "safe": package.safe,
                "category": category,
                "unit_family": package.package_key[2],
                "package_size": _number(sum(len(group.member_ids) for group in package_groups)),
                "has_exceptions": has_exceptions,
                "ready_for_mass_accept": package.safe
                and not manually_changed
                and category is not None,
                "manually_changed": manually_changed,
                "is_familiar": any(
                    group_id in state.familiar_group_ids for group_id in package.member_group_ids
                ),
                "suspicious": has_exceptions,
                "families": family_payloads,
            }
        )
    return {
        "review_packages": packages,
        "review_summary": {
            "package_count": _number(len(packages)),
            "group_count": _number(len(state.groups)),
            "row_count": _number(len(state.rows)),
            "unresolved_count": _number(len(state.unresolved_row_ids())),
        },
        "review_categories": [
            {"category_id": category_id, "label": str(label)[:200]}
            for category_id, label in sorted(state.categories.items())
        ],
        "review_can_apply": not state.unresolved_row_ids(),
        "review_last_action": {"message": state.last_action or "Решения не сохранены."},
    }


def _family_payload(state: ReconciliationReviewState, family) -> dict[str, object]:
    decision = state.family_decisions.get(family.family_id)
    groups = _groups(state, family.member_group_ids)
    return {
        "family_id": family.family_id,
        "version": family.version,
        "label": "Семейство работ",
        "member_group_ids": list(family.member_group_ids),
        "groups": [
            reconciliation_review_group_payload(group, state.rows, state.effective_decisions())
            for group in groups
        ],
        "selected_category_id": decision.target_category if decision else None,
        "action": decision.action.value if decision else None,
        "mode": decision.mode.value if decision and decision.mode else None,
    }


def _groups(state: ReconciliationReviewState, group_ids: tuple[str, ...]):
    return tuple(state.groups[group_id] for group_id in group_ids)


def _total(state: ReconciliationReviewState, group_ids: tuple[str, ...], field: str) -> str:
    row_ids = (row_id for group_id in group_ids for row_id in state.groups[group_id].member_ids)
    value = sum((getattr(state.rows[row_id], field) or Decimal("0")) for row_id in row_ids)
    return _decimal(value)


def _decimal(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _number(value: int) -> str:
    return _decimal(Decimal(value))


def _package_label(queue: str) -> str:
    if queue == "safe":
        return "Пакет для применения"
    if queue == "new":
        return "Новый вид работ"
    return "Пакет для ручной проверки"


def _package_reason(queue: str) -> str:
    if queue == "safe":
        return "Ограничения соблюдены."
    if queue == "new":
        return "Категория для работы не определена."
    return "Требуется отдельное решение оператора."


def _queue(safe: bool, category: str | None) -> str:
    if category is None:
        return "new"
    return "safe" if safe else "clarify"


def _manually_changed(state: ReconciliationReviewState, group_ids: tuple[str, ...]) -> bool:
    row_ids = {row_id for group_id in group_ids for row_id in state.groups[group_id].member_ids}
    family_ids = {
        family.family_id
        for family in state.grouping.families
        if state.grouping is not None
        if set(family.member_group_ids).intersection(group_ids)
    }
    return bool(
        set(group_ids).intersection(state.group_decisions)
        or row_ids.intersection(state.row_decisions)
        or family_ids.intersection(state.family_decisions)
    )
