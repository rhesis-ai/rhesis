from rhesis.backend.celery_app import app
from rhesis.backend.tasks import BaseTask


@app.task(base=BaseTask, name="rhesis.tasks.process_data")
def process_data(data: dict):
    """Example task that processes data."""
    try:
        print(f"Processing data: {data}")
        result = {"processed": data}
        return result
    except Exception as e:
        # The task will be automatically retried due to BaseTask settings
        raise e


@app.task(base=BaseTask, name="rhesis.tasks.echo")
def echo(message: str):
    """Echo task for testing."""
    return message
