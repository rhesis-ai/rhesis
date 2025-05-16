import os

from celery import Celery
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create the Celery app
app = Celery("rhesis")

# Configure Celery
app.conf.update(
    broker_url=os.getenv("BROKER_URL"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# Auto-discover tasks without loading config files
app.autodiscover_tasks(["rhesis.backend.tasks"], force=True)
