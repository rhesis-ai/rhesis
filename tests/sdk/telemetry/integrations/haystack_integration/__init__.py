"""Tests for the Haystack telemetry integration.

A package rather than flat modules so the autouse fixtures in ``conftest.py`` -- which force
Haystack's content-tracing flag on and reset process-wide tracing state -- stay scoped to these
tests instead of leaking into the other integrations' tests.

Named ``haystack_integration`` rather than ``haystack``: pytest puts this package's parent
directory on ``sys.path``, so a package named ``haystack`` here would shadow the real
``haystack`` distribution and every import of it would resolve to this directory.
"""
