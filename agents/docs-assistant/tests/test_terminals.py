from docs_assistant import terminals


def test_every_template_exists_in_every_language():
    keys = set(terminals._TEXT["en"])
    for language, texts in terminals._TEXT.items():
        assert set(texts) == keys, language


def test_language_falls_back_to_english():
    assert terminals.language_key("de-AT") == "de"
    assert terminals.language_key("fr") == "en"
    assert terminals.language_key(None) == "en"
    assert terminals.text("empty", "fr") == terminals.text("empty", "en")


def test_german_replies_are_german():
    assert terminals.out_of_scope("de").startswith("Dabei kann ich leider nicht helfen")
    assert "Wie installiere ich das Rhesis SDK?" in terminals.smalltalk("de")


def test_smalltalk_lists_example_questions():
    reply = terminals.smalltalk("en")
    assert reply.count("\n- ") == 4


def test_support_links_include_the_bug_report_template():
    urls = [s.url for s in terminals.SUPPORT_STEPS]
    assert "https://github.com/rhesis-ai/rhesis/issues/new?template=bug_report.md" in urls
    assert terminals.links(terminals.SUPPORT_STEPS).count("](https://") == 3


def test_placeholders_are_filled():
    assert "first 3" in terminals.text("parts_capped", "en", n=3)
    assert "2000" in terminals.text("input_clipped", "de", n=2000)
