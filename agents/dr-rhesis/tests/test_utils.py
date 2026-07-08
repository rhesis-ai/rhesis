import pytest

from dr_rhesis.utils import extract_json_object


def test_extract_json_plain():
    assert extract_json_object('{"intent": "greeting"}') == {"intent": "greeting"}


def test_extract_json_fenced():
    text = 'Here is JSON:\n```json\n{"approved": true, "feedback": ""}\n```'
    assert extract_json_object(text)["approved"] is True


def test_extract_json_missing():
    with pytest.raises(ValueError):
        extract_json_object("no json here")
