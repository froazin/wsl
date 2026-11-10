#!/bin/sh
# Builds one distro's user-data from its manifest, as docs/build.md describes:
#
#   scripts/user-data.sh src/manifests/<distro>.json dist/<distro>.user-data
#
# Checks the file's name, then the manifest with scripts/manifest.jq, then that its fragments exist, and stops at the
# first check that fails. Then joins the fragments, in order, into one MIME multipart file with cloud-init devel
# make-mime. Run it from the repository root. It writes nothing when a check fails.
set -eu

fail()
{
    printf '%s\n' "$@" >&2
    exit 1
}

[ $# -eq 2 ] || fail "Usage: $0 <manifest> <output>"
manifest=$1
out=$2
fragments_dir=src/fragments

for tool in jq cloud-init; do
    command -v "$tool" > /dev/null 2>&1 || fail "The build needs $tool, which isn't installed. CONTRIBUTING.md says how to set up."
done

# The file's name is the WSL distribution's name, which the datasource matches the user-data by.
distro=$(basename "$manifest" .json)
case $distro in
    [A-Za-z0-9]*) ;;
    *) fail "$manifest: the file's name must start with a letter or digit, such as Ubuntu-26.04.json." ;;
esac
case $distro in
    *[!A-Za-z0-9._-]*) fail "$manifest: the file's name must hold only letters, digits, ., _ and -, such as Ubuntu-26.04.json." ;;
esac

errors=$(jq -r -s -f scripts/manifest.jq "$manifest") || fail "$manifest: jq couldn't read it as JSON. See jq's error above."
[ -z "$errors" ] || fail "$manifest: it doesn't match the manifest schema:" "$errors"

# Each part is named after its fragment's file, so make-mime runs in the fragments' folder. A fragment that starts with
# the Jinja header is a jinja2 part, and any other a cloud-config part. manifest.jq has checked every name has no spaces.
set --
missing=
for fragment in $(jq -r '.fragments[]' "$manifest"); do
    file=$fragment.user-data
    if [ ! -f "$fragments_dir/$file" ]; then
        missing="$missing
$fragments_dir/$file"
        continue
    fi
    first=
    IFS= read -r first < "$fragments_dir/$file" || true
    if [ "$first" = "## template: jinja" ]; then
        set -- "$@" --attach "$file:jinja2"
    else
        set -- "$@" --attach "$file:cloud-config"
    fi
done
[ -z "$missing" ] || fail "$manifest: it lists fragments that don't exist:$missing"

mkdir -p "$(dirname "$out")"
tmp=$out.tmp
trap 'rm -f "$tmp"' EXIT
(cd "$fragments_dir" && cloud-init devel make-mime "$@") > "$tmp"
mv "$tmp" "$out"
