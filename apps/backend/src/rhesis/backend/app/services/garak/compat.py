"""
Compatibility helpers for garak API changes across versions.

When upgrading garak, this is the first file to update.
Each helper documents which version introduced the change.
"""

from typing import Optional


def get_probe_detector(probe_class) -> Optional[str]:
    """
    Get the recommended detector from a probe class.

    v0.13.3+: primary_detector (str) is preferred.
    v0.9.x:   recommended_detector (list[str]) was used.
    """
    if hasattr(probe_class, "primary_detector") and probe_class.primary_detector:
        return probe_class.primary_detector
    rd = getattr(probe_class, "recommended_detector", None)
    if isinstance(rd, (list, tuple)) and rd:
        return rd[0] if rd[0] != "always.Fail" else None
    if isinstance(rd, str) and rd != "always.Fail":
        return rd
    return None


def get_probe_base_class():
    """
    Import and return the garak Probe base class.

    Centralizes the import so changes to garak's module structure
    only need to be updated here.
    """
    from garak.probes.base import Probe

    return Probe
