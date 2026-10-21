# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = 'mite'
copyright = '2019, Sky UK - Identity performance engineers'
author = 'Sky UK - Identity performance engineers'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ["sphinx.ext.graphviz", "sphinx.ext.intersphinx", "myst_parser"]

# Generate anchors for Markdown headings up to level 3, so in-page links like
# [Layers](#layers) resolve. Without this, MyST emits an unresolved-reference
# warning, which is fatal under `sphinx-build -W`.
myst_heading_anchors = 3

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'furo'

# Set explicitly because no `release` is configured: Sphinx's default title is
# "{project} {release} documentation", which would render with a doubled space
# where the version should be. Furo shows this string in the sidebar brand and
# the mobile header, so the gap is visible.
html_title = 'mite documentation'

# Holds the logo referenced by light_logo/dark_logo below.
html_static_path = ['_static']

# Font Awesome, loaded from a CDN. The GitHub glyphs in the announcement
# banner and the footer icon below are styled purely by these classes, so
# without this stylesheet they render as empty boxes. Note this is a
# view-time dependency on a third party: sphinx-build cannot verify it, and
# a reader offline or behind a strict CSP will not see the icons.
html_css_files = [
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/fontawesome.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/solid.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/brands.min.css",
]

html_theme_options = {
    "announcement": (
        "<div>Follow and Fork me on GitHub! "
        "<a href='https://github.com/sky-uk/mite'>"
        "<i class='fa-brands fa-solid fa-github'></i></a></div>"
    ),
    "light_logo": "mite.png",
    "dark_logo": "mite.png",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/sky-uk/mite",
            "html": "",
            "class": "fa-brands fa-solid fa-github fa-2x",
        },
    ],
}


intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}
