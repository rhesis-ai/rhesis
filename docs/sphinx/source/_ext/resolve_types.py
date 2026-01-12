"""
Custom Sphinx extension to handle ambiguous type references.
"""

from sphinx.util import logging

logger = logging.getLogger(__name__)

def setup(app):
    """
    Set up the extension in Sphinx.
    """
    app.connect('autodoc-process-docstring', process_docstring)
    app.connect('build-finished', report_stats)

    app.fixed_refs = 0
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }

def process_docstring(app, what, name, obj, options, lines):
    """
    Process each docstring, fixing ambiguous type references.
    """
    for i, line in enumerate(lines):
        # Fix typing.Any references
        if ':type' in line or ':param' in line or ':return' in line:
            lines[i] = line.replace(' Any', ' typing.Any')
            if line != lines[i]:
                app.fixed_refs += 1

        # Fix other standard lib references
        if 'Path' in line:
            lines[i] = line.replace(' Path', ' pathlib.Path')
            if line != lines[i]:
                app.fixed_refs += 1

        if 'Template' in line:
            lines[i] = line.replace(' Template', ' jinja2.Template')
            if line != lines[i]:
                app.fixed_refs += 1

def report_stats(app, exception):
    """
    Report how many references were fixed.
    """
    if app.fixed_refs > 0:
        logger.info(f"Fixed {app.fixed_refs} ambiguous type references")
