from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AnalysisJob
from .deps import AuthContext, current_context


router = APIRouter(prefix="/analysis-jobs", tags=["任务"])


@router.get("/{job_id}")
def get_job(job_id: str, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict:
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.owner_id == context.user.id))
    if not job:
        raise HTTPException(404, "未找到任务")
    return {
        "id": job.id,
        "session_id": job.session_id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "error_code": job.error_code,
        "error": job.error_message,
        "retryable": bool((job.result_json or {}).get("retryable")),
        "result": job.result_json,
        "provider": job.provider,
        "model": job.provider_model,
        "provider_task_id": job.provider_task_id,
        "attempt_count": job.attempt_count,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
