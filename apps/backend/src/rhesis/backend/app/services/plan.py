"""The org's plan, as a display contract.

One builder, :func:`build_plan`, turning a license provider's ``info`` dict
into the payload clients render. It is a pure function of that dict -- no
database access -- which is why ``GET /features`` can carry the plan for free:
that endpoint already resolves ``license_info`` for its own ``license`` field.

This lives apart from the usage service on purpose. A plan is a *licensing*
fact, not an accounting one, and it first shipped on ``GET /usage`` only
because that was where the sidebar happened to fetch. Being cheap to compute
means the transport can be chosen for where clients need it -- and they need it
on first paint, everywhere, which is ``GET /features`` (server-seeded in the
protected layout) rather than ``GET /usage`` (client-fetched, one round trip
behind).
"""

from __future__ import annotations

__all__ = ["build_plan"]


def build_plan(license_info: dict) -> dict:
    """Build the plan payload a client renders, from a provider's ``info`` dict.

    Returns ``{name, is_paid, is_active}``:

    - ``name`` is the **display label, rendered verbatim by clients.** It is
      composed here, on purpose: a client that title-cases or appends to it is
      a client that has to be changed every time a tier is added or renamed.
      Building it once server-side means a new tier appears correctly in every
      surface with no frontend release.
    - ``is_paid`` describes the *tier*; ``is_active`` describes the *licence*.
      Both are needed, and the pair is why this exists: a free org is
      ``(False, False)`` and a lapsed enterprise is ``(True, False)``. With
      only one flag a client cannot separate them, which previously left the
      UI inferring "is this paid?" from the edition string -- so a renamed or
      newly added tier silently rendered as free.

    A lapsed paid tier carries the qualifier in ``name``, so the state is
    legible even where styling is not (a screenshot, a narrow column, a
    monochrome theme).
    """
    edition = str(license_info.get("edition", "community"))
    is_paid = bool(license_info.get("is_paid", False))
    is_active = bool(license_info.get("licensed", False))

    name = edition.replace("_", " ").replace("-", " ").strip().title() or "Unknown"
    if is_paid and not is_active:
        name = f"{name} (inactive)"

    return {"name": name, "is_paid": is_paid, "is_active": is_active}
