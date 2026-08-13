"""Starlette-compatible local app factory."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from inspect import Parameter, signature
from pathlib import Path
from urllib.parse import quote

from .drawing_card_presentation import (
    drawing_card_cluster_review_page,
    drawing_card_inline_review_page,
    drawing_card_job_payload,
)
from .drawing_card_service import (
    MAX_SOURCES as DRAWING_CARD_MAX_SOURCES,
)
from .drawing_card_service import (
    MAX_UPLOAD_BYTES as DRAWING_CARD_MAX_UPLOAD_BYTES,
)
from .drawing_card_service import (
    DrawingCardPersistenceError,
    DrawingCardService,
)
from .package_reconciliation_service import (
    MAX_PACKAGE_FILES,
    MAX_PACKAGE_UPLOAD_BYTES,
    PackageReconciliationService,
)
from .presentation import job_payload, stage_selection_payload
from .reconciliation_review_routes import reconciliation_review_routes
from .review_api import (
    ReviewRequestError,
    parse_manual_discrepancy_decision,
    parse_suggestion_decision,
)
from .service import (
    MAX_SOURCES as ADMIN_MAX_SOURCES,
)
from .service import (
    MAX_UPLOAD_BYTES,
    AdminPanelService,
    TargetStageSelectionError,
    validate_mode,
    validate_operation,
    validate_stage,
    validate_workbook_upload,
)
from .view import (
    drawing_card_page,
    help_page,
    index_page,
    package_reconciliation_page,
    static_asset,
)

_SAFE_DOWNLOAD_NAME = re.compile(r"[^\w. -]+", re.UNICODE)
_WORKBOOK_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_XLSM_MEDIA_TYPE = "application/vnd.ms-excel.sheet.macroEnabled.12"
_ZIP_MEDIA_TYPE = "application/zip"
_DRAWING_CARD_UPLOAD_ERRORS = {
    "combined upload is too large": "Общий размер загружаемых файлов превышает допустимый предел",
    "existing card is only valid for update": (
        "Файл существующей карточки допустим только при обновлении"
    ),
    "invalid filename": "Недопустимое имя загружаемого файла",
    "invalid operation": "Выбран недопустимый режим операции",
    "invalid idempotency key": "Повторите отправку формы из этой страницы",
    "idempotency key conflicts with another request": (
        "Повтор отправки относится к другому набору файлов. Выберите файлы заново"
    ),
    "invalid period": "Некорректный период",
    "invalid source count": "Загрузите от 1 до 32 исходных Excel-файлов",
    "invalid workbook content": "Файл не является корректной Excel-книгой",
    "missing upload": "Не выбран файл для загрузки",
    "mode must be create or update": "Выбран недопустимый режим операции",
    "request body is too large": "Размер запроса превышает допустимый предел",
    "unsupported workbook type": (
        "Неподдерживаемый тип файла. Загрузите Excel-файл (.xlsx, .xlsm или .xlsb)"
    ),
    "update requires an existing .xlsx drawing card": (
        "Для обновления загрузите существующую карточку Excel"
    ),
    "upload size is invalid": "Размер файла должен быть в допустимых пределах",
}
_DRAWING_CARD_UPLOAD_FALLBACK = "Проверьте исходные Excel-файлы и выбранную операцию"


def create_app(
    service=None,
    workspace_root=None,
    drawing_card_service=None,
    package_reconciliation_service=None,
):
    """Return the frozen local panel API without starting a server."""

    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, JSONResponse, Response
    from starlette.routing import Route

    workspace = (
        Path(workspace_root) if workspace_root is not None else Path.cwd() / ".admin-panel-jobs"
    )
    panel = service or AdminPanelService(workspace)
    drawing_panel = drawing_card_service or DrawingCardService(
        workspace / "drawing-card", background=True
    )
    package_panel = package_reconciliation_service or PackageReconciliationService(
        workspace / "package-reconciliation"
    )

    async def index(request):
        del request
        return _secure(HTMLResponse(index_page()))

    async def static(request):
        try:
            media_type, content = static_asset(request.path_params["path"])
        except (KeyError, OSError):
            return _error("Ресурс не найден", 404)
        return _secure(Response(content, media_type=media_type))

    async def drawing_card_index(request):
        del request
        return _secure(HTMLResponse(drawing_card_page()))

    async def package_reconciliation_index(request):
        del request
        try:
            return _secure(HTMLResponse(package_reconciliation_page()))
        except OSError:
            return _error("Ресурс не найден", 404)

    async def help_index(request):
        del request
        try:
            return _secure(HTMLResponse(help_page()))
        except OSError:
            return _error("Ресурс не найден", 404)

    async def package_reconciliation_upload(request):
        try:
            _validate_content_length(
                request.headers.get("content-length"),
                maximum=MAX_PACKAGE_UPLOAD_BYTES + 1024 * 1024,
            )
            async with request.form(
                max_files=MAX_PACKAGE_FILES,
                max_fields=0,
                max_part_size=MAX_PACKAGE_UPLOAD_BYTES + 1,
            ) as form:
                uploads = list(form.getlist("files"))
                files = []
                for item in uploads:
                    upload = _upload_value(item)
                    content = await _read_upload(upload, maximum=MAX_PACKAGE_UPLOAD_BYTES)
                    files.append((upload.filename, content))
            from anyio import to_thread

            current = await to_thread.run_sync(lambda: package_panel.create_job(files=files))
            payload = package_panel.payload_for(current.job_id)
        except (KeyError, OSError, TypeError, ValueError):
            return _error("Проверьте состав папки и таблицы (.xlsx, .xlsm, .ods)", 400)
        return _secure(JSONResponse(payload, status_code=201))

    async def package_reconciliation_job(request):
        try:
            payload = package_panel.payload_for(request.path_params["job_id"])
        except KeyError:
            return _error("Задача не найдена", 404)
        except (TypeError, ValueError):
            return _error("Состояние задачи недоступно", 500)
        return _secure(JSONResponse(payload))

    async def package_reconciliation_result(request):
        try:
            path, filename = package_panel.get_result(request.path_params["job_id"])
            content = _bounded_result(Path(path))
        except KeyError:
            return _error("Результат пока недоступен", 404)
        except (OSError, TypeError, ValueError):
            return _error("Результат недоступен", 409)
        return _secure(
            Response(
                content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="{_safe_download_name(filename)}"'
                },
            )
        )

    async def upload(request):
        try:
            _validate_content_length(request.headers.get("content-length"))
            async with request.form(
                max_files=ADMIN_MAX_SOURCES + 1,
                max_fields=3,
                max_part_size=MAX_UPLOAD_BYTES + 1,
            ) as form:
                source_uploads = list(form.getlist("sources"))
                legacy_source = not source_uploads and form.get("source") is not None
                if legacy_source:
                    source_uploads = [form.get("source")]
                if not 1 <= len(source_uploads) <= ADMIN_MAX_SOURCES:
                    raise ValueError("invalid source count")
                target = _upload_part(form, "target")
                sources: list[tuple[str, bytes]] = []
                combined_size = 0
                for source_item in source_uploads:
                    source = _upload_value(source_item)
                    source_content = await _read_upload(source)
                    validate_workbook_upload(source.filename, source_content)
                    combined_size += len(source_content)
                    sources.append((source.filename, source_content))
                target_content = await _read_upload(target)
                combined_size += len(target_content)
                if combined_size > MAX_UPLOAD_BYTES:
                    raise ValueError("combined upload is too large")
                validate_workbook_upload(target.filename, target_content)
                stage_value = form.get("stage")
                stage = validate_stage(stage_value) if stage_value is not None else None
                mode = validate_mode(form.get("mode", "write"))
                operation = validate_operation(form.get("operation", "reconcile"))
                operation_kwargs = {"operation": operation} if operation != "reconcile" else {}
                if legacy_source:
                    job = panel.create_job(
                        source_name=sources[0][0],
                        source_content=sources[0][1],
                        target_name=target.filename,
                        target_content=target_content,
                        stage=stage,
                        mode=mode,
                        validate_target_stage=True,
                        **operation_kwargs,
                    )
                else:
                    job = panel.create_job(
                        sources=sources,
                        target_name=target.filename,
                        target_content=target_content,
                        stage=stage,
                        mode=mode,
                        validate_target_stage=True,
                        **operation_kwargs,
                    )
        except TargetStageSelectionError as error:
            payload = stage_selection_payload(error.code, error.stage_options)
            return _secure(
                JSONResponse(
                    payload,
                    status_code=409 if error.code == "selection_required" else 400,
                )
            )
        except (KeyError, TypeError, ValueError):
            return _error("Проверьте исходные книги и отчёт, этап и режим", 400)
        return _secure(JSONResponse(job_payload(job), status_code=201))

    async def drawing_card_periods(request):
        try:
            _validate_content_length(
                request.headers.get("content-length"),
                maximum=DRAWING_CARD_MAX_UPLOAD_BYTES + 1024 * 1024,
            )
            async with request.form(
                max_files=DRAWING_CARD_MAX_SOURCES,
                max_fields=0,
                max_part_size=DRAWING_CARD_MAX_UPLOAD_BYTES + 1,
            ) as form:
                uploads = list(form.getlist("sources"))
                if not 1 <= len(uploads) <= DRAWING_CARD_MAX_SOURCES:
                    raise ValueError("invalid source count")
                sources = []
                combined_size = 0
                for upload_item in uploads:
                    upload = _upload_value(upload_item)
                    content = await _read_upload(
                        upload,
                        maximum=DRAWING_CARD_MAX_UPLOAD_BYTES,
                    )
                    combined_size += len(content)
                    sources.append((upload.filename, content))
                if combined_size > DRAWING_CARD_MAX_UPLOAD_BYTES:
                    raise ValueError("combined upload is too large")
                values = drawing_panel.discover_periods(sources)
        except (KeyError, OSError, TypeError, ValueError) as error:
            return _error(_drawing_card_upload_error(error), 400)
        periods = [{"value": value, "label": _period_label(value)} for value in values]
        return _secure(
            JSONResponse(
                {
                    "periods": periods,
                    "latest": values[-1] if values else None,
                }
            )
        )

    async def get_job(request):
        try:
            current = panel.get_job(request.path_params["job_id"])
        except KeyError:
            return _error("Задача не найдена", 404)
        try:
            payload = job_payload(current)
        except (TypeError, ValueError):
            return _error("Состояние задачи недоступно", 500)
        return _secure(JSONResponse(payload))

    async def decision(request):
        try:
            payload = await request.json()
        except ValueError:
            return _error("Ожидается JSON с решением", 400)
        try:
            review_request = parse_suggestion_decision(payload)
        except ReviewRequestError as error:
            return _error(str(error), 400)
        if review_request.is_group_decision:
            try:
                current = panel.record_suggestion_group_decision(
                    job_id=request.path_params["job_id"],
                    group_id=review_request.group_id,
                    suggestion_id=review_request.suggestion_id,
                    decision=review_request.decision,
                )
            except KeyError:
                return _error("Задача не найдена", 404)
            except (TypeError, ValueError):
                return _error("Решение не относится к открытой группе подсказок", 400)
            return _secure(JSONResponse(job_payload(current)))
        try:
            current = panel.record_decision(
                job_id=request.path_params["job_id"],
                suggestion_id=review_request.suggestion_id,
                decision=review_request.decision,
            )
        except KeyError:
            return _error("Задача не найдена", 404)
        except (TypeError, ValueError):
            return _error("Решение не относится к открытой рекомендации", 400)
        return _secure(JSONResponse(job_payload(current)))

    async def manual_discrepancy_decision(request):
        try:
            payload = await request.json()
        except ValueError:
            return _error("Ожидается JSON с решением", 400)
        try:
            review_request = parse_manual_discrepancy_decision(payload)
        except ReviewRequestError as error:
            return _error(str(error), 400)
        try:
            current = panel.record_manual_discrepancy_decision(
                job_id=request.path_params["job_id"],
                group_id=review_request.group_id,
                discrepancy_ids=review_request.discrepancy_ids,
                decision=review_request.decision,
            )
        except KeyError:
            return _error("Задача не найдена", 404)
        except (TypeError, ValueError):
            return _error("Решение не относится к открытой группе замечаний", 400)
        return _secure(JSONResponse(job_payload(current)))

    async def download(request):
        try:
            path, filename = panel.get_result(request.path_params["job_id"])
            content = _bounded_result(Path(path))
        except KeyError:
            return _error("Результат пока недоступен", 404)
        except (OSError, TypeError, ValueError):
            return _error("Результат недоступен", 409)
        safe_name = _safe_download_name(filename)
        media_type = _result_media_type(safe_name)
        return _secure(
            Response(
                content,
                media_type=media_type,
                headers={"Content-Disposition": _content_disposition(safe_name)},
            )
        )

    async def drawing_card_upload(request):
        try:
            _validate_content_length(
                request.headers.get("content-length"),
                maximum=DRAWING_CARD_MAX_UPLOAD_BYTES + 1024 * 1024,
            )
            async with request.form(
                max_files=DRAWING_CARD_MAX_SOURCES + 1,
                max_fields=3,
                max_part_size=DRAWING_CARD_MAX_UPLOAD_BYTES + 1,
            ) as form:
                uploads = list(form.getlist("sources"))
                if not 1 <= len(uploads) <= DRAWING_CARD_MAX_SOURCES:
                    raise ValueError("invalid source count")
                sources = []
                combined_size = 0
                for upload_item in uploads:
                    upload = _upload_value(upload_item)
                    content = await _read_upload(upload, maximum=DRAWING_CARD_MAX_UPLOAD_BYTES)
                    combined_size += len(content)
                    sources.append((upload.filename, content))
                operation = form.get("operation", "create")
                if operation not in {"create", "update"}:
                    raise ValueError("invalid operation")
                existing_name = None
                existing_content = None
                existing_item = form.get("existing_card")
                if operation == "update":
                    existing = _upload_value(existing_item)
                    existing_name = existing.filename
                    existing_content = await _read_upload(
                        existing, maximum=DRAWING_CARD_MAX_UPLOAD_BYTES
                    )
                    combined_size += len(existing_content)
                elif getattr(existing_item, "filename", ""):
                    raise ValueError("existing card is only valid for update")
                if combined_size > DRAWING_CARD_MAX_UPLOAD_BYTES:
                    raise ValueError("combined upload is too large")
                period_item = form.get("period")
                period = None
                if isinstance(period_item, str):
                    period = period_item.strip() or None
                current = drawing_panel.create_job(
                    sources=sources,
                    mode=operation,
                    existing_name=existing_name,
                    existing_content=existing_content,
                    period=period,
                    idempotency_key=request.headers.get("idempotency-key"),
                )
        except DrawingCardPersistenceError:
            return _error("Не удалось надёжно сохранить новую задачу", 503)
        except (KeyError, OSError, TypeError, ValueError) as error:
            return _error(_drawing_card_upload_error(error), 400)
        return _secure(JSONResponse(drawing_card_job_payload(current), status_code=201))

    async def drawing_card_get_job(request):
        try:
            current = drawing_panel.get_job(request.path_params["job_id"])
            payload = drawing_card_job_payload(current)
        except KeyError:
            return _error("Задача не найдена", 404)
        except (TypeError, ValueError):
            return _error("Состояние задачи недоступно", 500)
        return _secure(JSONResponse(payload))

    async def drawing_card_cancel(request):
        try:
            current = drawing_panel.cancel_job(job_id=request.path_params["job_id"])
        except KeyError:
            return _error("Задача не найдена", 404)
        except DrawingCardPersistenceError:
            return _error("Не удалось сохранить отмену задачи", 503)
        except ValueError:
            return _error("Эту задачу уже нельзя отменить", 409)
        return _secure(JSONResponse(drawing_card_job_payload(current), status_code=202))

    async def drawing_card_retry(request):
        try:
            current = drawing_panel.retry_job(job_id=request.path_params["job_id"])
        except KeyError:
            return _error("Задача не найдена", 404)
        except DrawingCardPersistenceError:
            return _error("Не удалось сохранить повторный запуск", 503)
        except ValueError:
            return _error("Повторный запуск для этой задачи сейчас недоступен", 409)
        return _secure(JSONResponse(drawing_card_job_payload(current), status_code=202))

    async def drawing_card_exclusion_audit(request):
        try:
            page = int(request.query_params.get("page", "1"))
            page_size = int(request.query_params.get("page_size", "100"))
            payload = drawing_panel.list_exclusion_audit(
                job_id=request.path_params["job_id"], page=page, page_size=page_size
            )
        except KeyError:
            return _error("Аудит исключений недоступен", 404)
        except (TypeError, ValueError):
            return _error("Проверьте номер страницы аудита", 400)
        return _secure(JSONResponse(payload))

    async def drawing_card_result(request):
        return _drawing_card_download(
            drawing_panel,
            request.path_params["job_id"],
            kind="result",
        )

    async def drawing_card_review(request):
        if request.method == "GET":
            return _drawing_card_download(
                drawing_panel,
                request.path_params["job_id"],
                kind="review",
            )
        try:
            _validate_content_length(
                request.headers.get("content-length"),
                maximum=DRAWING_CARD_MAX_UPLOAD_BYTES + 1024 * 1024,
            )
            async with request.form(
                max_files=1,
                max_fields=0,
                max_part_size=DRAWING_CARD_MAX_UPLOAD_BYTES + 1,
            ) as form:
                review = _upload_part(form, "review")
                review_content = await _read_upload(review, maximum=DRAWING_CARD_MAX_UPLOAD_BYTES)
                current = drawing_panel.apply_review(
                    job_id=request.path_params["job_id"],
                    review_name=review.filename,
                    review_content=review_content,
                )
        except KeyError:
            return _error("Задача не найдена", 404)
        except DrawingCardPersistenceError:
            return _error("Не удалось надёжно сохранить состояние задачи", 503)
        except (OSError, TypeError, ValueError):
            return _error("Проверьте заполненный файл проверки", 400)
        return _secure(JSONResponse(drawing_card_job_payload(current)))

    async def drawing_card_review_items(request):
        try:
            page = int(request.query_params.get("page", "1"))
            page_size = int(request.query_params.get("page_size", "50"))
            payload = drawing_panel.list_review_items(
                job_id=request.path_params["job_id"],
                page=page,
                page_size=page_size,
            )
            current = drawing_panel.get_job(request.path_params["job_id"])
        except KeyError:
            return _error("Задача не найдена", 404)
        except (TypeError, ValueError):
            return _error("Проверьте номер страницы и размер списка", 400)
        return _secure(JSONResponse(drawing_card_inline_review_page(payload, current)))

    async def drawing_card_review_clusters(request):
        try:
            page = int(request.query_params.get("page", "1"))
            page_size = int(request.query_params.get("page_size", "50"))
            filters = _drawing_card_review_filters(request.query_params)
            payload = _call_review_clusters(
                drawing_panel,
                job_id=request.path_params["job_id"],
                page=page,
                page_size=page_size,
                **filters,
            )
        except KeyError:
            return _error("Задача не найдена", 404)
        except (TypeError, ValueError):
            return _error("Проверьте номер страницы и размер списка", 400)
        return _secure(JSONResponse(drawing_card_cluster_review_page(payload)))

    async def drawing_card_review_cluster(request):
        job_id = request.path_params["job_id"]
        cluster_id = request.path_params["cluster_id"]
        try:
            if request.method == "DELETE":
                version = request.query_params.get("version")
                if not isinstance(version, str):
                    payload = await request.json()
                    version = payload.get("version") if isinstance(payload, Mapping) else None
                if not isinstance(version, str):
                    raise ValueError("invalid cluster action")
                current = drawing_panel.undo_review_cluster(
                    job_id=job_id, cluster_id=cluster_id, version=version
                )
            else:
                payload = await request.json()
                if not isinstance(payload, Mapping):
                    raise ValueError("invalid cluster action")
                action = payload.get("action")
                category = payload.get("category")
                version = payload.get("version")
                if (
                    not isinstance(action, str)
                    or not isinstance(version, str)
                    or (category is not None and not isinstance(category, str))
                ):
                    raise ValueError("invalid cluster action")
                current = drawing_panel.put_review_cluster(
                    job_id=job_id,
                    cluster_id=cluster_id,
                    version=version,
                    action=action,
                    category=category,
                )
        except KeyError:
            return _error("Задача не найдена", 404)
        except DrawingCardPersistenceError:
            return _error("Решения не сохранены. Повторите действие", 503)
        except (TypeError, ValueError):
            return _error("Кластер изменился — обновите список и повторите действие", 409)
        return _secure(JSONResponse(drawing_card_job_payload(current)))

    async def drawing_card_review_item(request):
        job_id = request.path_params["job_id"]
        review_id = request.path_params["review_id"]
        try:
            if request.method == "DELETE":
                current = drawing_panel.delete_review_item(
                    job_id=job_id,
                    review_id=review_id,
                )
            else:
                payload = await request.json()
                if not isinstance(payload, Mapping):
                    raise ValueError("invalid decision")
                action = payload.get("action")
                category = payload.get("category")
                version = payload.get("version")
                if (
                    not isinstance(action, str)
                    or (category is not None and not isinstance(category, str))
                    or (version is not None and not isinstance(version, str))
                ):
                    raise ValueError("invalid decision")
                current = _call_put_review_item(
                    drawing_panel,
                    job_id=job_id,
                    review_id=review_id,
                    action=action,
                    category=category,
                    version=version,
                )
        except KeyError:
            return _error("Задача не найдена", 404)
        except DrawingCardPersistenceError:
            return _error("Решения не сохранены. Повторите действие", 503)
        except (TypeError, ValueError):
            return _error("Выберите допустимое решение и категорию", 400)
        return _secure(JSONResponse(drawing_card_job_payload(current)))

    async def drawing_card_review_context(request):
        try:
            radius = _review_context_radius(request.query_params.get("radius", "2"))
            payload = drawing_panel.get_review_context(
                job_id=request.path_params["job_id"],
                review_id=request.path_params["review_id"],
                radius=radius,
            )
        except KeyError:
            return _error("Задача или строка не найдена", 404)
        except (TypeError, ValueError):
            return _error("Радиус контекста должен быть числом от 1 до 5", 400)
        return _secure(JSONResponse(_safe_review_context(payload)))

    async def drawing_card_review_apply(request):
        try:
            current = drawing_panel.apply_inline_review(
                job_id=request.path_params["job_id"],
            )
        except KeyError:
            return _error("Задача не найдена", 404)
        except DrawingCardPersistenceError:
            return _error("Решения не сохранены. Повторите действие", 503)
        except (TypeError, ValueError):
            return _error("Сначала примите решение по каждой строке", 409)
        return _secure(JSONResponse(drawing_card_job_payload(current)))

    return Starlette(
        routes=[
            Route("/", index),
            Route("/drawing-card", drawing_card_index),
            Route("/package-reconciliation", package_reconciliation_index),
            Route("/help", help_index),
            Route("/static/{path}", static),
            Route(
                "/api/package-reconciliation/jobs",
                package_reconciliation_upload,
                methods=["POST"],
            ),
            Route(
                "/api/package-reconciliation/jobs/{job_id}",
                package_reconciliation_job,
                methods=["GET"],
            ),
            Route(
                "/api/package-reconciliation/jobs/{job_id}/result",
                package_reconciliation_result,
                methods=["GET"],
            ),
            Route("/api/jobs", upload, methods=["POST"]),
            Route("/api/jobs/{job_id}", get_job),
            Route("/api/jobs/{job_id}/decisions", decision, methods=["POST"]),
            Route(
                "/api/jobs/{job_id}/manual-discrepancy-decisions",
                manual_discrepancy_decision,
                methods=["POST"],
            ),
            Route("/api/jobs/{job_id}/result", download),
            *reconciliation_review_routes(panel),
            Route("/api/drawing-card/periods", drawing_card_periods, methods=["POST"]),
            Route("/api/drawing-card/jobs", drawing_card_upload, methods=["POST"]),
            Route("/api/drawing-card/jobs/{job_id}", drawing_card_get_job),
            Route(
                "/api/drawing-card/jobs/{job_id}/cancel",
                drawing_card_cancel,
                methods=["POST"],
            ),
            Route(
                "/api/drawing-card/jobs/{job_id}/retry",
                drawing_card_retry,
                methods=["POST"],
            ),
            Route(
                "/api/drawing-card/jobs/{job_id}/audit/exclusions",
                drawing_card_exclusion_audit,
                methods=["GET"],
            ),
            Route("/api/drawing-card/jobs/{job_id}/result", drawing_card_result),
            Route(
                "/api/drawing-card/jobs/{job_id}/review",
                drawing_card_review,
                methods=["GET", "POST"],
            ),
            Route(
                "/api/drawing-card/jobs/{job_id}/review/items",
                drawing_card_review_items,
                methods=["GET"],
            ),
            Route(
                "/api/drawing-card/jobs/{job_id}/review/clusters",
                drawing_card_review_clusters,
                methods=["GET"],
            ),
            Route(
                "/api/drawing-card/jobs/{job_id}/review/clusters/{cluster_id}",
                drawing_card_review_cluster,
                methods=["PUT", "DELETE"],
            ),
            Route(
                "/api/drawing-card/jobs/{job_id}/review/items/{review_id}",
                drawing_card_review_item,
                methods=["PUT", "DELETE"],
            ),
            Route(
                "/api/drawing-card/jobs/{job_id}/review/items/{review_id}/context",
                drawing_card_review_context,
                methods=["GET"],
            ),
            Route(
                "/api/drawing-card/jobs/{job_id}/review/apply",
                drawing_card_review_apply,
                methods=["POST"],
            ),
        ]
    )


def _upload_part(form: Mapping[str, object], key: str):
    return _upload_value(form[key])


def _drawing_card_review_filters(query: Mapping[str, str]) -> dict[str, object]:
    """Parse the small, public packet-filter contract without changing its meaning."""
    reason = _optional_filter(query.get("reason"), "reason")
    category = _optional_filter(query.get("category"), "category")
    safe_filename = _safe_filename_filter(query.get("safe_filename"))
    confidence = _confidence_filter(query.get("confidence"))
    only_unresolved = _boolean_filter(query.get("only_unresolved", "true"))
    return {
        "reason": reason,
        "category": category,
        "safe_filename": safe_filename,
        "confidence": confidence,
        "only_unresolved": only_unresolved,
    }


def _optional_filter(value: str | None, name: str) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    if len(cleaned) > 200 or any(character in cleaned for character in "\x00\r\n"):
        raise ValueError(f"invalid {name}")
    return cleaned


def _safe_filename_filter(value: str | None) -> str | None:
    cleaned = _optional_filter(value, "safe_filename")
    if cleaned is None:
        return None
    if "/" in cleaned or "\\" in cleaned or cleaned in {".", ".."}:
        raise ValueError("invalid safe_filename")
    return cleaned


def _confidence_filter(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        confidence = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("invalid confidence") from error
    if not confidence.is_finite() or not Decimal("0") <= confidence <= Decimal("1"):
        raise ValueError("invalid confidence")
    return float(confidence)


def _boolean_filter(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError("invalid only_unresolved")


def _review_context_radius(value: str) -> int:
    radius = int(value)
    if not 1 <= radius <= 5:
        raise ValueError("invalid radius")
    return radius


def _call_review_clusters(service, **kwargs: object) -> dict[str, object]:
    """Call the frozen v3 signature, retaining old local service compatibility."""
    method = service.list_review_clusters
    accepted = signature(method).parameters
    if any(item.kind is Parameter.VAR_KEYWORD for item in accepted.values()):
        return method(**kwargs)
    return method(**{key: value for key, value in kwargs.items() if key in accepted})


def _call_put_review_item(service, **kwargs: object):
    """Pass member version to v3 services; pre-v3 services never see the new field."""
    method = service.put_review_item
    accepted = signature(method).parameters
    if any(item.kind is Parameter.VAR_KEYWORD for item in accepted.values()):
        return method(**kwargs)
    return method(**{key: value for key, value in kwargs.items() if key in accepted})


def _safe_review_context(payload: object) -> object:
    """Defence in depth: context rows cannot disclose paths or raw source containers."""
    if isinstance(payload, Mapping):
        result = {
            key: payload[key]
            for key in ("review_id", "radius", "items", "rows", "context")
            if key in payload
        }
        for key in ("items", "rows", "context"):
            if isinstance(result.get(key), (list, tuple)):
                result[key] = [_safe_review_context_row(item) for item in result[key]]
        return result
    if isinstance(payload, (list, tuple)):
        return [_safe_review_context_row(item) for item in payload]
    raise ValueError("invalid review context")


def _safe_review_context_row(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("invalid review context row")
    allowed = {
        "review_id",
        "version",
        "safe_filename",
        "sheet_name",
        "row_number",
        "position",
        "drawing_code",
        "object_index",
        "work_name",
        "source_unit",
        "quantity",
        "total_cost",
        "confidence",
        "reason",
        "reason_label",
        "selected_category",
    }
    result = {key: value[key] for key in allowed if key in value}
    filename = result.get("safe_filename")
    if isinstance(filename, str):
        result["safe_filename"] = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    return result


def _drawing_card_upload_error(error: Exception) -> str:
    """Return a public validation category without exposing exception details."""
    if isinstance(error, ValueError):
        return _DRAWING_CARD_UPLOAD_ERRORS.get(str(error), _DRAWING_CARD_UPLOAD_FALLBACK)
    return _DRAWING_CARD_UPLOAD_FALLBACK


def _period_label(value: str) -> str:
    months = (
        "январь",
        "февраль",
        "март",
        "апрель",
        "май",
        "июнь",
        "июль",
        "август",
        "сентябрь",
        "октябрь",
        "ноябрь",
        "декабрь",
    )
    year, month = value.split("-", 1)
    return f"{months[int(month) - 1]} {year}"


def _upload_value(value: object):
    if not isinstance(getattr(value, "filename", None), str):
        raise ValueError("missing upload")
    return value


async def _read_upload(upload, *, maximum: int = MAX_UPLOAD_BYTES) -> bytes:
    content = await upload.read(maximum + 1)
    if not content or len(content) > maximum:
        raise ValueError("upload size is invalid")
    return content


def _validate_content_length(
    value: str | None,
    *,
    maximum: int = MAX_UPLOAD_BYTES + 1024 * 1024,
) -> None:
    if value is None:
        return
    try:
        size = int(value)
    except ValueError as error:
        raise ValueError("invalid content length") from error
    if size < 0 or size > maximum:
        raise ValueError("request body is too large")


def _bounded_result(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError("result is not a regular file")
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError("result is too large")
    with path.open("rb") as stream:
        content = stream.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("result is too large")
    return content


def _safe_download_name(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("filename must be a string")
    name = Path(value).name.replace("\r", "").replace("\n", "")
    name = _SAFE_DOWNLOAD_NAME.sub("-", name).strip(".-")
    if not name:
        return "result.bin"
    if len(name) <= 120:
        return name
    suffix = Path(name).suffix
    if suffix and len(suffix) < 120:
        return name[: 120 - len(suffix)] + suffix
    return name[:120]


def _result_media_type(filename: str) -> str:
    suffix = Path(filename).suffix.casefold()
    if suffix == ".json":
        return "application/json"
    if suffix == ".xlsm":
        return _XLSM_MEDIA_TYPE
    if suffix == ".zip":
        return _ZIP_MEDIA_TYPE
    return _WORKBOOK_MEDIA_TYPE


def _content_disposition(filename: str) -> str:
    """Build a header-safe name while retaining a UTF-8 download filename."""

    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "result.bin"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _drawing_card_download(service, job_id: str, *, kind: str):
    from starlette.responses import Response

    try:
        getter = service.get_result if kind == "result" else service.get_review
        path, filename = getter(job_id)
        content = _bounded_result(Path(path))
        safe_name = _safe_download_name(filename)
    except KeyError:
        return _error("Файл пока недоступен", 404)
    except (OSError, TypeError, ValueError):
        return _error("Файл недоступен", 409)
    return _secure(
        Response(
            content,
            media_type=_WORKBOOK_MEDIA_TYPE,
            headers={"Content-Disposition": _content_disposition(safe_name)},
        )
    )


def _secure(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _error(message: str, status_code: int):
    from starlette.responses import JSONResponse

    return _secure(JSONResponse({"error": message}, status_code=status_code))


create_admin_app = create_app
