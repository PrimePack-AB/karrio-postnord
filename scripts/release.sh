#!/usr/bin/env bash
# Usage: scripts/release.sh <version>
# Sets the [project] version in pyproject.toml, commits it, and creates the annotated tag v<version>.
# Nothing is pushed; the push command is printed at the end.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <version>   (CalVer YYYY.M.N, e.g. 2026.10.1)" >&2
  exit 2
fi

version=$1
tag="v$version"

if [[ ! "$version" =~ ^[0-9]{4}\.(1[0-2]|[1-9])\.[0-9]+$ ]]; then
  echo "version $version is not CalVer YYYY.M.N" >&2
  exit 1
fi

cd "$(git rev-parse --show-toplevel)"

branch=$(git symbolic-ref --quiet --short HEAD || true)
if [[ "$branch" != "main" ]]; then
  echo "releases are cut from main; current branch is ${branch:-a detached HEAD}" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "the working tree is not clean" >&2
  exit 1
fi

if git rev-parse --quiet --verify "refs/tags/$tag" >/dev/null; then
  echo "tag $tag already exists" >&2
  exit 1
fi

python3 - "$version" <<'PY'
import re
import sys
import tomllib
from pathlib import Path

path = Path("pyproject.toml")
text = path.read_text()
pattern = re.compile(r'(?ms)^(\[project\]\n.*?^version = )"[^"]*"')
updated, count = pattern.subn(rf'\g<1>"{sys.argv[1]}"', text, count=1)
if count != 1:
    sys.exit("could not find the [project] version in pyproject.toml")
if tomllib.loads(updated)["project"]["version"] != sys.argv[1]:
    sys.exit("pyproject.toml did not parse back to the new version")
path.write_text(updated)
PY

scripts/check-release-tag.sh "$tag"

git commit --quiet -m "chore(release): $version" -- pyproject.toml
git tag -a "$tag" -m "$tag"

echo "Created commit $(git rev-parse --short HEAD) and tag $tag. To publish:"
echo "  git push --atomic origin main $tag"
