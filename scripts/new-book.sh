#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <slug> \"<title>\"" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
slug="$1"
title="$2"

if [[ ! "$slug" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  echo \
    "error: slug must contain lowercase letters/numbers separated by single hyphens" \
    >&2
  exit 2
fi

if [[ -z "$title" || "$title" == *$'\n'* ]]; then
  echo "error: title must be a non-empty single line" >&2
  exit 2
fi

target="$repo_root/books/$slug"

if [[ -e "$target" ]]; then
  echo "error: refusing to overwrite existing path: $target" >&2
  exit 1
fi

"$PYTHON" "$repo_root/scripts/books.py" validate
cleanup() {
  if [[ -d "$target" ]]; then
    echo "error: creation failed; removing $target" >&2
    rm -rf "$target"
  fi
}

trap cleanup ERR

mkdir -p "$target/chapters/01-introduction"

cp \
  "$repo_root/common/templates/book.tex" \
  "$target/book.tex"

cp \
  "$repo_root/common/templates/metadata.tex" \
  "$target/metadata.tex"

cp \
  "$repo_root/common/templates/README.md" \
  "$target/README.md"

cp \
  "$repo_root/common/templates/chapter.tex" \
  "$target/chapters/01-introduction/index.tex"

cp \
  "$repo_root/common/templates/section.tex" \
  "$target/chapters/01-introduction/01-first-section.tex"

TITLE="$title" SLUG="$slug" perl -pi -e \
  's/__BOOK_TITLE__/$ENV{TITLE}/g; s/__BOOK_SLUG__/$ENV{SLUG}/g' \
  "$target/metadata.tex" \
  "$target/README.md"

"$PYTHON" "$repo_root/scripts/books.py" add "$slug" "$title"
trap - ERR

echo "Created books/$slug"
echo "Registered '$slug' in books.yml as draft"
echo "Site publication remains disabled; see docs/site-metadata.md to enable it"