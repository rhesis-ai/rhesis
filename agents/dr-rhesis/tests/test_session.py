"""Session-layer regression tests."""

from __future__ import annotations

from dr_rhesis.session import StateStore, run_chat_turn
from tests.mocks import make_components


def test_run_chat_turn_reuses_pipeline_across_turns():
    """Multiple turns with one components bundle must not rebuild the pipeline.

    Haystack forbids adding the same component instances to a second Pipeline,
    so rebuilding per turn raised PipelineError on turn two.
    """
    components = make_components(
        [
            '{"intent": "greeting"}',
            '{"intent": "greeting"}',
        ]
    )
    store = StateStore()

    first = run_chat_turn("hello", store=store, components=components)
    second = run_chat_turn(
        "hi again",
        conversation_id=first["conversation_id"],
        store=store,
        components=components,
    )

    assert second["conversation_id"] == first["conversation_id"]
    assert second["state"].turn == 2
