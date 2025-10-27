# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
import re
from datetime import datetime

sys.path.insert(0, os.path.abspath('../../../sdk/src'))
sys.path.insert(0, os.path.abspath('_ext'))

# Convert CHANGELOG.md to changelog.rst
def convert_changelog():
    """Convert the CHANGELOG.md file to RST format and save as changelog.rst and individual version files"""
    changelog_md_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../sdk/CHANGELOG.md'))
    changelog_rst_path = os.path.join(os.path.dirname(__file__), 'changelog.rst')
    changelog_dir = os.path.join(os.path.dirname(__file__), 'changelog')

    # Create changelog directory if it doesn't exist
    os.makedirs(changelog_dir, exist_ok=True)

    if not os.path.exists(changelog_md_path):
        print(f"Warning: CHANGELOG.md not found at {changelog_md_path}")
        return

    with open(changelog_md_path, 'r') as md_file:
        md_content = md_file.read()

    # Replace Markdown links with RST links
    md_content = re.sub(r'\[([^]]+)\]\(([^)]+)\)', r'`\1 <\2>`_', md_content)

    # Extract versions
    version_blocks = []
    current_version = None
    current_content = ""
    processed_versions = set()  # Track processed versions to avoid duplicates

    lines = md_content.split('\n')
    for i, line in enumerate(lines):
        if i == 0:  # Skip the title
            continue

        # New version block starts
        if line.startswith('## ['):
            # Save previous version block if exists
            if current_version and current_version not in processed_versions:
                version_blocks.append((current_version, current_content))
                processed_versions.add(current_version)

            # Extract version number - skip [Unreleased] and other non-version headers
            version_match = re.search(r'## \[(\d+\.\d+\.\d+)\](.+)', line)
            if version_match:
                current_version = version_match.group(1)
                # Skip if we've already processed this version
                if current_version in processed_versions:
                    current_version = None
                    current_content = ""
                    continue

                date_part = version_match.group(2).strip()
                current_content = f"Version {current_version} {date_part}\n"
                current_content += f"{'=' * len(current_content)}\n\n"
            else:
                # Skip non-version headers like [Unreleased]
                current_version = None
                current_content = ""

        # Add line to current version block
        elif current_version:
            # Format subheaders
            if line.startswith('### '):
                subheader = line[4:]
                current_content += f"{subheader}\n"
                current_content += f"{'-' * len(subheader)}\n\n"
            # Skip link references at the end
            elif line.startswith('[') and ']' in line and ':' in line:
                continue
            # Regular content
            else:
                current_content += f"{line}\n"

    # Add the last version block
    if current_version and current_content and current_version not in processed_versions:
        version_blocks.append((current_version, current_content))
        processed_versions.add(current_version)

    # Create individual version files
    for version, content in version_blocks:
        version_file = os.path.join(changelog_dir, f"v{version}.rst")
        with open(version_file, 'w') as f:
            f.write(content)

    # Create main changelog.rst with toctree
    main_content = "Changelog\n=========\n\n"
    main_content += "All notable changes to the Rhesis SDK.\n\n"
    main_content += ".. toctree::\n"
    main_content += "   :maxdepth: 1\n\n"

    # Sort versions using semantic versioning principles (newer versions first)
    sorted_versions = sorted(version_blocks, key=lambda x: list(map(int, x[0].split('.'))), reverse=True)

    # Add version files to toctree in sorted order (newest first)
    for version, _ in sorted_versions:
        main_content += f"   changelog/v{version}\n"

    with open(changelog_rst_path, 'w') as f:
        f.write(main_content)

    print(f"Successfully created changelog at {changelog_rst_path} with {len(version_blocks)} version subpages")

# Extract latest version from CHANGELOG.md
def get_latest_version():
    changelog_md_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../sdk/CHANGELOG.md'))
    if os.path.exists(changelog_md_path):
        with open(changelog_md_path, 'r') as f:
            content = f.read()
            # Look for version number in format ## [x.y.z]
            version_match = re.search(r'## \[(\d+\.\d+\.\d+)\]', content)
            if version_match:
                return version_match.group(1)
    return '0.1.0'  # Default if changelog not found or no version detected

# Run the changelog conversion
convert_changelog()

project = 'rhesis-sdk'
copyright = f'{datetime.now().year}, Rhesis AI'
author = 'Rhesis AI'
release = get_latest_version()

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Add any Sphinx extension module names here, as strings
extensions = [
    'sphinx.ext.autodoc',  # Required for automodule directives
    'sphinx.ext.napoleon',
    'sphinx_autodoc_typehints',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'myst_parser', # TODO: implement link from README.md to index.rst
    'resolve_types',  # Our custom extension to fix ambiguous type references
    'fix_entity_docs',  # Custom extension to fix Client references in BaseEntity
]

# Mock imports for modules that might not be available at build time are no longer needed
# since we removed references to these modules

templates_path = ['_templates']
exclude_patterns = []

# Add this to your existing conf.py
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
    'special-members': '__init__',
    'member-order': 'bysource',
    'private-members': False,
    'imported-members': True,
}

# This will prevent duplicate warnings
suppress_warnings = [
    'autodoc.duplicate_object_description',
    'autodoc.import_object',
    'docutils.nodes.title_reference',
    'docutils',  # Suppress all docutils warnings
]

# Disable docutils warnings about title underlines for Sphinx
nitpicky = False
nitpick_ignore = [
    ('py:.*', '.*'),  # Ignore all Python references
    ('.*', 'Title underline too short'),  # Ignore title underline warnings
]

# Set up a warning filter to ignore docutils warnings
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='docutils')

# Configure intersphinx mapping to Python standard library and other packages
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'jinja2': ('https://jinja.palletsprojects.com/en/3.0.x/', None),
}

# To avoid duplicate object warnings
add_module_names = False  # Don't prepend module names to objects

# Handle cross-reference issues by preferring certain modules
primary_domain = 'py'
default_role = 'py:obj'

# Create explicit type overrides to handle ambiguous types
typehints_defaults = 'comma'
typehints_document_rtype = True
always_document_param_types = True

# Add typing module to autodoc_type_aliases
autodoc_type_aliases = {
    'Any': 'typing.Any',
    'Path': 'pathlib.Path',
    'Template': 'jinja2.environment.Template',
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Use custom Rhesis pygments style for syntax highlighting
pygments_style = 'rhesis_pygments_style.RhesisStyle'

# Custom CSS files
html_css_files = [
    'rhesis-theme.css',
]

# Theme options for RTD theme
html_theme_options = {
    'analytics_id': '',
    'analytics_anonymize_ip': False,
    'logo_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': True,
    'vcs_pageview_mode': '',
    'style_nav_header_background': '#2AA1CE',  # Rhesis CTA Blue
    'collapse_navigation': False,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}

# Custom HTML context
html_context = {
    'display_github': True,
    'github_user': 'rhesis-ai',
    'github_repo': 'rhesis',
    'github_version': 'main',
    'conf_py_path': '/docs/sphinx/source/',
}

# HTML title and short title
html_title = "Rhesis SDK Documentation"
html_short_title = "Rhesis SDK"

# Favicon
html_favicon = None  # Add favicon path if you have one

# Additional HTML head content
html_head = '''
<meta name="description" content="Rhesis SDK - Gen AI Testing. Collaborative. Adaptive. Python SDK for comprehensive Gen AI application testing.">
<meta name="keywords" content="Gen AI, AI testing, Python SDK, collaborative testing, AI validation">
<meta name="author" content="Rhesis AI">
<meta property="og:title" content="Rhesis SDK Documentation">
<meta property="og:description" content="From 'I hope this works' to 'I know this works.' Python SDK for comprehensive Gen AI testing.">
<meta property="og:type" content="website">
<meta property="og:image" content="https://cdn.prod.website-files.com/68c3e3b148a4fd9bcf76eb6a/68c95daec03defb40e24fca4_Rhesis%20AI_Logo_RGB_Website%20logo-p-500.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Rhesis SDK Documentation">
<meta name="twitter:description" content="Gen AI Testing. Collaborative. Adaptive. Python SDK for comprehensive testing.">
'''
