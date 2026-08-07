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

from dataclasses import dataclass

from markupsafe import Markup

from rhesis.backend.app.config.settings import get_smtp_settings


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


@dataclass(frozen=True)
class Brand:
    """Everything a template needs, exposed to Jinja as `brand`."""

    color: Colors
    font: Fonts
    type: Type
    layout: Layout
    asset_base_url: str

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


def get_brand() -> Brand:
    """Build the brand tokens, resolving the asset host from settings."""
    return Brand(
        color=Colors(),
        font=Fonts(),
        type=Type(),
        layout=Layout(),
        asset_base_url=get_smtp_settings().asset_base_url.rstrip("/"),
    )
