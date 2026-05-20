"""Parameters facade for resolving project-scoped configuration.

Provides a ``Parameters`` class with class methods for fetching resolved
parameter values from the Rhesis backend. Accepts a project name or
UUID. Caching ensures immutable version lookups are stored forever
while environment-based and experiment-id lookups use a TTL.

Usage::

    from rhesis.sdk import Parameters

    # By project name (resolved to UUID automatically)
    params = Parameters.get("My App")
    params.model          # "gpt-4o"
    params.temperature    # 0.7
    params["max_tokens"]  # 1024

    # Or from a Project entity
    from rhesis.sdk.entities import Projects

    project = Projects.pull(name="My App")
    params = project.parameters()

Resolution order: ``version`` (immutable pin) > ``experiment_id``
(latest version) > ``environment`` (movable pointer) > implicit
:attr:`~rhesis.sdk.models.parameters.BuiltInEnvironment.DEFAULT`.
"""

from rhesis.sdk.parameters._facade import Parameters

__all__ = ["Parameters"]
