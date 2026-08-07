#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
PYTHON="${PYTHON:-python3}"
if ! command -v rg >/dev/null 2>&1; then
  echo "error: required command 'rg' (ripgrep) was not found in PATH" >&2
  exit 127
fi
"$PYTHON" scripts/books.py validate
"$PYTHON" scripts/check-architecture.py
"$PYTHON" scripts/generate-readme-books.py --check
"$PYTHON" scripts/generate-site-data.py --check

required=(
  Makefile
  README.md
  CONTRIBUTING.md
  common/styles/textbook.sty
  common/styles/textbook-core.sty
  common/styles/textbook-math.sty
  common/styles/textbook-theorems.sty
  common/styles/textbook-draft.sty
  scripts/build-book.sh
)
for path in "${required[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "error: required repository path is missing: $path" >&2
    exit 1
  fi
done

mapfile -t python_files < <(find scripts -type f -name '*.py' -print | sort)
if ((${#python_files[@]})); then
  "$PYTHON" -m py_compile "${python_files[@]}"
fi
mapfile -t tex_files < <(
  find books common/templates -type f -name '*.tex' -print 2>/dev/null | sort
)
"$PYTHON" scripts/check-labels.py "${tex_files[@]}"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  generated_directories='(^|/)(__pycache__|vscode-build|build|dist'
  generated_directories+='|unist-logo.png|context.tex|tree.txt)/'
  generated_extensions='\.(aux|bbl|bcf|blg|fdb_latexmk|fls|idx'
  generated_extensions+='|ilg|ind|lof|log|lot|out|pdf|pyc'
  generated_extensions+='|run\.xml|synctex\.gz|toc|xdv)$'
  generated_pattern="$generated_directories|$generated_extensions"

  tracked_generated="$(git ls-files | grep -E "$generated_pattern" || true)"
  if [[ -n "$tracked_generated" ]]; then
    echo "error: generated files are tracked:" >&2
    printf '%s\n' "$tracked_generated" >&2
    exit 1
  fi
else
  echo "warning: Git metadata unavailable; skipped tracked generated-file check" >&2
fi
marker_pattern='TODO|VERIFY|SOURCECHECK|\\(todo|verify|sourcecheck)\{'
set +e
marker_output="$(rg -n "$marker_pattern" books --glob '*.tex')"
marker_status=$?
set -e
if ((marker_status > 1)); then
  echo "error: ripgrep failed while checking unfinished-writing markers" >&2
  exit "$marker_status"
fi
if [[ -n "$marker_output" ]]; then
  marker_count="$(printf '%s\n' "$marker_output" | wc -l | tr -d ' ')"
  echo "warning: found $marker_count unfinished-writing marker(s);" \
    "these are reported but do not fail CI" >&2
  printf '%s\n' "$marker_output" >&2
fi
echo "Repository source checks passed."
