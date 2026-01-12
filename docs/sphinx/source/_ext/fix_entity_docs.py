"""
Custom Sphinx extension to fix Client references in BaseEntity.
"""
from sphinx.util import logging

logger = logging.getLogger(__name__)

def setup(app):
    """
    Set up the extension in Sphinx.
    """
    app.connect('autodoc-process-docstring', fix_client_ref)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }

def fix_client_ref(app, what, name, obj, options, lines):
    """
    Fix Client references in BaseEntity docstring.
    """
    if 'BaseEntity' in name:
        for i, line in enumerate(lines):
            # Replace Client with fully qualified rhesis.client.Client
            if 'client' in line.lower() and 'Client' in line:
                lines[i] = line.replace('Client', ':class:`rhesis.client.Client`')
                logger.info(f"Fixed Client reference in {name}")
