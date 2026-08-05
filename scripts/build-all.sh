#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 ]]; then
  echo "usage: $0 [build|check]" >&2
  exit 2
fi

purpose="${1:-build}"
case "$purpose" in
  build|check) ;;
  *) echo "error: unsupported build purpose '$purpose'; expected build or check" >&2; exit 2 ;;
esac

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

if [[ -n "${BOOK_BUILD_JOBS+x}" ]]; then
  jobs="$BOOK_BUILD_JOBS"
else
  cpu_count=""
  if command -v getconf >/dev/null 2>&1; then
    cpu_count="$(getconf _NPROCESSORS_ONLN 2>/dev/null || true)"
  fi
  if [[ ! "$cpu_count" =~ ^[1-9][0-9]*$ ]] && command -v sysctl >/dev/null 2>&1; then
    cpu_count="$(sysctl -n hw.ncpu 2>/dev/null || true)"
  fi
  [[ "$cpu_count" =~ ^[1-9][0-9]*$ ]] || cpu_count=2
  if ((cpu_count > 4)); then jobs=4; else jobs="$cpu_count"; fi
fi

if [[ ! "$jobs" =~ ^[1-9][0-9]*$ ]]; then
  echo "error: BOOK_BUILD_JOBS must be a positive integer (for example, BOOK_BUILD_JOBS=2)" >&2
  exit 2
fi

"$PYTHON" "$repo_root/scripts/books.py" validate
target_output="$($PYTHON "$repo_root/scripts/books.py" list --for "$purpose")"
books=()
while IFS= read -r slug; do
  [[ -n "$slug" ]] && books+=("$slug")
done <<< "$target_output"

if ((${#books[@]} == 0)); then
  echo "No books are enabled for $purpose in books.yml."
  exit 0
fi

log_dir="$(mktemp -d "${TMPDIR:-/tmp}/book-build-all.XXXXXXXX")"
cleanup() { rm -rf "$log_dir"; }
trap cleanup EXIT
trap 'exit 130' HUP INT TERM

succeeded=()
failed=()
pids=()
declare -A pid_to_slug=()
declare -A pid_to_log=()

terminate_children() {
  trap - HUP INT TERM
  if ((${#pids[@]} > 0)); then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
  exit 130
}
trap terminate_children HUP INT TERM

start_book() {
  local slug="$1" log pid
  log="$log_dir/$slug.console.log"
  echo "==> Starting $slug"
  "$repo_root/scripts/build-book.sh" "$slug" >"$log" 2>&1 &
  pid="$!"
  pids+=("$pid")
  pid_to_slug["$pid"]="$slug"
  pid_to_log["$pid"]="$log"
}

finish_one() {
  local completed_pid status slug log pid
  local -a remaining_pids=()
  set +e
  wait -n -p completed_pid
  status=$?
  set -e
  slug="${pid_to_slug[$completed_pid]}"
  log="${pid_to_log[$completed_pid]}"

  echo
  echo "==> Output: $slug"
  cat "$log"
  if ((status == 0)); then
    echo "==> Built $slug"
    succeeded+=("$slug")
  else
    echo "==> FAILED $slug (exit $status)"
    failed+=("$slug")
  fi
  unset 'pid_to_slug[$completed_pid]' 'pid_to_log[$completed_pid]'

  for pid in "${pids[@]}"; do
    [[ "$pid" == "$completed_pid" ]] || remaining_pids+=("$pid")
  done
  pids=("${remaining_pids[@]}")
}

next_book=0
while ((next_book < ${#books[@]} || ${#pids[@]} > 0)); do
  while ((next_book < ${#books[@]} && ${#pids[@]} < jobs)); do
    start_book "${books[next_book]}"
    ((next_book += 1))
  done
  ((${#pids[@]} == 0)) || finish_one
done

echo
echo "Build summary:"
echo "  succeeded: ${#succeeded[@]}"
echo "  failed: ${#failed[@]}"
if ((${#failed[@]} > 0)); then
  echo
  echo "Failed books:"
  for slug in "${failed[@]}"; do
    echo "  - $slug"
  done
  exit 1
fi
