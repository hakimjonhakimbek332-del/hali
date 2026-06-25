"""
Celery tasks package
"""
from tasks.celery_tasks import app as celery_app

__all__ = ["celery_app"]
