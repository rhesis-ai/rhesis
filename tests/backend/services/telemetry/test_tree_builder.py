"""Tests for span tree builder."""

from datetime import datetime, timedelta

from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.services.telemetry.tree_builder import (
    build_span_tree,
    count_spans_in_tree,
    find_span_by_id,
)


def create_mock_span(
    span_id: str,
    parent_span_id: str | None,
    span_name: str,
    start_offset_ms: int = 0,
) -> Trace:
    """Helper to create mock Trace object."""
    base_time = datetime.utcnow()

    span = Trace()
    span.span_id = span_id
    span.parent_span_id = parent_span_id
    span.span_name = span_name
    span.span_kind = "INTERNAL"
    span.start_time = base_time + timedelta(milliseconds=start_offset_ms)
    span.end_time = base_time + timedelta(milliseconds=start_offset_ms + 100)
    span.duration_ms = 100.0
    span.status_code = "OK"
    span.status_message = None
    span.attributes = {"function.name": span_name}
    span.events = []

    return span


def test_build_simple_tree():
    """Test building a simple two-level tree."""
    spans = [
        create_mock_span("root", None, "function.root", 0),
        create_mock_span("child1", "root", "function.child1", 10),
        create_mock_span("child2", "root", "function.child2", 20),
    ]

    tree = build_span_tree(spans)

    assert len(tree) == 1  # One root
    assert tree[0].span_id == "root"
    assert len(tree[0].children) == 2
    assert tree[0].children[0].span_id == "child1"
    assert tree[0].children[1].span_id == "child2"


def test_build_deep_tree():
    """Test building a deeply nested tree."""
    spans = [
        create_mock_span("root", None, "function.root", 0),
        create_mock_span("child", "root", "function.child", 10),
        create_mock_span("grandchild", "child", "function.grandchild", 20),
        create_mock_span("great_grandchild", "grandchild", "function.ggc", 30),
    ]

    tree = build_span_tree(spans)

    assert len(tree) == 1
    assert tree[0].span_id == "root"
    assert len(tree[0].children) == 1
    assert tree[0].children[0].span_id == "child"
    assert len(tree[0].children[0].children) == 1
    assert tree[0].children[0].children[0].span_id == "grandchild"


def test_multiple_roots():
    """Test handling multiple root spans."""
    spans = [
        create_mock_span("root1", None, "function.root1", 0),
        create_mock_span("root2", None, "function.root2", 10),
        create_mock_span("child1", "root1", "function.child1", 5),
    ]

    tree = build_span_tree(spans)

    assert len(tree) == 2
    assert tree[0].span_id == "root1"
    assert tree[1].span_id == "root2"
    assert len(tree[0].children) == 1


def test_count_spans():
    """Test counting spans in tree."""
    spans = [
        create_mock_span("root", None, "function.root", 0),
        create_mock_span("child1", "root", "function.child1", 10),
        create_mock_span("child2", "root", "function.child2", 20),
        create_mock_span("grandchild", "child1", "function.grandchild", 15),
    ]

    tree = build_span_tree(spans)
    count = count_spans_in_tree(tree)

    assert count == 4


def test_find_span_by_id():
    """Test finding span by ID in tree."""
    spans = [
        create_mock_span("root", None, "function.root", 0),
        create_mock_span("child", "root", "function.child", 10),
        create_mock_span("grandchild", "child", "function.grandchild", 20),
    ]

    tree = build_span_tree(spans)

    found = find_span_by_id(tree, "grandchild")
    assert found is not None
    assert found.span_id == "grandchild"

    not_found = find_span_by_id(tree, "nonexistent")
    assert not_found is None


def test_empty_spans():
    """Test handling empty span list."""
    tree = build_span_tree([])
    assert tree == []
    assert count_spans_in_tree(tree) == 0


def test_orphan_span():
    """Test handling span with missing parent."""
    spans = [
        create_mock_span("root", None, "function.root", 0),
        create_mock_span("orphan", "missing_parent", "function.orphan", 10),
    ]

    tree = build_span_tree(spans)

    # Orphan should become a root since parent is missing
    assert len(tree) == 2
    span_ids = [s.span_id for s in tree]
    assert "root" in span_ids
    assert "orphan" in span_ids


def test_children_sorted_by_start_time():
    """Test that children are sorted by start_time."""
    spans = [
        create_mock_span("root", None, "function.root", 0),
        create_mock_span("child3", "root", "function.child3", 30),  # Latest
        create_mock_span("child1", "root", "function.child1", 10),  # Earliest
        create_mock_span("child2", "root", "function.child2", 20),  # Middle
    ]

    tree = build_span_tree(spans)

    assert len(tree[0].children) == 3
    # Should be sorted by start_time (child1, child2, child3)
    assert tree[0].children[0].span_id == "child1"
    assert tree[0].children[1].span_id == "child2"
    assert tree[0].children[2].span_id == "child3"


def test_root_spans_sorted_by_start_time():
    """Test that root spans are sorted by start_time."""
    spans = [
        create_mock_span("root3", None, "function.root3", 30),  # Latest
        create_mock_span("root1", None, "function.root1", 10),  # Earliest
        create_mock_span("root2", None, "function.root2", 20),  # Middle
    ]

    tree = build_span_tree(spans)

    assert len(tree) == 3
    # Should be sorted by start_time (root1, root2, root3)
    assert tree[0].span_id == "root1"
    assert tree[1].span_id == "root2"
    assert tree[2].span_id == "root3"


def test_attributes_and_events_preserved():
    """Test that attributes and events are preserved in tree."""
    spans = [
        create_mock_span("root", None, "function.root", 0),
    ]
    spans[0].attributes = {"custom.key": "custom.value", "function.name": "root"}
    spans[0].events = [{"name": "test_event", "timestamp": datetime.utcnow()}]

    tree = build_span_tree(spans)

    assert tree[0].attributes["custom.key"] == "custom.value"
    assert len(tree[0].events) == 1
    assert tree[0].events[0]["name"] == "test_event"


def test_span_metadata_preserved():
    """Test that span metadata (name, kind, status, etc.) is preserved."""
    spans = [
        create_mock_span("root", None, "function.root", 0),
    ]
    spans[0].span_kind = "SERVER"
    spans[0].status_code = "ERROR"
    spans[0].status_message = "Test error message"
    spans[0].duration_ms = 250.5

    tree = build_span_tree(spans)

    assert tree[0].span_kind == "SERVER"
    assert tree[0].status_code == "ERROR"
    assert tree[0].status_message == "Test error message"
    assert tree[0].duration_ms == 250.5
