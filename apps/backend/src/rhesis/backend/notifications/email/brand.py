"""Brand tokens for transactional email templates.

Single source of truth for the values the email templates render. Kept in
Python rather than a Jinja include so the same tokens are importable from
tests and from any future email code.

The values mirror the marketing site (`website/src/components/home/*.tsx`) —
**not** the `@theme` block in `website/src/styles/tailwind.css`, which still
holds the previous brand (`#50B9E0`, `#2AA1CE`) that the redesigned sections
no longer use. Semantic colors come from the product UI
(`apps/frontend/src/styles/theme.ts`), since these emails link into it.

Email constrains what can be expressed:

- Web fonts reach maybe half of recipients. `@font-face` works in Apple Mail,
  Outlook for Mac, and Thunderbird; Gmail (every client), Outlook Windows,
  Outlook.com, and Yahoo strip it. Hence every token that names a font names a
  full stack, and Sora never appears — its only job on the site is the
  wordmark, which is baked into `logo-lockup-v1.png` instead.
- `border-radius` is dropped by Outlook Windows, so cards carry a 1px border
  to stay defined there and buttons degrade to solid rectangles.
- `box-shadow` renders inconsistently and muddily in mail, so the site's card
  and button shadows are omitted rather than approximated.
"""

import logging
import re
from dataclasses import dataclass, replace
from typing import Optional

from markupsafe import Markup

from rhesis.backend.app.config.settings import get_smtp_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Colors:
    """Palette. Lowercase hex throughout so the regression test can match it."""

    # Surfaces
    canvas: str = "#f9fafa"  # page background (site: Home.tsx)
    surface: str = "#ffffff"  # cards
    # Recessed panels: fallback-link boxes, info callouts, secondary cards.
    # Neutral on purpose — a blue tint here clashes with the header wash's cyan
    # and reads as a different brand. The site keeps these greys and reserves
    # blue for type and CTAs.
    surface_subtle: str = "#f0f2f6"

    # Text — three levels, and that is the whole set. Anything that wants a
    # fourth is really asking for a different size or weight.
    heading: str = "#101011"  # headlines, subheads, table values
    body: str = "#2c2c2c"  # prose
    muted: str = "#6b7280"  # small print, table labels, the imprint

    # Lines
    border: str = "#e5e7eb"  # rules and table dividers
    # Card edges are far lighter than rules. On the site a card is defined by
    # its shadow and carries no border at all; this is only here so the card
    # does not dissolve into the canvas in Outlook, which drops box-shadow.
    card_edge: str = "#eceff3"

    # Brand
    blue: str = "#0080af"  # primary; also the product UI primary
    blue_dark: str = "#006d96"
    blue_light: str = "#009bd3"
    yellow: str = "#fdd803"
    orange: str = "#f97316"

    # Semantic, from apps/frontend/src/styles/theme.ts
    success: str = "#38ad87"
    success_tint: str = "#eef8f4"
    success_border: str = "#c3e6da"
    warning: str = "#f57c00"
    warning_tint: str = "#fff7ed"
    warning_border: str = "#fed7aa"
    error: str = "#de3355"
    error_tint: str = "#fdeff2"
    error_border: str = "#f6c9d3"

    # CTAs. The site's navbar CTA is a near-black pill
    # (linear-gradient(179.48deg, #101011, #424246)); flattened to its top stop
    # here because Outlook ignores gradients. Blue stays the accent colour for
    # headline tails and links rather than doubling as the button fill.
    button: str = "#101011"
    inverse: str = "#ffffff"  # text on a solid dark fill


@dataclass(frozen=True)
class Fonts:
    """Font stacks. The first family only resolves where @font-face survives.

    Wrapped in `Markup` because the environment autoescapes unconditionally,
    which would turn the quotes around multi-word family names into `&#39;`.
    These are developer-controlled constants, never user input, so marking them
    safe is sound — nothing else on `brand` needs it, since hex values, URLs and
    shadow values contain no escapable characters.
    """

    sans: str = Markup(
        "'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
    )
    mono: str = Markup("'Geist Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace")


@dataclass(frozen=True)
class Type:
    """The whole type ramp. Five steps — no template should introduce a sixth.

    18 does double duty: regular weight is a lede, bold is a section head. The
    distinction is weight, not size, which is what keeps the ramp short.
    """

    headline: int = 32  # one per email
    lede: int = 18  # intro line (400) and section heads (700)
    body: int = 16  # prose, buttons, table values
    small: int = 13  # small print, table labels, the imprint
    label: int = 11  # mono eyebrows and chips


@dataclass(frozen=True)
class Layout:
    """Geometry. Widths in px because email measures in px."""

    width: int = 600  # the canonical email content width
    radius_card: int = 24  # the site's card range is 20-30px
    radius_chip: int = 999
    radius_button: int = 999  # pill, matching the site's rounded-full CTAs
    gutter: int = 32

    # The site's card shadow. Honoured by Apple Mail, iOS, and Gmail; Outlook
    # drops it, which is what card_edge covers for.
    shadow_card: str = "0 4px 30px 0 rgba(45, 30, 133, 0.1)"

    # Display sizes of the raster assets. Both are rendered at 2x by
    # website/scripts/build-email-assets.mjs, which prints these numbers —
    # keep them in step with that script's output.
    logo_width: int = 232
    logo_height: int = 60
    # An organization's favicon, shown beside its product name in place of the lockup.
    org_logo_size: int = 40
    wash_height: int = 297
    # How far down the content table the wash starts, so its centre (half of
    # wash_height) lands on the CTA. Measured button centres in the auth emails:
    # 334-427px at 600px wide, 378-523px at 375px, because the copy reflows to
    # more lines on a phone. Hence two offsets — the mobile one is applied by a
    # media query in _base.html.jinja2. Longer emails (a stat tile ahead of the
    # button) push their button below the wash; one offset serves every
    # template, so it tracks the high-volume transactional ones.
    wash_offset: int = 200
    wash_offset_mobile: int = 240


_EMAIL_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


@dataclass(frozen=True)
class ImprintLine:
    """One line of the imprint, split around an email address so it can be a link."""

    text: str
    email: str = ""
    after: str = ""


def imprint_lines(imprint: Optional[str]) -> tuple[ImprintLine, ...]:
    """``EMAIL_IMPRINT`` as lines, each with its first email address picked out."""
    lines = []
    # A literal "\n" counts as a line break too: a shell or .env value without
    # quote processing keeps it as two characters.
    for line in (imprint or "").replace("\\n", "\n").splitlines():
        line = line.strip()
        if not line:
            continue
        match = _EMAIL_ADDRESS.search(line)
        if match:
            lines.append(ImprintLine(line[: match.start()], match.group(), line[match.end() :]))
        else:
            lines.append(ImprintLine(line))
    return tuple(lines)


#: Settings cannot change within a process, and tests start a fresh app lifespan
#: per test, so the warning is logged once.
_imprint_checked = False


def warn_if_imprint_missing() -> None:
    """Warn at startup when this deployment sends email without an imprint.

    Only the operator knows who legally sends the mail, so there is no default to
    fall back on. A warning rather than a failed boot: mail still works without it.
    """
    global _imprint_checked
    if _imprint_checked:
        return
    _imprint_checked = True
    settings = get_smtp_settings()
    if settings.host and not imprint_lines(settings.imprint):
        logger.warning(
            "Email is sent without an imprint because EMAIL_IMPRINT is unset; a notice "
            "shows in its place. In some "
            "countries, such as Germany, business email must name the sending company "
            "and its legal details. Set EMAIL_IMPRINT to yours, one line per entry."
        )


DEFAULT_PRODUCT_NAME = "Rhesis AI"
# Content-ID of the organization's favicon, attached to the message itself because
# the uploaded file is only served to signed-in users.
LOGO_CONTENT_ID = "organization-logo"


@dataclass(frozen=True)
class OrganizationBrand:
    """The branding an organization set, as email uses it. Every field is optional."""

    product_name: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    # PNG bytes of a raster favicon; an SVG one is left out, as on report PDFs.
    logo_png: Optional[bytes] = None


@dataclass(frozen=True)
class Brand:
    """Everything a template needs, exposed to Jinja as `brand`."""

    color: Colors
    font: Fonts
    type: Type
    layout: Layout
    asset_base_url: str
    product_name: str = DEFAULT_PRODUCT_NAME
    # Set when the organization has its own product name. The header shows that name
    # (and its favicon) instead of the Rhesis lockup and wash, and Rhesis-only copy
    # such as the invitation's "About" block is left out. The imprint stays: it names
    # whoever runs the deployment, which is still the sender.
    white_label: bool = False
    has_logo: bool = False
    # The deployment's EMAIL_IMPRINT. Empty shows a notice that it is not set.
    imprint: tuple[ImprintLine, ...] = ()

    @property
    def logo_cid(self) -> str:
        return LOGO_CONTENT_ID

    @property
    def logo_url(self) -> str:
        return f"{self.asset_base_url}/email/logo-lockup-v1.png"

    @property
    def wash_url(self) -> str:
        return f"{self.asset_base_url}/email/header-gradient-v1.jpg"

    @property
    def font_sans_url(self) -> str:
        return f"{self.asset_base_url}/fonts/Geist-VariableFont_wght.woff2"

    @property
    def font_mono_url(self) -> str:
        return f"{self.asset_base_url}/fonts/GeistMono-VariableFont_wght.woff2"


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _text_on(fill: str, light: str, dark: str) -> str:
    """Whichever of ``light`` and ``dark`` contrasts more with ``fill`` (WCAG ratio)."""
    fill_l = _relative_luminance(fill)

    def ratio(text: str) -> float:
        lighter, darker = sorted((fill_l, _relative_luminance(text)), reverse=True)
        return (lighter + 0.05) / (darker + 0.05)

    return light if ratio(light) >= ratio(dark) else dark


def _colors(organization: OrganizationBrand) -> Colors:
    colors = Colors()
    if organization.primary_color:
        accent = organization.primary_color.lower()
        colors = replace(colors, blue=accent, blue_dark=accent, blue_light=accent)
    if organization.secondary_color:
        button = organization.secondary_color.lower()
        colors = replace(
            colors, button=button, inverse=_text_on(button, colors.inverse, colors.heading)
        )
    return colors


def get_brand(organization: Optional[OrganizationBrand] = None) -> Brand:
    """Build the brand tokens, resolving the asset host from settings.

    With an organization's branding, its colours replace the accent and button
    colours and its product name replaces "Rhesis AI".
    """
    settings = get_smtp_settings()
    asset_base_url = settings.asset_base_url.rstrip("/")
    imprint = imprint_lines(settings.imprint)
    if organization is None:
        return Brand(
            color=Colors(),
            font=Fonts(),
            type=Type(),
            layout=Layout(),
            asset_base_url=asset_base_url,
            imprint=imprint,
        )
    return Brand(
        color=_colors(organization),
        font=Fonts(),
        type=Type(),
        layout=Layout(),
        asset_base_url=asset_base_url,
        product_name=organization.product_name or DEFAULT_PRODUCT_NAME,
        white_label=bool(organization.product_name),
        has_logo=bool(organization.product_name and organization.logo_png),
        imprint=imprint,
    )
