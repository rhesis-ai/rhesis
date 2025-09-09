"""Utility functions and context managers for statistics calculations."""

import time
from contextlib import contextmanager
from typing import Generator


@contextmanager
def timer(operation_name: str, enabled: bool = True) -> Generator[None, None, None]:
    """Context manager for timing operations"""
    if not enabled:
        yield
        return

    start_time = time.time()
    print(f"Starting {operation_name}")
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        print(f"{operation_name} took {elapsed:.3f}s")
