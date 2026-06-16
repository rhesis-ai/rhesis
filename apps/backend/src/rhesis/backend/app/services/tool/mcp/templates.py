"""Jinja2 environment for MCP prompt templates."""

from pathlib import Path

import jinja2

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=jinja2.select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)
