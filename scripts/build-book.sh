#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 <book-slug>" >&2;
    exit 2;
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
slug="$1";
book_dir="$repo_root/books/$slug";
entry="$book_dir/book.tex"

"$PYTHON" "$repo_root/scripts/books.py" require "$slug" >/dev/null

if [[ ! -f "$entry" ]]; then
    echo "error: registered book '$slug' is missing its entry point: $entry" >&2;
    exit 2;
fi

out_dir="$repo_root/build/$slug";
mkdir -p "$out_dir"

while IFS= read -r source_dir; do
  [[ "$source_dir" == "$book_dir" ]] && continue
  relative="${source_dir#"$book_dir"/}"
  mkdir -p "$out_dir/$relative"
done < <(find "$book_dir" -mindepth 1 -type d -print)

export TEXINPUTS="$repo_root/common/styles//:${TEXINPUTS:-}"
echo "==> Building $slug"
cd "$book_dir"

latexmk -r "$repo_root/latexmkrc" -lualatex -outdir="$out_dir" book.tex
echo "==> Built $out_dir/book.pdf"
