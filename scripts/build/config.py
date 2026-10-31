"""Paths and names for building the config in src/ into dist/."""

SRC_FOLDER = "src"
DIST_FOLDER = "dist"
PARTS_SUFFIX = ".d"
JINJA_HEADER = "## template: jinja"
JINJA_PART_TYPE = "jinja2"
CLOUD_CONFIG_PART_TYPE = "cloud-config"
MAKE_MIME_COMMAND = ("cloud-init", "devel", "make-mime")
README_FILE = "README.md"
META_DATA_EXAMPLE_MARKER = "<!-- meta-data example -->"
"""The comment in the README straight before the yaml code block that holds the meta-data example. The e2e job's
seed-cloud-init.ps1 finds the example by the same comment.
"""
