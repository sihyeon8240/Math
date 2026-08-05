#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

"$repo_root/scripts/check-repository.sh"
mapfile -t books < <("$PYTHON" "$repo_root/scripts/books.py" list --for check)
if ((${#books[@]} == 0)); then
  echo "No books are enabled for check in books.yml; source checks passed."
  exit 0
fi

"$repo_root/scripts/build-all.sh" check

logs=()
for slug in "${books[@]}"; do
  log="$repo_root/build/$slug/book.log"
  if [[ ! -f "$log" ]]; then
    echo "error: checked book '$slug' is missing its expected build log: $log" >&2
    exit 1
  fi
  logs+=("$log")
done

check_log_args=()
if [[ "${CHECK_LOG_STRICT:-0}" == 1 ]]; then
  check_log_args+=(--strict)
fi
"$PYTHON" "$repo_root/scripts/check-log.py" "${check_log_args[@]}" "${logs[@]}"
