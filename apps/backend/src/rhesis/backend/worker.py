import logging

from dotenv import load_dotenv

# Load environment variables from .env file (only works locally, not in Cloud Run)
load_dotenv()

# Import signals so that they are registered
import rhesis.backend.celery.signals  # noqa: E402, F401
from rhesis.backend.app.services.telemetry.conversation_linking import (  # noqa: E402
    initialize_cache as init_conv_cache_parent,
)
from rhesis.backend.app.services.telemetry.trace_metrics_cache import (  # noqa: E402
    initialize_cache as init_metrics_cache_parent,
)
from rhesis.backend.celery.core import app  # noqa: E402

# Initialize caches in parent worker (needed for master process state)
init_conv_cache_parent()
init_metrics_cache_parent()

# Pre-warm the exchange rate cache so the first enrichment task
# does not block on an HTTP call to the exchange rate API.
try:
    from rhesis.backend.app.services.exchange_rate import get_usd_to_eur_rate

    get_usd_to_eur_rate()
except Exception:
    pass

# Configure logging to reduce verbosity
# Suppress verbose Celery task result logging
logging.getLogger("celery.task").setLevel(logging.WARNING)
logging.getLogger("celery.worker").setLevel(logging.WARNING)

if __name__ == "__main__":
    print("\n=== Worker Module Test ===")
    print("Redis-optimized Celery configuration loaded")
    print(f"Available tasks: {len(app.tasks)}")
