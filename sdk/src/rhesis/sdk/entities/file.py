import base64
import mimetypes
from io import BytesIO
from pathlib import Path
from typing import ClassVar, List, Optional, Union

from rhesis.sdk.clients import APIClient, Endpoints, Methods
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.FILES


class File(BaseEntity):
    """File entity for managing file attachments on Tests and TestResults.

    Files cannot be created via push(). Use File.add() or entity helper
    methods (e.g. Test.add_files()) instead.
    """

    __test__ = False  # Tell pytest to ignore this class
    endpoint: ClassVar[Endpoints] = ENDPOINT

    filename: str = ""
    content_type: str = ""
    size_bytes: int = 0
    description: Optional[str] = None
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    position: int = 0
    id: Optional[str] = None

    @classmethod
    def add(
        cls,
        sources: List[Union[str, Path, dict]],
        entity_id: str,
        entity_type: str,
    ) -> List["File"]:
        """Upload files from paths or base64 dicts.

        Args:
            sources: List of file paths (str/Path) or dicts with keys:
                - filename (str): The file name
                - content_type (str): MIME type
                - data (str): Base64-encoded file content
            entity_id: ID of the entity to attach files to.
            entity_type: Entity type ("Test" or "TestResult").

        Returns:
            List of File instances from the API response.
        """
        file_tuples = []
        open_files = []

        try:
            for source in sources:
                if isinstance(source, (str, Path)):
                    path = Path(source)
                    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
                    f = open(path, "rb")
                    open_files.append(f)
                    file_tuples.append(("files", (path.name, f, mime)))
                elif isinstance(source, dict):
                    raw = base64.b64decode(source["data"])
                    file_tuples.append(
                        (
                            "files",
                            (
                                source["filename"],
                                BytesIO(raw),
                                source["content_type"],
                            ),
                        )
                    )
                else:
                    raise TypeError(f"Unsupported source type: {type(source)}")

            client = APIClient()
            results = client.send_file_upload(
                endpoint=ENDPOINT,
                files=file_tuples,
                params={
                    "entity_id": str(entity_id),
                    "entity_type": entity_type,
                },
            )
        finally:
            for f in open_files:
                f.close()

        return [cls.model_validate(r) for r in results]

    def download(self, directory: Union[str, Path] = ".") -> Path:
        """Download file content and save to a local directory.

        Args:
            directory: Target directory (default: current directory).

        Returns:
            Path to the saved file.

        Raises:
            ValueError: If the file has no ID.
        """
        if not self.id:
            raise ValueError("File ID is required for download")

        client = APIClient()
        response = client.send_raw_request(
            endpoint=ENDPOINT,
            method=Methods.GET,
            url_params=f"{self.id}/content",
        )

        dest = Path(directory)
        dest.mkdir(parents=True, exist_ok=True)
        file_path = dest / self.filename
        file_path.write_bytes(response.content)
        return file_path

    def push(self):
        """Not supported for File. Use File.add() instead."""
        raise NotImplementedError("Use File.add() or entity.add_files() to upload files")
