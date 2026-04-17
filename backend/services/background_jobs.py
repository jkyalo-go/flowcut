from __future__ import annotations

import json
import socket
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from domain.automation import AuditLog, Notification
from domain.enterprise import BackgroundJob, ComplianceExport, UsageLedger
from domain.platforms import CalendarSlot
from domain.shared import ComplianceExportStatus, JobStatus
from services.audit import create_notification, record_audit
from services.platform_integrations import execute_slot, sync_slot_status
from services.storage import write_text_artifact


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_job(
    db: Session,
    *,
    job_type: str,
    correlation_id: str,
    payload: dict,
    workspace_id: str | None = None,
    idempotency_key: str | None = None,
    next_attempt_at: datetime | None = None,
) -> BackgroundJob:
    if idempotency_key:
        existing = db.query(BackgroundJob).filter(BackgroundJob.idempotency_key == idempotency_key).first()
        if existing:
            return existing
    row = BackgroundJob(
        workspace_id=workspace_id,
        job_type=job_type,
        status=JobStatus.PENDING,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        payload_json=json.dumps(payload),
        next_attempt_at=next_attempt_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def ensure_due_publish_jobs(db: Session, workspace_id: str | None = None) -> int:
    now = _now()
    query = db.query(CalendarSlot).filter(CalendarSlot.status.in_(["scheduled", "publishing", "processing"]))
    if workspace_id:
        query = query.filter(CalendarSlot.workspace_id == workspace_id)
    created = 0
    for slot in query.all():
        if slot.status == "scheduled" and slot.scheduled_at and slot.scheduled_at > now:
            continue
        job_type = "publish_execute" if slot.status == "scheduled" else "publish_sync"
        key = f"{job_type}:{slot.id}:{slot.retry_count}:{slot.status}"
        existing = db.query(BackgroundJob).filter(
            BackgroundJob.idempotency_key == key,
            BackgroundJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
        ).first()
        if existing:
            continue
        enqueue_job(
            db,
            workspace_id=slot.workspace_id,
            job_type=job_type,
            correlation_id=slot.correlation_id or slot.id,
            idempotency_key=key,
            payload={"slot_id": slot.id},
            next_attempt_at=now,
        )
        created += 1
    return created


def _run_compliance_export(db: Session, job: BackgroundJob, payload: dict) -> None:
    export_id = payload["export_id"]
    export = db.query(ComplianceExport).filter(ComplianceExport.id == export_id).first()
    if not export:
        raise RuntimeError("Compliance export not found")
    export.status = ComplianceExportStatus.PROCESSING
    db.commit()

    export_type = export.export_type
    rows: list[dict] = []
    if export_type == "audit_log":
        query = db.query(AuditLog).filter(AuditLog.workspace_id == export.workspace_id).order_by(AuditLog.created_at.asc())
        rows = [
            {
                "id": row.id,
                "actor": row.actor,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "reason": row.reason,
                "metadata_json": row.metadata_json,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in query.all()
        ]
    elif export_type == "usage":
        query = db.query(UsageLedger).filter(UsageLedger.workspace_id == export.workspace_id).order_by(UsageLedger.created_at.asc())
        rows = [
            {
                "id": row.id,
                "category": row.category,
                "quantity": row.quantity,
                "unit": row.unit,
                "amount_usd": row.amount_usd,
                "correlation_id": row.correlation_id,
                "metadata_json": row.metadata_json,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in query.all()
        ]
    else:
        query = db.query(Notification).filter(Notification.workspace_id == export.workspace_id).order_by(Notification.created_at.asc())
        rows = [
            {
                "id": row.id,
                "category": row.category,
                "title": row.title,
                "body": row.body,
                "metadata_json": row.metadata_json,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in query.all()
        ]

    artifact = write_text_artifact(
        export.workspace_id,
        f"{export_type}_{export.id}.json",
        json.dumps({"export_type": export_type, "rows": rows}, indent=2),
    )
    export.storage_uri = artifact
    export.status = ComplianceExportStatus.COMPLETED
    export.completed_at = _now()
    db.commit()
    create_notification(
        db,
        workspace_id=export.workspace_id,
        category="compliance",
        title="Flowcut compliance export completed",
        body=f"{export_type} export is ready.",
        metadata={"export_id": export.id, "storage_uri": artifact},
    )


def _run_publish_execute(db: Session, job: BackgroundJob, payload: dict) -> None:
    slot = db.query(CalendarSlot).filter(CalendarSlot.id == payload["slot_id"]).first()
    if not slot:
        raise RuntimeError("Calendar slot not found")
    execute_slot(db, slot)


def _run_publish_sync(db: Session, job: BackgroundJob, payload: dict) -> None:
    slot = db.query(CalendarSlot).filter(CalendarSlot.id == payload["slot_id"]).first()
    if not slot:
        raise RuntimeError("Calendar slot not found")
    sync_slot_status(db, slot)


def _run_performance_feedback_sweep(db: Session, job: BackgroundJob, payload: dict) -> None:
    from services.sie.performance import run_performance_feedback_sweep
    run_performance_feedback_sweep()


JOB_HANDLERS = {
    "compliance_export": _run_compliance_export,
    "publish_execute": _run_publish_execute,
    "publish_sync": _run_publish_sync,
    "performance_feedback_sweep": _run_performance_feedback_sweep,
}


def process_available_jobs(db: Session, limit: int = 20) -> int:
    now = _now()
    host = socket.gethostname()
    rows = db.query(BackgroundJob).filter(
        BackgroundJob.status == JobStatus.PENDING,
        or_(BackgroundJob.next_attempt_at == None, BackgroundJob.next_attempt_at <= now),  # noqa: E711
    ).order_by(BackgroundJob.created_at.asc()).limit(limit).all()

    processed = 0
    for row in rows:
        handler = JOB_HANDLERS.get(row.job_type)
        if not handler:
            row.status = JobStatus.DEAD_LETTER
            row.last_error = f"No handler for job type `{row.job_type}`"
            db.commit()
            continue

        row.status = JobStatus.RUNNING
        row.lease_owner = host
        row.lease_expires_at = now
        row.attempts = (row.attempts or 0) + 1
        db.commit()

        try:
            handler(db, row, json.loads(row.payload_json or "{}"))
            row.status = JobStatus.SUCCEEDED
            row.result_json = json.dumps({"completed_at": _now().isoformat()})
            row.last_error = None
            db.commit()
        except Exception as exc:
            row.last_error = str(exc)
            row.status = JobStatus.DEAD_LETTER if row.attempts >= 5 else JobStatus.PENDING
            row.next_attempt_at = _now()
            db.commit()
            if row.workspace_id:
                record_audit(
                    db,
                    workspace_id=row.workspace_id,
                    actor="system",
                    action="job.failed",
                    target_type="background_job",
                    target_id=row.id,
                    reason=str(exc),
                    metadata={"job_type": row.job_type, "correlation_id": row.correlation_id},
                )
                create_notification(
                    db,
                    workspace_id=row.workspace_id,
                    category="operations",
                    title="Flowcut background job failed",
                    body=str(exc),
                    metadata={"job_id": row.id, "job_type": row.job_type, "correlation_id": row.correlation_id},
                )
        processed += 1
    return processed
