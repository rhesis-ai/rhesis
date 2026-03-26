from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, field_validator, model_validator

if TYPE_CHECKING:
    from rhesis.sdk.entities.file import File

from rhesis.sdk.clients import APIClient, Endpoints, Methods
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity, handle_http_errors
from rhesis.sdk.entities.endpoint import Endpoint
from rhesis.sdk.entities.prompt import Prompt
from rhesis.sdk.enums import TestType

ENDPOINT = Endpoints.TESTS


class TestConfiguration(BaseModel):
    goal: str
    instructions: str = ""  # Optional - how Penelope should conduct the test
    restrictions: str = ""  # Optional - forbidden behaviors for the target
    scenario: str = ""  # Optional - contextual framing for the test
    max_turns: Optional[int] = None  # Maximum conversation turns (default: 10)
    min_turns: Optional[int] = None  # Minimum turns before early stopping


class Test(BaseEntity):
    endpoint = ENDPOINT
    _push_required_fields: ClassVar[tuple[str, ...]] = ("category", "behavior")
    _write_only_fields: ClassVar[tuple[str, ...]] = ("files",)

    category: Optional[str] = None
    topic: Optional[str] = None
    behavior: Optional[str] = None
    prompt: Optional[Prompt] = None
    metadata: dict = {}
    id: Optional[str] = None
    test_configuration: Optional[TestConfiguration] = None
    test_type: Optional[TestType] = None
    files: Optional[list] = None
    # Convenience fields that build test_configuration if not provided
    goal: Optional[str] = None
    instructions: Optional[str] = None
    restrictions: Optional[str] = None
    scenario: Optional[str] = None
    max_turns: Optional[int] = None
    min_turns: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def build_test_configuration(cls, data: Any) -> Any:
        """Build test_configuration from separate fields if not already provided.

        This allows users to provide goal, instructions, restrictions, and scenario
        as separate fields instead of constructing TestConfiguration manually.
        """
        if not isinstance(data, dict):
            return data

        # If test_configuration already provided, use it and remove separate fields
        if "test_configuration" in data and data["test_configuration"] is not None:
            # Remove the separate fields if they exist
            for field in [
                "goal",
                "instructions",
                "restrictions",
                "scenario",
                "max_turns",
                "min_turns",
            ]:
                data.pop(field, None)
            return data

        # Build test_configuration from separate fields if goal is provided
        goal = data.get("goal")
        if goal:
            config_data = {
                "goal": goal,
                "instructions": data.get("instructions", ""),
                "restrictions": data.get("restrictions", ""),
                "scenario": data.get("scenario", ""),
            }
            # Include turn parameters if provided
            if data.get("max_turns") is not None:
                config_data["max_turns"] = data["max_turns"]
            if data.get("min_turns") is not None:
                config_data["min_turns"] = data["min_turns"]
            data["test_configuration"] = config_data
            # Remove the separate fields
            for field in [
                "goal",
                "instructions",
                "restrictions",
                "scenario",
                "max_turns",
                "min_turns",
            ]:
                data.pop(field, None)

        return data

    @model_validator(mode="before")
    @classmethod
    def map_test_metadata(cls, data: Any) -> Any:
        """Map test_metadata from backend response to metadata.

        The backend uses 'test_metadata' (to avoid SQLAlchemy reserved name),
        but the SDK uses 'metadata' for consistency.
        """
        if isinstance(data, dict):
            # If test_metadata exists and metadata doesn't, copy it over
            if "test_metadata" in data and "metadata" not in data:
                data["metadata"] = data.pop("test_metadata") or {}
            elif "test_metadata" in data:
                # Remove test_metadata if metadata already exists
                data.pop("test_metadata", None)
        return data

    @field_validator("category", "topic", "behavior", mode="before")
    @classmethod
    def extract_name_from_dict(cls, v: Any) -> Optional[str]:
        """Extract name from nested dict if backend returns full object.

        Handles:
        - None: returns None
        - str: returns as-is
        - dict: extracts 'name' key (backend API response format)
        """
        if v is None:
            return None
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return v.get("name")
        return v

    @field_validator("test_type", mode="before")
    @classmethod
    def extract_test_type(cls, v: Any) -> Optional[str]:
        """Extract type_value from nested dict if backend returns full TypeLookup object.

        Handles:
        - None: returns None
        - TestType enum: returns the enum value string
        - str: returns as-is (Pydantic handles enum conversion)
        - dict: extracts 'type_value' key (backend API response format)
        """
        if v is None:
            return None
        if isinstance(v, TestType):
            return v.value
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return v.get("type_value")
        return v

    def model_dump(self, **kwargs):
        """Exclude None turn params from test_configuration."""
        d = super().model_dump(**kwargs)
        config = d.get("test_configuration")
        if isinstance(config, dict):
            for key in ("max_turns", "min_turns"):
                if key in config and config[key] is None:
                    del config[key]
        return d

    def push(self) -> Optional[Dict[str, Any]]:
        """Save the test, then upload any attached files."""
        pending_files = self.files
        self.files = None  # Clear before super().push() serialization
        response = super().push()
        if pending_files:
            self.add_files(pending_files)
        return response

    def add_files(self, sources: list) -> List["File"]:
        """Add files to this test from paths or base64 dicts.

        Args:
            sources: List of file paths (str/Path) or dicts with keys:
                - filename (str): The file name
                - content_type (str): MIME type
                - data (str): Base64-encoded content

        Returns:
            List of File instances.
        """
        from rhesis.sdk.entities.file import File

        if not self.id:
            raise ValueError("Test must have an ID before adding files")
        return File.add(sources, entity_id=self.id, entity_type="Test")

    def get_files(self) -> List["File"]:
        """Get all files attached to this test.

        Returns:
            List of File instances.
        """
        from rhesis.sdk.entities.file import File

        if not self.id:
            raise ValueError("Test must have an ID to get files")
        client = APIClient()
        results = client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=f"{self.id}/files",
        )
        return [File.model_validate(r) for r in results]

    def delete_file(self, file_id: str) -> bool:
        """Delete a file attached to this test.

        Args:
            file_id: The ID of the file to delete.

        Returns:
            True if deleted, False if not found.
        """
        from rhesis.sdk.entities.file import File

        return File(id=file_id).delete()

    @handle_http_errors
    def execute(self, endpoint: Endpoint) -> Optional[Dict[str, Any]]:
        """Execute the test against the given endpoint.

        Args:
            endpoint: The endpoint to execute the test against

        Returns:
            Dict containing the execution results.

        Raises:
            RhesisAPIError: If the API request fails.

        Example:
            >>> test = Test(id='test-123')
            >>> endpoint = Endpoint(id='endpoint-123')
            >>> result = test.execute(endpoint=endpoint)
        """
        if not endpoint.id:
            raise ValueError("Endpoint ID must be set before executing")

        if not self.id:
            raise ValueError("Test ID must be set before executing")

        data: Dict[str, Any] = {
            "test_id": self.id,
            "endpoint_id": endpoint.id,
            "evaluate_metrics": True,
        }

        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params="execute",
            data=data,
        )


class Tests(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Test
