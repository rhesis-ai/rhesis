"""Rule-based red-flag detection."""

from haystack.dataclasses import ChatMessage

from visit_prep.safety import first_red_flag_text, text_suggests_red_flag


def test_chest_pain_red_flag():
    assert text_suggests_red_flag("I have crushing chest pain")


def test_mild_headache_not_red_flag():
    assert not text_suggests_red_flag("I have a mild headache")


def test_first_red_flag_text_scans_the_whole_conversation():
    """Scanning every user turn is what makes escalation sticky across turns."""
    messages = [
        ChatMessage.from_system("you are a coordinator"),
        ChatMessage.from_user("I've been fine"),
        ChatMessage.from_assistant("Tell me more."),
        ChatMessage.from_user("Now I can't breathe and have chest pain"),
    ]
    assert first_red_flag_text(messages) == "Now I can't breathe and have chest pain"


def test_first_red_flag_text_ignores_assistant_wording():
    """The assistant's own escalation copy must not re-trigger the check."""
    from visit_prep.terminals import escalate

    messages = [
        ChatMessage.from_user("I have a mild headache"),
        ChatMessage.from_assistant(escalate()),
    ]
    assert first_red_flag_text(messages) is None


def test_first_red_flag_text_returns_none_when_clear():
    messages = [ChatMessage.from_user("mild headache for two days")]
    assert first_red_flag_text(messages) is None
