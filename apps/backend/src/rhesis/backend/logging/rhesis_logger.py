import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv(override=True)

# Create a named logger
logger = logging.getLogger("__rhesis__")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Create a console handler (Cloud Run captures logs from stdout)
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Set the formatter for the console handler
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S%p",
)
console_handler.setFormatter(formatter)

# Add the console handler to the logger
logger.addHandler(console_handler)

# Conditionally add file logging only for local development
if os.environ.get("ENV", "production") != "production":
    # Determine the log file path
    log_file_path = os.environ.get("LOG_FILE_PATH", "logs/rhesis.log")

    # Ensure the directory exists
    from pathlib import Path

    Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)

    # Create a file handler
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

    # Set the formatter for the file handler
    file_formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S%p",
    )
    file_handler.setFormatter(file_formatter)

    # Add the file handler to the logger
    logger.addHandler(file_handler)
