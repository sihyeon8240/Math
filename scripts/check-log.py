#!/usr/bin/env python3
"""Check LaTeX logs for unresolved or fatal diagnostics."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FAILURES = {
    "undefined reference": re.compile(
        r"(?:Reference .* undefined|There were undefined references)",
        re.I,
    ),
    "undefined citation": re.compile(
        r"(?:Citation .* undefined|There were undefined citations)",
        re.I,
    ),
    "multiply defined label": re.compile(
        r"(?:Label .* multiply defined|multiply-defined labels)",
        re.I,
    ),
    "missing character": re.compile(
        r"Missing character:",
        re.I,
    ),
    "fatal LaTeX error": re.compile(
        r"(?:^! |Fatal error|Emergency stop)",
        re.I | re.M,
    ),
    "rerun required": re.compile(
        r"(?:Rerun to get cross-references right|"
        r"Package rerunfilecheck Warning:)",
        re.I,
    ),
}
OVERFULL = re.compile(r"Overfull \\[hv]box", re.I)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail on overfull boxes",
    )
    args = parser.parse_args()

    failed = False
    for path in args.logs:
        text = path.read_text(encoding="utf-8", errors="replace")

        for name, pattern in FAILURES.items():
            count = len(pattern.findall(text))
            if count:
                print(
                    f"{path}: error: {name} ({count})",
                    file=sys.stderr,
                )
                failed = True

        overfull = len(OVERFULL.findall(text))
        if overfull:
            level = "error" if args.strict else "warning"
            print(
                f"{path}: {level}: overfull box ({overfull})",
                file=sys.stderr,
            )
            failed |= args.strict

    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
