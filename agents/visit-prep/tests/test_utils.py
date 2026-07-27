import pytest

from visit_prep.utils import extract_json_object, normalize_slot_payload


def test_extract_json_plain():
    assert extract_json_object('{"intent": "greeting"}') == {"intent": "greeting"}


def test_normalize_slot_payload_blanks_become_none():
    payload = {"onset": "", "location": "   ", "severity": 7, "character": "sharp"}
    normalized = normalize_slot_payload(payload)
    assert normalized["onset"] is None
    assert normalized["location"] is None
    assert normalized["severity"] == "7"
    assert normalized["character"] == "sharp"


def test_extract_json_fenced():
    text = 'Here is JSON:\n```json\n{"approved": true, "feedback": ""}\n```'
    assert extract_json_object(text)["approved"] is True


def test_extract_json_missing():
    with pytest.raises(ValueError):
        extract_json_object("no json here")
