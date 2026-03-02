from celery import Celery

from app.config import settings

celery_app = Celery(
    "url_shortener",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.click_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,           # Acknowledge after completion, not on receipt
    worker_prefetch_multiplier=1,  # Fair task distribution
)
