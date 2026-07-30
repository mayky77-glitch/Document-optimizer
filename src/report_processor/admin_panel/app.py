"""Starlette-compatible local app factory."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from .presentation import job_payload
from .service import (
    MAX_UPLOAD_BYTES,
    AdminPanelService,
    validate_mode,
    validate_stage,
    validate_workbook_upload,
)
from .view import index_page, static_asset

_SAFE_DOWNLOAD_NAME = re.compile(r"[^0-9A-Za-z._-]+")
_WORKBOOK_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def create_app(service=None, workspace_root=None):
    """Return the frozen local panel API without starting a server."""

    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, JSONResponse, Response
    from starlette.routing import Route

    panel = service or AdminPanelService(
        Path(workspace_root) if workspace_root is not None else Path.cwd() / ".admin-panel-jobs"
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

    return Starlette(
        routes=[
            Route("/", index),
            Route("/static/{path}", static),
            Route("/api/jobs", upload, methods=["POST"]),
            Route("/api/jobs/{job_id}", get_job),
            Route("/api/jobs/{job_id}/decisions", decision, methods=["POST"]),
            Route("/api/jobs/{job_id}/result", download),
        ]
    )


def _upload_part(form: Mapping[str, object], key: str):
    value = form[key]
    if not isinstance(getattr(value, "filename", None), str):
        raise ValueError("missing upload")
    return value


async def _read_upload(upload) -> bytes:
    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("upload size is invalid")
    return content


def _validate_content_length(value: str | None) -> None:
    if value is None:
        return
    try:
        size = int(value)
    except ValueError as error:
        raise ValueError("invalid content length") from error
    if size < 0 or size > MAX_UPLOAD_BYTES + 1024 * 1024:
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


def _secure(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _error(message: str, status_code: int):
    from starlette.responses import JSONResponse

    return _secure(JSONResponse({"error": message}, status_code=status_code))


create_admin_app = create_app
