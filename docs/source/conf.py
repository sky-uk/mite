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


html_static_path = ["_static"]

html_css_files = [
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/fontawesome.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/solid.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/brands.min.css",
]

html_theme_options = {
    "announcement": "<div>Follow and Fork me on GitHub! <a href='https://github.com/sky-uk/mite'><i class='fa-brands fa-solid fa-github'></i></a>",
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


intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
