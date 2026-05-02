"""
Celery worker entrypoint.
Run with: celery -A celery_worker.celery_app worker --loglevel=info -Q analysis,blockchain
"""
import sys
import os

# Add the API service to the path so we can import the app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from app.core.celery_app import celery_app  # noqa: E402
from app.tasks.analyze import run_video_analysis  # noqa: E402, F401
