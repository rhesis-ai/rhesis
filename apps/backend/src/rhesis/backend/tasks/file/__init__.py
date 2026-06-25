"""File-related Celery tasks.

Importing the submodules here ensures the ``@app.task`` decorators run at
package-import time, so the worker registers the tasks. Without this, the
worker rejects messages with ``KeyError: 'rhesis.backend.tasks.file.extract_text'``.
"""

from rhesis.backend.tasks.file import extract_text  # noqa: F401
