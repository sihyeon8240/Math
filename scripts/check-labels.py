#!/usr/bin/env python3
"""Validate labels without rewriting legacy identifiers."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

LABEL = re.compile(r"\\label\{([^}]*)\}")
MODERN = re.compile(
    r"^(la|an|nt):"
    r"(ch|sec|def|thm|lem|prop|cor|ex|exc|eq|fig|tab):"
    r"[a-z0-9]+(?:-[a-z0-9]+)*$"
)
PLACEHOLDER = re.compile(
    r"^xx:(ch|sec):[a-z0-9]+(?:-[a-z0-9]+)*$"
)
EXPECTED = {
    "linear-algebra": "la",
    "mathematical-analysis": "an",
    "elementary-number-theory": "nt",
}


def book_for(path: Path) -> str | None:
    parts = path.as_posix().split("/")
    try:
        return parts[parts.index("books") + 1]
    except (ValueError, IndexError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()

    seen: dict[str, tuple[Path, int]] = {}
    legacy = defaultdict(int)
    failed = False

    for path in args.files:
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in LABEL.finditer(line):
                label = match.group(1)
                where = f"{path}:{lineno}"

                if not label:
                    print(
                        f"{where}: error: empty label",
                        file=sys.stderr,
                    )
                    failed = True
                    continue

                if any(character.isspace() for character in label):
                    print(
                        f"{where}: error: whitespace in label '{label}'",
                        file=sys.stderr,
                    )
                    failed = True

                if label in seen:
                    old_path, old_line = seen[label]
                    print(
                        f"{where}: error: duplicate label '{label}' "
                        f"(first at {old_path}:{old_line})",
                        file=sys.stderr,
                    )
                    failed = True
                else:
                    seen[label] = (path, lineno)

                if MODERN.fullmatch(label):
                    book = book_for(path)
                    expected = EXPECTED.get(book)
                    if expected and not label.startswith(expected + ":"):
                        print(
                            f"{where}: error: prefix collision for "
                            f"'{label}', expected '{expected}:'",
                            file=sys.stderr,
                        )
                        failed = True
                elif (
                    PLACEHOLDER.fullmatch(label)
                    and "common/templates" in path.as_posix()
                ):
                    pass
                else:
                    legacy[book_for(path) or "shared"] += 1

    for book, count in sorted(legacy.items()):
        print(
            f"warning: {book}: {count} legacy labels do not yet follow "
            "<book>:<kind>:<description>",
            file=sys.stderr,
        )

    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
