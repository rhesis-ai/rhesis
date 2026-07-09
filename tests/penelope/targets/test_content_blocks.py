"""Tests for the files_to_content_blocks helper shared by LangChain/LangGraph targets."""

from rhesis.penelope.targets._content_blocks import files_to_content_blocks

SAMPLE_FILES = [
    {"filename": "image.png", "content_type": "image/png", "data": "aW1hZ2U="},
    {"filename": "document.pdf", "content_type": "application/pdf", "data": "ZG9j"},
    {"filename": "clip.mp3", "content_type": "audio/mpeg", "data": "YXVkaW8="},
    {"filename": "clip.mp4", "content_type": "video/mp4", "data": "dmlkZW8="},
]


def test_no_files_returns_plain_message():
    result = files_to_content_blocks("hello", None)
    assert result == "hello"


def test_empty_files_returns_plain_message():
    result = files_to_content_blocks("hello", [])
    assert result == "hello"


def test_files_returns_block_list_with_text_first():
    result = files_to_content_blocks("hello", SAMPLE_FILES[:1])
    assert isinstance(result, list)
    assert result[0]["type"] == "text"
    assert result[0]["text"] == "hello"


def test_image_file_becomes_image_block():
    result = files_to_content_blocks("x", [SAMPLE_FILES[0]])
    block = result[1]
    assert block["type"] == "image"
    assert block["base64"] == "aW1hZ2U="
    assert block["mime_type"] == "image/png"


def test_pdf_file_becomes_file_block():
    result = files_to_content_blocks("x", [SAMPLE_FILES[1]])
    assert result[1]["type"] == "file"
    assert result[1]["mime_type"] == "application/pdf"


def test_audio_file_becomes_audio_block():
    result = files_to_content_blocks("x", [SAMPLE_FILES[2]])
    assert result[1]["type"] == "audio"


def test_video_file_becomes_video_block():
    result = files_to_content_blocks("x", [SAMPLE_FILES[3]])
    assert result[1]["type"] == "video"


def test_multiple_files_all_attached():
    result = files_to_content_blocks("x", SAMPLE_FILES)
    assert len(result) == len(SAMPLE_FILES) + 1


class _FakeFileReference:
    def __init__(self, filename, content_type, content, extracted_text=None):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self.extracted_text = extracted_text

    def read_bytes(self):
        return self._content


def test_file_reference_without_extracted_text_becomes_binary_block():
    file_ref = _FakeFileReference("photo.png", "image/png", b"rawbytes")
    result = files_to_content_blocks("What is this?", [file_ref])

    assert result[1]["type"] == "image"
    assert result[1]["mime_type"] == "image/png"


def test_file_reference_with_extracted_text_becomes_text_block():
    file_ref = _FakeFileReference(
        "doc.pdf", "application/pdf", b"unused", extracted_text="Hello from PDF"
    )
    result = files_to_content_blocks("Summarize", [file_ref])

    assert result[1]["type"] == "text"
    assert "doc.pdf" in result[1]["text"]
    assert "Hello from PDF" in result[1]["text"]


def test_image_with_ocr_extracted_text_still_becomes_image_block():
    # The backend OCRs images into extracted_text; the real image must still
    # reach the target instead of being replaced by the OCR text.
    file_ref = _FakeFileReference("photo.png", "image/png", b"rawbytes", extracted_text="OCR text")
    result = files_to_content_blocks("What is this?", [file_ref])

    assert result[1]["type"] == "image"
    assert result[1]["mime_type"] == "image/png"
