"""
This file provides unified error messages for the entire SDK.
Error messages should be defined here as a constant before usage.
This makes editing the messages easier by never missing occurrences.
Before adding a message, if there is one present for your case!
"""

RHESIS_ONLINE_MODE_REQUIRED = "Rhesis is currently set to offline mode. To use this feature Rhesis has to be set to online mode"

JSON_MODE_ERROR_INVALID_JSON = "The model returned an invalid JSON file. JSON could not be parsed: {error}"
GENERAL_MODEL_ERROR_PROCESSING_REQUEST = "Error occurred while running the prompt: {error}"