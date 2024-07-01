project = "Motile Plugin"
copyright = "2024, Howard Hughes Medical Institute"
author = "Caroline Malin-Mayor"

extensions = [
    "sphinx.ext.autodoc",
    "myst_parser",
    "autoapi.extension",
    "sphinx_rtd_theme",
    "sphinxcontrib.video",
]
autoapi_dirs = ["../../src/motile_plugin"]

exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
# html_static_path = ['_static']
