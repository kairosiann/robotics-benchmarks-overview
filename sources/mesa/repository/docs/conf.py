"""Sphinx configuration for the MESA documentation site."""

from datetime import datetime

# -- Project information -----------------------------------------------------
project = "MESA"
author = "Albert Wilcox"
copyright = f"{datetime.now().year}, {author}"
release = "1.0.0"
html_title = f"{project} Documentation"


# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_copybutton",
]

source_suffix = {
    ".md": "markdown",
}
root_doc = "index"
master_doc = "index"

# Generate anchors for headings (h1–h3) so intra-doc `page.md#heading-slug`
# links resolve.
myst_heading_anchors = 3

templates_path = ["_templates"]
exclude_patterns = ["_build", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_book_theme"
html_logo = "images/logo.png"
html_favicon = "images/favicon.png"
html_static_path = ["_static"]
# Copy raw rollout videos into _build/html/videos so the policy viewer URLs resolve.
html_extra_path = ["videos"]
html_context = {
    "default_mode": "light",
}
html_theme_options = {
    "logo": {
        "text": "",
    },
    "show_toc_level": 1,
    "show_navbar_depth": 2,
    "collapse_navigation": False,
    "use_download_button": False,
    "use_fullscreen_button": False,
}

# Make shell snippets easier to copy by stripping prompts.
copybutton_prompt_text = r"^\$ "
copybutton_prompt_is_regexp = True
