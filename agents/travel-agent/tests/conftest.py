"""Makes ``tests.mocks`` importable from the test modules.

Deliberately holds no fixtures: the scripted client is constructed per test, because each
test's script is the point of the test.
"""
