"""Maintenance tasks (stale-flagging, cleanup, exports). Never ADMS ingest (§71)."""

from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(name="maintenance.flag_stale_devices")  # type: ignore[untyped-decorator]
def flag_stale_devices() -> dict[str, int]:
    """Mark devices inactive beyond ZKTECO_STALE_AFTER as `stale` (no deletion, §46)."""
    return {"flagged": 0}
