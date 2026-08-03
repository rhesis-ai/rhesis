#!/usr/bin/env python3
"""Render every email template with sample data so they can be eyeballed.

Writes one HTML file per template plus an index that shows each at 600px and
375px side by side. Nothing is sent — this only exercises the Jinja layer.

Run from apps/backend:

    uv run python scripts/preview_emails.py
    open /tmp/rhesis-email-preview/index.html

Pass --out to write somewhere else. Note this renders with whatever
EMAIL_ASSET_BASE_URL resolves to, so the logo, header wash, and web fonts only
appear if that host is reachable and already has the assets deployed.
"""

import argparse
import sys
from pathlib import Path

# The fixtures live with the tests so the previews and the brand assertions in
# tests/notifications/test_email_brand.py can never drift apart.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from rhesis.backend.notifications.email.template_service import (  # noqa: E402
    EmailTemplate,
    TemplateService,
)
from tests.notifications.email_fixtures import FIXTURES, VARIANTS  # noqa: E402

INDEX_HEAD = """<!DOCTYPE html>
<meta charset="utf-8">
<title>Rhesis email preview</title>
<style>
  body { margin: 0; padding: 32px; background: #1c1c1e; color: #f2f2f7;
         font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .meta { color: #8e8e93; margin-bottom: 32px; }
  section { margin-bottom: 48px; }
  h2 { font-size: 15px; font-weight: 600; margin: 0 0 12px; }
  h2 a { color: #64d2ff; text-decoration: none; font-weight: 400; font-size: 13px;
         margin-left: 8px; }
  .frames { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }
  iframe { border: 0; background: #fff; border-radius: 8px; }
</style>
<h1>Rhesis transactional emails</h1>
<div class="meta">Desktop 600px and mobile 375px. Fonts and images resolve only if
the asset host is live.</div>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/tmp/rhesis-email-preview", type=Path)
    args = parser.parse_args()

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    service = TemplateService()
    cases: list[tuple[str, EmailTemplate, dict]] = [
        (template.value.removesuffix(".html.jinja2"), template, variables)
        for template, variables in FIXTURES.items()
    ]
    cases.extend(VARIANTS)
    cases.sort(key=lambda case: case[0])

    index = [INDEX_HEAD]
    for name, template, variables in cases:
        html = service.render_template(template, variables)
        (out_dir / f"{name}.html").write_text(html, encoding="utf-8")
        index.append(
            f'<section><h2>{name}<a href="{name}.html" target="_blank">open</a></h2>'
            f'<div class="frames">'
            f'<iframe src="{name}.html" width="620" height="900"></iframe>'
            f'<iframe src="{name}.html" width="375" height="900"></iframe>'
            f"</div></section>"
        )
        print(f"  {name}  ({len(html):,} bytes)")

    (out_dir / "index.html").write_text("\n".join(index), encoding="utf-8")
    print(f"\n{len(cases)} previews -> {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
