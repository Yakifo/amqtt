import os
import sys
import datetime

sys.path.insert(0, os.path.abspath(".."))

project = "aMQTT"
author = "Your Name"
copyright = f"{datetime.date.today().year}, {author}"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns = []

html_theme = "furo"
html_static_path = ["_static"]
