"""Jinja2 environment for MCP prompt templates."""

from pathlib import Path

import jinja2

# templates.py lives at app/services/tool/mcp/; the templates dir is app/templates/.
# parents[3] == app/ (mcp -> tool -> services -> app).
TEMPLATE_DIR = Path(__file__).parents[3] / "templates"
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=jinja2.select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)
