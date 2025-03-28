# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Mite"
copyright = "2025, Sky UK - Identity performance engineers"
author = "Sky UK - Identity performance engineers"
release = "2.4.9"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.graphviz",
    "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = (
    "furo"  # customisation for furo here ->  https://pradyunsg.me/furo/customisation/
)

html_theme_options = {
    "announcement": "<em>Important</em> This is still a WIP!",
    # "github_user": "sky-uk",
    # "github_repo": "mite",
    # "github_banner": True,
    # "show_powered_by": False,
}

html_static_path = ["_static"]
html_theme_options = {
    "light_logo": "mite.png",
    "dark_logo": "mite.png",
}


intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
