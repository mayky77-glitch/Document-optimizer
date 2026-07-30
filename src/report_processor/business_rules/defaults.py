"""Approved baseline M01-M15 records; these are data, not rule subclasses."""

_PILE = "Устройство основания из буроопускных металлических свай"


def default_payload() -> dict[str, object]:
    return {
        "configuration_version": "RuleConfigurationVersion-1.0",
        "rule_set_version": "ValidatedRuleSet-10.0",
        "defaults": {
            "coefficient": "2.7",
            "tolerance": "0.05",
            "quantum": "0.01",
            "rounding": "ROUND_HALF_UP",
            "unit_conversion_enabled": False,
            "source_priority": [
                "hard_exclude",
                "exclusive_ownership",
                "approved_scoped_exact",
                "approved_feedback",
                "baseline_candidate",
                "manual_review",
            ],
        },
        "rules": [
            _rule(
                "M01",
                ("КГС", "ГК"),
                ("Устройство свайных фундаментов",),
                [
                    _exclude("Испытание свай"),
                    _exact(_PILE),
                    _review("Изготовление и монтаж оголовков свай"),
                ],
                True,
            ),
            _rule(
                "M02",
                ("КГС",),
                ("Бетонные работы",),
                [
                    _exclude_contains("железобетон"),
                    _exact(
                        "Армирование и бетонирование монолитных участков из бетона "
                        "(участки из жаростойкого бетона)"
                    ),
                    _exact("Армирование и бетонирование монолитных участков из бетона"),
                    _exact("Бетонирование фундаментов"),
                    _exact("Бетонирование фундаментов общего назначения"),
                ],
            ),
            _rule("M03", ("КГС",), ("Монтаж ТТ и СДТ КГС",), [_prefix("Монтаж ТТ")]),
            _rule(
                "M04",
                ("КГС",),
                ("Прокладка кабеля, провода (Силовые сети) КГС",),
                [
                    _prefix("Прокладка кабеля"),
                    _prefix("Прокладка кабелей"),
                    _prefix("Прокладка провода"),
                    _prefix("Прокладка проводов"),
                ],
            ),
            _rule(
                "M05",
                ("КГС",),
                ("Прокладка кабеля, провода (Слаботочные сети) КГС",),
                [_contains("слаботочн"), _contains("ВОЛС")],
            ),
            _rule(
                "M06",
                ("КГС", "ГК"),
                ("Монтаж металлоконструкций",),
                [
                    _exclude("Монтаж мачт"),
                    _exclude("Изготовление резервуаров"),
                    _prefix("Монтаж м/к фундаментов и ростверков"),
                    _prefix("Монтаж м/к каркасов зданий и сооружений"),
                    _prefix("Монтаж м/к эстакад"),
                    _prefix("Монтаж жалюзийных решеток"),
                ],
                True,
            ),
            _rule("M07", ("ГК",), ("Сварка в нитку",), [_prefix("Сварка на трассе трубопроводов")]),
            _rule(
                "M08",
                ("ГК",),
                ("Укладка", "Укладка трубопроводов"),
                [_prefix("Укладка трубопроводов")],
                True,
            ),
            _rule(
                "M09",
                ("ГК",),
                ("Бетонные работы",),
                [
                    _exact("Бетонирование фундаментов"),
                    _exact("Бетонирование фундаментов общего назначения"),
                ],
                True,
            ),
            _rule(
                "M10",
                ("ГК",),
                ("Обратная засыпка",),
                [_exact("Обратная засыпка траншеи под трубопровод")],
            ),
            _rule(
                "M11",
                ("ГК",),
                ("Разработка траншеи",),
                [_exact("Разработка траншеи под трубопровод")],
            ),
            _rule(
                "M12",
                ("ВЛ",),
                ("Монтаж опор ВЛ",),
                [
                    _prefix("Комплект анкерной концевой опоры"),
                    _exact("Монтаж железобетонных опор ВЛ"),
                ],
            ),
            _rule(
                "M13",
                ("ВЛ",),
                ("Монтаж силового кабеля ВЛ",),
                [_review("Монтаж силового кабеля")],
                True,
            ),
            _rule(
                "M14",
                ("ВЛ",),
                ("Монтаж ВОЛС ВЛ",),
                [_exact("Прокладка самонесущего кабеля ВОЛС по стальным опорам")],
                True,
            ),
            _rule(
                "M15",
                ("ВЛ",),
                ("Устройство свайного основания ВЛ",),
                [
                    _exclude("Испытание свай"),
                    _exact(_PILE),
                    _review("Изготовление и монтаж оголовков свай"),
                ],
                True,
            ),
        ],
    }


def _rule(
    rule_id: str,
    object_scopes: tuple[str, ...],
    targets: tuple[str, ...],
    clauses: list[dict[str, object]],
    exclusive: bool = False,
) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "rule_version": "1",
        "scope": {"object_scopes": list(object_scopes), "target_processes": list(targets)},
        "clauses": clauses,
        "priority": 100,
        "exclusive_owner": exclusive,
        "owner_approved": True,
        "evidence": ["BUSINESS_RULES-v1"],
    }


def _exact(literal: str) -> dict[str, object]:
    return {"action": "include", "match_kind": "exact", "literal": literal}


def _prefix(literal: str) -> dict[str, object]:
    return {"action": "include", "match_kind": "prefix", "literal": literal}


def _contains(literal: str) -> dict[str, object]:
    return {"action": "include", "match_kind": "contains", "literal": literal}


def _review(literal: str) -> dict[str, object]:
    return {"action": "needs_review", "match_kind": "prefix", "literal": literal}


def _exclude(literal: str) -> dict[str, object]:
    return {
        "action": "exclude",
        "match_kind": "prefix",
        "literal": literal,
        "hard_exclude": True,
    }


def _exclude_contains(literal: str) -> dict[str, object]:
    return {
        "action": "exclude",
        "match_kind": "contains",
        "literal": literal,
        "hard_exclude": True,
    }
