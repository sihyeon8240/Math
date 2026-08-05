#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <book-slug>" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
slug="$1"
logo="$repo_root/common/assets/logos/unist-logo.png"

cd "$repo_root"

[[ -f "$logo" ]] || {
  echo "error: authorized institutional logo is missing: $logo" >&2
  exit 1
}

if [[ -n "$(git status --porcelain)" ]]; then
  echo "error: repository must be clean before publishing" >&2
  git status --short >&2
  exit 1
fi

current_branch="$(git branch --show-current)"
if [[ "$current_branch" != "main" ]]; then
  echo "error: releases must be published from the main branch (current: ${current_branch:-detached HEAD})" >&2
  exit 1
fi

git fetch --no-tags origin main
head_commit="$(git rev-parse HEAD)"
remote_main_commit="$(git rev-parse origin/main)"
if [[ "$head_commit" != "$remote_main_commit" ]]; then
  echo "error: HEAD must exactly match origin/main" >&2
  echo "HEAD:        $head_commit" >&2
  echo "origin/main: $remote_main_commit" >&2
  exit 1
fi

"$PYTHON" scripts/books.py validate
"$PYTHON" scripts/books.py require "$slug" >/dev/null
version="$("$PYTHON" scripts/books.py version "$slug")"
tag="$slug-v$version"
./scripts/release-plan.sh "$tag" >/dev/null

release_dir="$(mktemp -d)"
trap 'rm -rf -- "$release_dir"' EXIT
./scripts/build-book.sh "$slug"
./scripts/package-book.sh "$slug" "$release_dir"
pdf="$release_dir/$tag.pdf"
(
  cd "$release_dir"
  sha256sum "$tag.pdf" > SHA256SUMS
)

if git rev-parse --verify --quiet "refs/tags/$tag" >/dev/null; then
  tag_commit="$(git rev-list -n 1 "$tag")"
  if [[ "$tag_commit" != "$(git rev-parse HEAD)" ]]; then
    echo "error: existing tag $tag does not point to HEAD" >&2
    exit 1
  fi
  if [[ "$(git cat-file -t "refs/tags/$tag")" != "tag" ]]; then
    echo "error: existing tag $tag is not annotated" >&2
    exit 1
  fi
else
  git tag -a "$tag" -m "Release $slug version $version"
fi

git push origin "$tag"

echo "==> Waiting for the release workflow for $tag"
run_id=""
for _ in {1..24}; do
  run_id="$(gh run list --workflow release.yml --branch "$tag" --event push --limit 1 --json databaseId --jq '.[0].databaseId // empty')"
  [[ -n "$run_id" ]] && break
  sleep 5
done
if [[ -z "$run_id" ]]; then
  echo "error: release workflow did not appear within 2 minutes for $tag" >&2
  exit 1
fi
if ! timeout 15m gh run watch "$run_id" --exit-status; then
  echo "error: release workflow $run_id failed or did not finish within 15 minutes" >&2
  exit 1
fi

gh release upload "$tag" "$pdf" "$release_dir/SHA256SUMS"
echo "==> Published $tag.pdf and SHA256SUMS to release $tag"
