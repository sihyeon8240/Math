#!/usr/bin/env python3
"""Generate the root README book table from the canonical manifest."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from book_manifest import load_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"
BEGIN_MARKER = "<!-- BEGIN GENERATED BOOKS -->"
END_MARKER = "<!-- END GENERATED BOOKS -->"


def _escape_table_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|")


def render_books_table(manifest: dict) -> str:
    lines = ["| Book | Slug | Build command |", "|---|---|---|"]
    for book in manifest["books"]:
        slug = book["slug"]
        lines.append(
            f"| {_escape_table_cell(book['title'])} | `{slug}` | "
            f"`make book BOOK={slug}` |"
        )
    return "\n".join(lines)


def replace_generated_books(readme: str, table: str) -> str:
    begin_count = readme.count(BEGIN_MARKER)
    end_count = readme.count(END_MARKER)
    if begin_count != 1:
        raise ValueError(
            f"README must contain exactly one {BEGIN_MARKER!r} marker; found {begin_count}"
        )
    if end_count != 1:
        raise ValueError(
            f"README must contain exactly one {END_MARKER!r} marker; found {end_count}"
        )
    begin = readme.index(BEGIN_MARKER) + len(BEGIN_MARKER)
    end = readme.index(END_MARKER)
    if begin > end:
        raise ValueError("README generated books markers are in the wrong order")
    return readme[:begin] + "\n\n" + table + "\n\n" + readme[end:]


def generate(
    *, check: bool = False, readme_path: Path = README_PATH,
    manifest: dict | None = None,
) -> int:
    current = readme_path.read_bytes().decode("utf-8")
    expected = replace_generated_books(
        current, render_books_table(load_manifest() if manifest is None else manifest)
    )
    display = readme_path.relative_to(REPO_ROOT) if readme_path.is_relative_to(REPO_ROOT) else readme_path
    if check:
        if current != expected:
            print(f"error: generated README book table is stale: {display}", file=sys.stderr)
            return 1
        print("Generated README book table is up to date.")
        return 0
    readme_path.write_bytes(expected.encode("utf-8"))
    print(f"Generated book table in {display}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail instead of updating a stale table")
    args = parser.parse_args()
    try:
        return generate(check=args.check)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
