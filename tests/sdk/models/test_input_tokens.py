"""Input estimates count a file by what it holds, not as one image."""

import base64

from rhesis.sdk.models import input_tokens
from rhesis.sdk.models.input_tokens import (
    IMAGE_PART_TOKENS,
    PDF_PAGE_TOKENS,
    estimate_input_tokens,
)

MODEL = "gpt-4o-mini"


def _pdf(pages: int) -> bytes:
    """A minimal valid PDF with *pages* empty pages."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{i + 3} 0 R" for i in range(pages))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
    for _ in range(pages):
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 10 10] >>")
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out


def _file_message(mime: str, data: bytes) -> list:
    url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    return [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}}]}]


def test_an_image_counts_as_one_image():
    assert estimate_input_tokens(MODEL, _file_message("image/png", b"x" * 100_000)) == (
        IMAGE_PART_TOKENS
    )


def test_a_pdf_counts_by_its_pages():
    tokens = estimate_input_tokens(MODEL, _file_message("application/pdf", _pdf(50)))
    assert tokens == 50 * PDF_PAGE_TOKENS


def test_a_small_pdf_counts_at_least_as_an_image():
    tokens = estimate_input_tokens(MODEL, _file_message("application/pdf", _pdf(1)))
    assert tokens == IMAGE_PART_TOKENS


def test_page_markers_are_the_fallback_when_pdfminer_cannot_read_it():
    broken = b"%PDF-1.4 garbage " + b"<< /Type /Page >> " * 30 + b"<< /Type /Pages >>"
    tokens = estimate_input_tokens(MODEL, _file_message("application/pdf", broken))
    assert tokens == 30 * PDF_PAGE_TOKENS


def test_another_file_counts_by_its_size():
    data = b"x" * 400_000
    tokens = estimate_input_tokens(MODEL, _file_message("application/msword", data))
    assert tokens == len(data) // input_tokens.BYTES_PER_TOKEN


def test_text_and_files_add_up():
    message = _file_message("image/png", b"x")
    message[0]["content"].append({"type": "text", "text": "describe this"})
    tokens = estimate_input_tokens(MODEL, message)
    assert IMAGE_PART_TOKENS < tokens < IMAGE_PART_TOKENS + 20


def test_long_text_skips_the_tokenizer():
    chars = input_tokens.TOKENIZE_MAX_CHARS + 3
    tokens = estimate_input_tokens(MODEL, [{"role": "user", "content": "x" * chars}])
    assert tokens == chars // input_tokens.CHARS_PER_TOKEN_ESTIMATE
