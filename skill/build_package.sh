#!/bin/bash
# Build the upload zip from the source package in this repository.
#
# The zip is the artifact that gets uploaded, so it must be generated from the
# source every time. A hand-synced copy drifted once already: the staged zip
# was still version 1.1.0, with no AI disclosure and the old token budget,
# while the source had moved on.
#
# Usage:
#   ./skill/build_package.sh                 # writes skill/podcast-brain-pro-skill.zip
#   ./skill/build_package.sh /path/to/out.zip
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_NAME="podcast-brain-pro"
SOURCE_DIR="$REPO_ROOT/skill/$PACKAGE_NAME"
OUTPUT="${1:-$REPO_ROOT/skill/$PACKAGE_NAME-skill.zip}"

if [ ! -f "$SOURCE_DIR/SKILL.md" ]; then
  echo "error: no SKILL.md in $SOURCE_DIR" >&2
  exit 1
fi

# Build artifacts that must never ship in the package. They appear whenever the
# validator is imported locally, so the build excludes them rather than
# refusing: the archive is guaranteed clean either way, and a normal test run
# does not block the build.
EXCLUDES=(--exclude='.DS_Store' --exclude='__pycache__' --exclude='*.pyc')

VERSION="$(sed -n 's/^version:[[:space:]]*//p' "$SOURCE_DIR/SKILL.md" | head -1)"
if [ -z "$VERSION" ]; then
  echo "error: no version in the SKILL.md frontmatter" >&2
  exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# Copy so the zip holds exactly the package and nothing else.
mkdir -p "$STAGE/$PACKAGE_NAME"
tar -C "$SOURCE_DIR" "${EXCLUDES[@]}" -cf - . | tar -C "$STAGE/$PACKAGE_NAME" -xf -

rm -f "$OUTPUT"
(cd "$STAGE" && zip -r -q "$OUTPUT" "$PACKAGE_NAME")
(cd "$STAGE" && zip -T "$OUTPUT")

echo "built $OUTPUT"
echo "  version: $VERSION"
echo "  files:"
unzip -l "$OUTPUT" | awk 'NR > 3 && $0 !~ /^-/ && $4 != "" { print "    " $4 }'
