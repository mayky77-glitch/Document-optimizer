"""Starlette-compatible local app factory."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from .drawing_card_presentation import drawing_card_job_payload
from .drawing_card_service import (
    MAX_SOURCES as DRAWING_CARD_MAX_SOURCES,
)
from .drawing_card_service import (
    MAX_UPLOAD_BYTES as DRAWING_CARD_MAX_UPLOAD_BYTES,
)
from .drawing_card_service import (
    DrawingCardService,
)
from .presentation import job_payload
from .service import (
    MAX_UPLOAD_BYTES,
    AdminPanelService,
    validate_mode,
    validate_stage,
    validate_workbook_upload,
)
from .view import drawing_card_page, index_page, static_asset

_SAFE_DOWNLOAD_NAME = re.compile(r"[^0-9A-Za-z._-]+")
_WORKBOOK_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def create_app(service=None, workspace_root=None, drawing_card_service=None):
    """Return the frozen local panel API without starting a server."""

    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, JSONResponse, Response
    from starlette.routing import Route

    workspace = (
        Path(workspace_root) if workspace_root is not None else Path.cwd() / ".admin-panel-jobs"
    )
    panel = service or AdminPanelService(workspace)
    drawing_panel = drawing_card_service or DrawingCardService(workspace / "drawing-card")

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

    async def upload(request):
        try:
            _validate_content_length(request.headers.get("content-length"))
            async with request.form(
                max_files=2,
                max_fields=2,
                max_part_size=MAX_UPLOAD_BYTES + 1,
            ) as form:
                source = _upload_part(form, "source")
                target = _upload_part(form, "target")
                source_content = await _read_upload(source)
                target_content = await _read_upload(target)
                if len(source_content) + len(target_content) > MAX_UPLOAD_BYTES:
                    raise ValueError("combined upload is too large")
                validate_workbook_upload(source.filename, source_content)
                validate_workbook_upload(target.filename, target_content)
                stage = validate_stage(form.get("stage", "13.1"))
                mode = validate_mode(form.get("mode", "write"))
                job = panel.create_job(
                    source_name=source.filename,
                    source_content=source_content,
                    target_name=target.filename,
                    target_content=target_content,
                    stage=stage,
                    mode=mode,
                )
        except (KeyError, TypeError, ValueError):
            return _error("Проверьте два Excel-файла, этап и режим", 400)
        return _secure(JSONResponse(job_payload(job), status_code=201))

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
        if not isinstance(payload, Mapping):
            return _error("Ожидается JSON с решением", 400)
        suggestion_id = payload.get("suggestion_id")
        value = payload.get("decision")
        if not isinstance(suggestion_id, str) or value not in {"fit", "not_fit"}:
            return _error("Допустимы только решения fit и not_fit", 400)
        try:
            current = panel.record_decision(
                job_id=request.path_params["job_id"],
                suggestion_id=suggestion_id,
                decision=value,
            )
        except KeyError:
            return _error("Задача не найдена", 404)
        except (TypeError, ValueError):
            return _error("Решение не относится к открытой рекомендации", 400)
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
        media_type = (
            "application/json"
            if Path(safe_name).suffix.casefold() == ".json"
            else _WORKBOOK_MEDIA_TYPE
        )
        return _secure(
            Response(
                content,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
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
                )
        except (KeyError, OSError, TypeError, ValueError):
            return _error("Проверьте исходные Excel-файлы и выбранную операцию", 400)
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
        except (OSError, TypeError, ValueError):
            return _error("Проверьте заполненный файл проверки", 400)
        return _secure(JSONResponse(drawing_card_job_payload(current)))

    return Starlette(
        routes=[
            Route("/", index),
            Route("/drawing-card", drawing_card_index),
            Route("/static/{path}", static),
            Route("/api/jobs", upload, methods=["POST"]),
            Route("/api/jobs/{job_id}", get_job),
            Route("/api/jobs/{job_id}/decisions", decision, methods=["POST"]),
            Route("/api/jobs/{job_id}/result", download),
            Route("/api/drawing-card/jobs", drawing_card_upload, methods=["POST"]),
            Route("/api/drawing-card/jobs/{job_id}", drawing_card_get_job),
            Route("/api/drawing-card/jobs/{job_id}/result", drawing_card_result),
            Route(
                "/api/drawing-card/jobs/{job_id}/review",
                drawing_card_review,
                methods=["GET", "POST"],
            ),
        ]
    )


def _upload_part(form: Mapping[str, object], key: str):
    return _upload_value(form[key])


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
    return name[:120] or "result.bin"


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
            headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
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
