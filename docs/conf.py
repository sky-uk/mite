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
#
# ARCHITECTURE-HA-ROADMAP.md is an internal planning document, not user
# documentation. Enabling myst_parser above makes every .md file under docs/ a
# Sphinx source, so without this exclusion it would be built and would emit a
# fatal "document isn't included in any toctree" warning under `sphinx-build -W`.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'ARCHITECTURE-HA-ROADMAP.md']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

html_theme_options = {
    "github_user": "sky-uk",
    "github_repo": "mite",
    "github_banner": True,
    "show_powered_by": False,
}


intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}
