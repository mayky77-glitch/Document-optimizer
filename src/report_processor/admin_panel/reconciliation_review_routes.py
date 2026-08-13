"""Authoritative reconciliation route handlers, kept outside the app factory."""

from __future__ import annotations

from collections.abc import Mapping

from .presentation import job_payload
from .reconciliation_review_api import (
    ReconciliationReviewRequestError,
    parse_reconciliation_batch_decision,
    parse_reconciliation_review_decision,
    parse_safe_package_ids,
)


def reconciliation_review_routes(panel):
    from starlette.routing import Route

    async def group(request):
        return await _put(request, panel, "group")

    async def row(request):
        if request.method == "DELETE":
            return await _delete(request, panel)
        return await _put(request, panel, "row")

    async def package(request):
        return await _put(request, panel, "package")

    async def family(request):
        return await _put(request, panel, "family")

    async def accept_safe(request):
        try:
            payload = await request.json()
            current = panel.accept_reconciliation_safe_packages(
                request.path_params["job_id"], parse_safe_package_ids(payload)
            )
        except KeyError:
            return _error("Задача не найдена", 404)
        except (ReconciliationReviewRequestError, TypeError, ValueError):
            return _error("Решение устарело или содержит недопустимую категорию", 409)
        return _json(job_payload(current))

    async def undo(request):
        try:
            current = panel.undo_reconciliation(request.path_params["job_id"])
        except KeyError:
            return _error("Задача не найдена", 404)
        except (TypeError, ValueError):
            return _error("Нет решения для отмены", 409)
        return _json(job_payload(current))

    async def apply(request):
        try:
            current = panel.apply_reconciliation(request.path_params["job_id"])
        except KeyError:
            return _error("Задача не найдена", 404)
        except (OSError, TypeError, ValueError, RuntimeError):
            return _error("Не удалось безопасно применить решения", 409)
        return _json(job_payload(current))

    return [
        Route("/api/jobs/{job_id}/review/groups/{group_id}", group, methods=["PUT"]),
        Route("/api/jobs/{job_id}/review/items/{row_id}", row, methods=["PUT", "DELETE"]),
        Route("/api/jobs/{job_id}/review/packages/accept-safe", accept_safe, methods=["POST"]),
        Route("/api/jobs/{job_id}/review/undo", undo, methods=["POST"]),
        Route("/api/jobs/{job_id}/review/packages/{package_id}", package, methods=["PUT"]),
        Route("/api/jobs/{job_id}/review/families/{family_id}", family, methods=["PUT"]),
        Route("/api/jobs/{job_id}/review/apply", apply, methods=["POST"]),
    ]


async def _put(request, panel, scope: str):
    try:
        payload = await request.json()
        job_id = request.path_params["job_id"]
        if scope in {"package", "family"}:
            decision = parse_reconciliation_batch_decision(payload)
            if scope == "package":
                current = panel.put_reconciliation_package(
                    job_id, request.path_params["package_id"], decision
                )
            else:
                current = panel.put_reconciliation_family(
                    job_id, request.path_params["family_id"], decision
                )
        else:
            decision = parse_reconciliation_review_decision(
                payload,
                group_id=request.path_params["group_id"] if scope == "group" else None,
                row_id=request.path_params["row_id"] if scope == "row" else None,
            )
            if scope == "group":
                current = panel.put_reconciliation_group(
                    job_id, request.path_params["group_id"], decision
                )
            else:
                current = panel.put_reconciliation_row(
                    job_id, request.path_params["row_id"], decision
                )
    except KeyError:
        return _error("Задача не найдена", 404)
    except (ReconciliationReviewRequestError, TypeError, ValueError):
        return _error("Решение устарело или содержит недопустимую категорию", 409)
    return _json(job_payload(current))


async def _delete(request, panel):
    try:
        payload = await request.json()
        version = payload.get("version") if isinstance(payload, Mapping) else None
        if not isinstance(version, str):
            raise ValueError("version is required")
        current = panel.delete_reconciliation_row(
            request.path_params["job_id"], request.path_params["row_id"], version
        )
    except KeyError:
        return _error("Задача не найдена", 404)
    except (TypeError, ValueError):
        return _error("Изменение устарело", 409)
    return _json(job_payload(current))


def _json(payload):
    from starlette.responses import JSONResponse

    return _secure(JSONResponse(payload))


def _error(message: str, status_code: int):
    from starlette.responses import JSONResponse

    return _secure(JSONResponse({"error": message}, status_code=status_code))


def _secure(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
