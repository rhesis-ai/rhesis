"""Tests for LangChainTarget file-attachment support."""

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda

from rhesis.penelope.targets.langchain import LangChainTarget

SAMPLE_FILES = [
    {"filename": "image.png", "content_type": "image/png", "data": "aW1hZ2U="},
]


def _echo_target():
    received = {}

    def echo(x):
        received["input"] = x
        return "ok"

    target = LangChainTarget(RunnableLambda(echo), "test-target")
    return target, received


def test_send_message_without_files_uses_input_key_dict():
    target, received = _echo_target()

    target.send_message("hello")

    assert received["input"] == {"input": "hello"}


def test_send_message_with_files_passes_human_message():
    target, received = _echo_target()

    response = target.send_message("What is this?", files=SAMPLE_FILES)

    assert response.success is True
    assert isinstance(received["input"], HumanMessage)


def test_send_message_with_files_builds_content_blocks():
    target, received = _echo_target()

    target.send_message("What is this?", files=SAMPLE_FILES)

    content = received["input"].content
    assert content[0]["type"] == "text"
    assert content[0]["text"] == "What is this?"
    assert content[1]["type"] == "image"
    assert content[1]["mime_type"] == "image/png"


# --- Native async path (a_send_message via ainvoke) ---


class _AsyncOnlyRunnable:
    """Runnable whose async path is observable: ainvoke records, invoke fails.

    Ensures a_send_message really goes through ainvoke() rather than the
    base-class thread-pool fallback (which would call invoke()).
    """

    def __init__(self):
        self.received = {}

    def invoke(self, x, config=None):
        raise AssertionError("sync invoke() must not be called by a_send_message")

    async def ainvoke(self, x, config=None):
        self.received["input"] = x
        return "async ok"


def test_a_send_message_uses_native_ainvoke():
    import asyncio

    runnable = _AsyncOnlyRunnable()
    target = LangChainTarget(runnable, "test-target")

    response = asyncio.run(target.a_send_message("hello"))

    assert response.success is True
    assert response.content == "async ok"
    assert runnable.received["input"] == {"input": "hello"}


def test_a_send_message_with_files_builds_content_blocks():
    import asyncio

    runnable = _AsyncOnlyRunnable()
    target = LangChainTarget(runnable, "test-target")

    response = asyncio.run(target.a_send_message("What is this?", files=SAMPLE_FILES))

    assert response.success is True
    received = runnable.received["input"]
    assert isinstance(received, HumanMessage)
    assert received.content[0]["type"] == "text"
    assert received.content[1]["type"] == "image"


def test_a_send_message_with_file_reference_uses_aread_bytes():
    import asyncio

    class _FakeFileReference:
        def __init__(self):
            self.filename = "photo.png"
            self.content_type = "image/png"
            self.extracted_text = None
            self.aread_called = False

        def read_bytes(self):
            raise AssertionError("blocking read_bytes() must not be used on the async path")

        async def aread_bytes(self):
            self.aread_called = True
            return b"rawbytes"

    runnable = _AsyncOnlyRunnable()
    target = LangChainTarget(runnable, "test-target")
    file_ref = _FakeFileReference()

    response = asyncio.run(target.a_send_message("What is this?", files=[file_ref]))

    assert response.success is True
    assert file_ref.aread_called is True


def test_a_send_message_error_is_captured():
    import asyncio

    class _Boom:
        def invoke(self, x, config=None):
            raise AssertionError("must use ainvoke")

        async def ainvoke(self, x, config=None):
            raise RuntimeError("async boom")

    target = LangChainTarget(_Boom(), "test-target")
    response = asyncio.run(target.a_send_message("hello"))

    assert response.success is False
    assert "async boom" in response.error
