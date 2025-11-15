import tempfile
import os

def create_temp_document(content: str) -> str:
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        return f.name

def cleanup_file(file_path: str):
    if os.path.exists(file_path):
        os.unlink(file_path)
