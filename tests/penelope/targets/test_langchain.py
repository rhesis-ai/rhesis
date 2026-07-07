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
