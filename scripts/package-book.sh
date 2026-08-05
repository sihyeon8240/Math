#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <book-slug> <output-directory>" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
slug="$1"
output_dir="$2"

"$PYTHON" "$repo_root/scripts/books.py" require "$slug" >/dev/null
version="$("$PYTHON" "$repo_root/scripts/books.py" version "$slug")"
source_pdf="$repo_root/build/$slug/book.pdf"
log="$repo_root/build/$slug/book.log"
target="$output_dir/$slug-v$version.pdf"

[[ -f "$source_pdf" ]] || { echo "error: expected PDF is missing: $source_pdf" >&2; exit 1; }
[[ -f "$log" ]] || { echo "error: expected log is missing: $log" >&2; exit 1; }
if [[ -e "$target" ]]; then
  echo "error: refusing to overwrite existing release artifact: $target" >&2
  exit 1
fi

"$PYTHON" "$repo_root/scripts/check-log.py" --strict "$log"
mkdir -p "$output_dir"
cp "$source_pdf" "$target"
echo "==> Created $target"
