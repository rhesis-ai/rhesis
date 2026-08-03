"""Guards that the email templates stay on the current brand.

The templates went through three visual generations before this — old-brand
(Be Vietnam Pro, #2AA1CE), generic Bootstrap (Arial, #007bff, alert greens and
reds), and the current one. Nothing structural stops a fourth from creeping
back in one template at a time, so these tests render every template and fail
on the specific markers of the old ones.

Pure unit tests: Jinja only, nothing is sent.
"""

import re

import pytest

from rhesis.backend.notifications.email.brand import get_brand
from rhesis.backend.notifications.email.template_service import EmailTemplate, TemplateService
from tests.notifications.email_fixtures import FIXTURES, VARIANTS

# Hex values and font names from the superseded generations. Matched
# case-insensitively — the old templates mixed #2AA1CE and #2aa1ce.
RETIRED_COLORS = [
    "#2AA1CE",  # old brand primary
    "#50B9E0",  # old brand light blue
    "#F2F9FD",  # old brand tint
    "#E4F2FA",  # old brand tint
    "#3D3D3D",  # old brand body text
    "#F38755",  # old brand link
    "#e5f2ff",  # blue panel tint — clashed with the header wash, now neutral
    "#007bff",  # Bootstrap primary
    "#1976d2",  # Material blue
    "#0ea5e9",
    "#f8f9fa",  # Bootstrap panel
    "#dee2e6",  # Bootstrap border
    "#e9ecef",
    "#868e96",
    "#6c757d",
    "#d4edda",  # Bootstrap alert success
    "#28a745",
    "#155724",
    "#f8d7da",  # Bootstrap alert danger
    "#dc3545",
    "#721c24",
    "#fff3cd",  # Bootstrap alert warning
    "#856404",
    "#2c3e50",
    "#1D2939",
    "#495057",
]

RETIRED_FONTS = ["Be Vietnam Pro", "Plus Jakarta", "DM Sans", "JetBrains Mono"]


def _cases():
    cases = [
        (template.value.removesuffix(".html.jinja2"), template, variables)
        for template, variables in FIXTURES.items()
    ]
    cases.extend(VARIANTS)
    return cases


CASES = _cases()
CASE_IDS = [name for name, _, _ in CASES]


@pytest.fixture(scope="module")
def rendered() -> dict[str, str]:
    """Every template rendered once, keyed by case name."""
    service = TemplateService()
    return {name: service.render_template(template, dict(v)) for name, template, v in CASES}


def test_every_template_has_a_case():
    """A new template without a fixture would silently skip every check here."""
    covered = {template for _, template, _ in CASES}
    missing = sorted(t.value for t in set(EmailTemplate) - covered)
    assert covered == set(EmailTemplate), f"templates with no preview fixture: {missing}"


@pytest.mark.parametrize("name", CASE_IDS)
def test_no_retired_colors(rendered: dict[str, str], name: str):
    html = rendered[name]
    found = [color for color in RETIRED_COLORS if color.lower() in html.lower()]
    assert not found, f"{name} uses retired colours: {found}"


@pytest.mark.parametrize("name", CASE_IDS)
def test_no_retired_fonts(rendered: dict[str, str], name: str):
    html = rendered[name]
    found = [font for font in RETIRED_FONTS if font in html]
    assert not found, f"{name} uses retired fonts: {found}"


@pytest.mark.parametrize("name", CASE_IDS)
def test_font_stacks_lead_with_geist(rendered: dict[str, str], name: str):
    """Arial is the fallback, never the first choice."""
    # Capture up to the `;` or the closing `"` of an inline style. Single quotes
    # have to stay inside the class, or the family names in the @font-face rules
    # (font-family: 'Geist';) capture as an empty string.
    stacks = re.findall(r"font-family:\s*([^;\"]+)", rendered[name])
    assert stacks, f"{name} declares no font-family at all"
    for stack in stacks:
        first = stack.split(",")[0].strip().strip("'\"")
        assert first in ("Geist", "Geist Mono"), f"{name} has a stack starting with {first!r}"


@pytest.mark.parametrize("name", CASE_IDS)
def test_assets_come_from_the_configured_host(rendered: dict[str, str], name: str):
    """raw.githubusercontent.com is branch-coupled and rate-limited, and Gmail's
    image proxy caches by URL — a change to main would mutate already-sent mail."""
    html = rendered[name]
    assert "raw.githubusercontent.com" not in html
    assert get_brand().logo_url in html


@pytest.mark.parametrize("name", CASE_IDS)
def test_client_compatibility_scaffold(rendered: dict[str, str], name: str):
    """The pieces that make these render outside Apple Mail."""
    html = rendered[name]
    # Outlook Windows ignores a width on <body>; the 600px table is what works.
    assert 'width="600"' in html, f"{name} is missing the 600px table"
    # Light is locked, so clients skip their auto-invert pass.
    assert '<meta name="color-scheme" content="light">' in html
    assert '<meta name="supported-color-schemes" content="light">' in html
    # Gmail strips @font-face, so inline stacks are what carry the typeface.
    assert "@font-face" in html


@pytest.mark.parametrize("name", CASE_IDS)
def test_imprint_is_present(rendered: dict[str, str], name: str):
    """Legally required on every outbound mail."""
    assert "Rhesis AI GmbH" in rendered[name]
    assert "HRB 39358 Potsdam" in rendered[name]


@pytest.mark.parametrize("name", CASE_IDS)
def test_no_unrendered_jinja(rendered: dict[str, str], name: str):
    html = rendered[name]
    for marker in ("{{", "}}", "{%"):
        assert marker not in html, f"{name} leaked an unrendered {marker} into the output"


@pytest.mark.parametrize("name", CASE_IDS)
def test_no_literal_none_or_undefined_leaks(rendered: dict[str, str], name: str):
    """A missing optional variable should drop its row, not print 'None'."""
    html = rendered[name]
    assert ">None<" not in html, f"{name} rendered a bare None"
    assert "Undefined" not in html
