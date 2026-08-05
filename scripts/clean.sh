#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="$repo_root/build"

case "$build_dir" in
  "$repo_root/build") ;;
  *)
    echo "error: refusing unsafe clean paths" >&2
    exit 1
    ;;
esac

mkdir -p "$build_dir"
find "$build_dir" -mindepth 1 -delete
