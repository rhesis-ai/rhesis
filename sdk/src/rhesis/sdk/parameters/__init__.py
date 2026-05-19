"""Parameters facade for resolving project-scoped configuration.

Provides a ``Parameters`` class with class methods for fetching resolved
parameter values from the Rhesis backend. Caching ensures immutable
version lookups are stored forever while environment-based and
experiment-id lookups use a TTL.

Usage::

    from rhesis.sdk import Parameters
    from rhesis.sdk.models.parameters import BuiltInEnvironment

    params = Parameters.get(
        project="my-project",
        environment=BuiltInEnvironment.DEFAULT,
    )
    print(params["temperature"])       # native Python value
    print(params.get_string("model"))  # typed accessor

Resolution order: ``version`` (immutable pin) > ``experiment_id``
(latest version) > ``environment`` (movable pointer) > implicit
:attr:`~rhesis.sdk.models.parameters.BuiltInEnvironment.DEFAULT`.
"""

from rhesis.sdk.parameters._facade import Parameters

__all__ = ["Parameters"]
