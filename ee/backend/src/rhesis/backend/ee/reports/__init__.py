"""Enterprise report sections and the report audit trail.

Core reports are complete on their own. EE adds, through core's report-section
registry, the By impact, Who was involved and Stats sections (gated on
``FeatureName.ADVANCED_REPORTS``) and a live audit trail route (gated on
``FeatureName.AUDIT_LOG``, mounted from :func:`~rhesis.backend.ee.bootstrap`).
"""

from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.app.services.report.sections import ReportSection, register_report_section
from rhesis.backend.ee.reports.sections import build_by_impact, build_people, build_stats

SECTIONS = (
    ReportSection("by_impact", FeatureName.ADVANCED_REPORTS, build_by_impact),
    ReportSection("people", FeatureName.ADVANCED_REPORTS, build_people),
    ReportSection("stats", FeatureName.ADVANCED_REPORTS, build_stats),
)


def register_reports() -> None:
    """Register the feature and its sections. Idempotent."""
    FeatureRegistry.register(
        Feature(
            name=FeatureName.ADVANCED_REPORTS,
            display_name="Advanced reports",
            description="Report sections by impact, who was involved, and stats.",
        )
    )
    for section in SECTIONS:
        register_report_section(section)
