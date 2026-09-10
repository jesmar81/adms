"""Celery app — only for reports/exports/maintenance (§71), never ADMS ingest."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

celery_app = Celery("zkteco_adms", broker=get_settings().redis_url)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])
