"""Paths and names for building the config in src/ into dist/."""

SRC_FOLDER = "src"
DIST_FOLDER = "dist"
FRAGMENTS_FOLDER = "fragments"
"""The shared fragments, in src/. Any distro's manifest.json can list them."""
DISTROS_FOLDER = "distros"
"""One folder per distro, in src/, with its manifest.json and the fragments only it uses."""
SRC_FOLDERS = (FRAGMENTS_FOLDER, DISTROS_FOLDER)
MANIFEST_FILE = "manifest.json"
MANIFEST_SCHEMA = "schemas/distro-manifest.schema.json"
FRAGMENT_SUFFIX = ".user-data"
USER_DATA_SUFFIX = ".user-data"
"""dist/<distro>.user-data, the name the WSL datasource looks for on an instance named after the distro."""
JINJA_HEADER = "## template: jinja"
JINJA_PART_TYPE = "jinja2"
CLOUD_CONFIG_PART_TYPE = "cloud-config"
MAKE_MIME_COMMAND = ("cloud-init", "devel", "make-mime")
README_FILE = "README.md"
META_DATA_EXAMPLE_MARKER = "<!-- meta-data example -->"
"""The comment in the README straight before the yaml code block that holds the meta-data example. The e2e job's
seed-cloud-init.ps1 finds the example by the same comment.
"""
META_DATA_FILLED_KEYS = ("username", "git_name", "git_email")
"""The keys the example must leave empty, on a line of their own, because seed-cloud-init.ps1 fills them in."""
