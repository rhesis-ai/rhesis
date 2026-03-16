"""
Compatibility helpers for garak API changes across versions.

When upgrading garak, this is the first file to update.
Each helper documents which version introduced the change.
"""

from typing import Dict, Optional

# Detectors that are local models and cannot be run ad hoc by Rhesis.
# Map each to an API-based equivalent that provides comparable coverage.
DETECTOR_OVERRIDES: Dict[str, str] = {
    "garak.detectors.unsafe_content.ToxicCommentModel": ("garak.detectors.perspective.Toxicity"),
}


def get_probe_detector(probe_class) -> Optional[str]:
    """
    Get the recommended detector from a probe class.

    v0.13.3+: primary_detector (str) is preferred.
    v0.9.x:   recommended_detector (list[str]) was used.

    Applies DETECTOR_OVERRIDES to replace local-model detectors with
    API-based equivalents that Rhesis can run.
    """
    detector = None
    if hasattr(probe_class, "primary_detector") and probe_class.primary_detector:
        detector = probe_class.primary_detector
    else:
        rd = getattr(probe_class, "recommended_detector", None)
        if isinstance(rd, (list, tuple)) and rd:
            detector = rd[0] if rd[0] != "always.Fail" else None
        elif isinstance(rd, str) and rd != "always.Fail":
            detector = rd

    if detector:
        detector = DETECTOR_OVERRIDES.get(detector, detector)

    return detector


def get_probe_base_class():
    """
    Import and return the garak Probe base class.

    Centralizes the import so changes to garak's module structure
    only need to be updated here.
    """
    from garak.probes.base import Probe

    return Probe
