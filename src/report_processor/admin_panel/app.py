"""Starlette-compatible local app factory."""

from __future__ import annotations

from pathlib import Path

from .service import AdminPanelService
from .view import PAGE


def create_app(service: AdminPanelService | None = None, workspace_root: Path | None = None):
    """Return a local Starlette app; importing this package does not require Starlette."""

    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, JSONResponse, Response
    from starlette.routing import Route

    panel = service or AdminPanelService(workspace_root or Path.cwd() / ".admin-panel-jobs")

    async def index(request):
        return HTMLResponse(PAGE)

    async def upload(request):
        form = await request.form()
        try:
            source, target = form["source"], form["target"]
            job = panel.create_job(
                source_name=source.filename,
                source_content=await source.read(),
                target_name=target.filename,
                target_content=await target.read(),
                stage=form.get("stage", "13.1"),
                mode=form.get("mode", "write"),
            )
            return JSONResponse(_job(job))
        except (KeyError, ValueError):
            return JSONResponse({"error": "Некорректные файлы"}, status_code=400)

    async def job(request):
        try:
            return JSONResponse(_job(panel.get(request.path_params["job_id"])))
        except KeyError:
            return JSONResponse({"error": "Задача не найдена"}, status_code=404)

    async def decision(request):
        try:
            payload = await request.json()
            return JSONResponse(
                _job(
                    panel.record_decision(
                        job_id=request.path_params["job_id"],
                        suggestion_id=payload["suggestion_id"],
                        decision=payload["decision"],
                    )
                )
            )
        except (KeyError, ValueError):
            return JSONResponse({"error": "Некорректное решение"}, status_code=400)

    async def download(request):
        try:
            path, filename = panel.get_result(request.path_params["job_id"])
            if path.is_file():
                return Response(
                    path.read_bytes(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={
                        "Content-Disposition": f"attachment; filename={filename}",
                        "X-Content-Type-Options": "nosniff",
                        "Cache-Control": "no-store",
                    },
                )
        except KeyError:
            pass
        return JSONResponse({"error": "Файл недоступен"}, status_code=404)

    return Starlette(
        routes=[
            Route("/", index),
            Route("/api/jobs", upload, methods=["POST"]),
            Route("/api/jobs/{job_id}", job),
            Route("/api/jobs/{job_id}/decisions", decision, methods=["POST"]),
            Route("/api/jobs/{job_id}/result", download),
        ]
    )


def _job(job):
    return {
        "job_id": job.job_id,
        "status": job.status,
        "stage": job.stage,
        "summary": {},
        "discrepancies": [],
        "suggestions": [],
        "download_url": f"/api/jobs/{job.job_id}/result" if job.output else None,
    }


create_admin_app = create_app
