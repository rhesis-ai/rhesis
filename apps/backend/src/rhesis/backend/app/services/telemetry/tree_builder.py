"""
Utility for building hierarchical span trees from flat span lists.
"""

from typing import Dict, List

from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.schemas.telemetry import SpanNode


def build_span_tree(spans: List[Trace]) -> List[SpanNode]:
    """
    Build hierarchical span tree from flat span list.

    Converts a flat list of Trace models into a tree structure where
    each span's children are properly nested. Returns a list of root
    span nodes (spans with no parent).

    Args:
        spans: List of Trace models from database

    Returns:
        List of root SpanNode objects with children populated recursively

    Example:
        Given spans:
        - span_a (parent=None)
          - span_b (parent=span_a)
            - span_c (parent=span_b)
          - span_d (parent=span_a)

        Returns:
        [
            SpanNode(
                span_id="span_a",
                children=[
                    SpanNode(span_id="span_b", children=[
                        SpanNode(span_id="span_c", children=[])
                    ]),
                    SpanNode(span_id="span_d", children=[])
                ]
            )
        ]
    """
    if not spans:
        return []

    # Create span map for O(1) lookup
    span_map: Dict[str, SpanNode] = {}

    # Convert all spans to SpanNode objects
    for span in spans:
        node = SpanNode(
            span_id=span.span_id,
            span_name=span.span_name,
            span_kind=span.span_kind,
            start_time=span.start_time,
            end_time=span.end_time,
            duration_ms=span.duration_ms or 0.0,
            status_code=span.status_code,
            status_message=span.status_message,
            attributes=span.attributes or {},
            events=span.events or [],
            children=[],  # Will be populated below
            tags=None,  # TODO: Populate from span.tags relationship
            comments=None,  # TODO: Populate from span.comments relationship
        )
        span_map[span.span_id] = node

    # Build parent-child relationships
    root_nodes: List[SpanNode] = []

    for span in spans:
        node = span_map[span.span_id]

        if span.parent_span_id and span.parent_span_id in span_map:
            # This span has a parent - add to parent's children
            parent = span_map[span.parent_span_id]
            parent.children.append(node)
        else:
            # This is a root span (no parent or parent not in trace)
            root_nodes.append(node)

    # Sort children by start_time for consistent ordering
    def sort_children_recursive(node: SpanNode):
        node.children.sort(key=lambda x: x.start_time)
        for child in node.children:
            sort_children_recursive(child)

    for root in root_nodes:
        sort_children_recursive(root)

    # Sort root nodes by start_time
    root_nodes.sort(key=lambda x: x.start_time)

    return root_nodes


def count_spans_in_tree(root_spans: List[SpanNode]) -> int:
    """
    Count total number of spans in a tree structure.

    Args:
        root_spans: List of root span nodes

    Returns:
        Total count of spans including all nested children
    """

    def count_recursive(node: SpanNode) -> int:
        count = 1  # Count this node
        for child in node.children:
            count += count_recursive(child)
        return count

    total = 0
    for root in root_spans:
        total += count_recursive(root)

    return total


def find_span_by_id(root_spans: List[SpanNode], span_id: str) -> SpanNode | None:
    """
    Find a specific span by ID in the tree.

    Args:
        root_spans: List of root span nodes
        span_id: Span ID to search for

    Returns:
        SpanNode if found, None otherwise
    """

    def search_recursive(node: SpanNode) -> SpanNode | None:
        if node.span_id == span_id:
            return node

        for child in node.children:
            result = search_recursive(child)
            if result:
                return result

        return None

    for root in root_spans:
        result = search_recursive(root)
        if result:
            return result

    return None
