"""
Telemetry Processor Service

Legacy entry point for backwards compatibility.
Imports and runs the refactored implementation.
"""

from processor.main import serve

if __name__ == "__main__":
    serve()
