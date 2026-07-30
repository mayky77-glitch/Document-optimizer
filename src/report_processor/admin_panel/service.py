"""Private job lifecycle and a small injectable execution boundary."""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class AdminJob:
    job_id: str
    directory: Path
    source: Path
    target: Path
    stage: str
    status: str = "ready"
    output: Path | None = None
    review: list[dict[str, str]] = field(default_factory=list)


class AdminPanelService:
    """Owns opaque job IDs and never exposes workspace paths to clients."""

    def __init__(
        self, workspace_root: Path, execute: Callable[[AdminJob], Path | None] | None = None
    ):
        self.workspace_root = workspace_root
        self.execute = execute
        self.jobs: dict[str, AdminJob] = {}

    def create_job(
        self,
        *,
        source_name: str,
        source_content: bytes,
        target_name: str,
        target_content: bytes,
        stage: str,
        mode: str = "write",
    ) -> AdminJob:
        source_bytes, target_bytes = source_content, target_content
        _validate_upload(source_name, source_bytes)
        _validate_upload(target_name, target_bytes)
        job_id = secrets.token_urlsafe(18)
        directory = self.workspace_root / job_id
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        source = directory / f"source{Path(source_name).suffix.lower()}"
        target = directory / f"target{Path(target_name).suffix.lower()}"
        source.write_bytes(source_bytes)
        target.write_bytes(target_bytes)
        job = AdminJob(job_id, directory, source, target, stage)
        self.jobs[job_id] = job
        return job

    def run(self, job_id: str) -> AdminJob:
        job = self.get(job_id)
        job.status = "running"
        try:
            job.output = self.execute(job) if self.execute else None
            job.status = "review" if job.review else "complete"
        except Exception:
            job.status = "failed"
        return job

    def decide(self, job_id: str, relation_id: str, decision: str) -> AdminJob:
        if decision not in {"fit", "not_fit"}:
            raise ValueError("invalid decision")
        job = self.get(job_id)
        job.review.append({"relation_id": relation_id, "decision": decision, "version": "18.0"})
        return job

    def record_decision(self, *, job_id: str, suggestion_id: str, decision: str) -> AdminJob:
        return self.decide(job_id, suggestion_id, decision)

    def get_result(self, job_id: str) -> tuple[Path, str]:
        job = self.get(job_id)
        if job.output is None:
            raise KeyError(job_id)
        return job.output, "result.xlsx"

    def review_bytes(self, job_id: str) -> bytes:
        return json.dumps(self.get(job_id).review, ensure_ascii=False, indent=2).encode()

    def get(self, job_id: str) -> AdminJob:
        if job_id not in self.jobs:
            raise KeyError(job_id)
        return self.jobs[job_id]


def _validate_upload(name: str, content: bytes) -> None:
    if Path(name).suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError("only Excel workbooks are accepted")
    if not content:
        raise ValueError("empty upload")
