#!/usr/bin/env python3
"""Command-line interface for the books.yml textbook manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from scripts.book_manifest import (
        add_book, load_manifest, manifest_warnings, metadata_title_warnings,
        metadata_version, require_book,
    )
except ModuleNotFoundError:
    # Direct execution places scripts/, rather than the repository root, on sys.path.
    from book_manifest import (  # type: ignore[no-redef]
        add_book, load_manifest, manifest_warnings, metadata_title_warnings,
        metadata_version, require_book,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and query the books.yml textbook manifest."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument(
        "--for", dest="purpose", choices=("build", "check", "release", "site")
    )
    list_parser.add_argument("--format", choices=("text", "json"), default="text")

    export_parser = subparsers.add_parser(
        "export", help="export normalized manifest records"
    )
    export_parser.add_argument(
        "--for", dest="purpose", choices=("build", "check", "release", "site")
    )
    export_parser.add_argument("--format", choices=("json",), default="json")
    export_parser.add_argument(
        "--manifest", type=Path,
        help="read an alternate books.yml (primarily for repository tooling)",
    )

    subparsers.add_parser("validate")
    add_parser = subparsers.add_parser(
        "add", help="register an existing book directory in books.yml",
        description=(
            "Register a book whose required files already exist; this command "
            "does not create a book directory."
        ),
    )
    add_parser.add_argument("slug")
    add_parser.add_argument("title")
    subparsers.add_parser("version").add_argument("slug")
    subparsers.add_parser(
        "require", help="require a slug to be registered and print it"
    ).add_argument("slug")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "add":
            add_book(args.slug, args.title)
            print(f"Added '{args.slug}' to books.yml")
            return 0
        if args.command == "version":
            print(metadata_version(args.slug))
            return 0
        if args.command == "require":
            print(require_book(args.slug)["slug"])
            return 0

        if args.command == "export" and args.manifest is not None:
            manifest = load_manifest(args.manifest, args.manifest.parent)
        else:
            manifest = load_manifest()

        if args.command == "validate":
            for warning in manifest_warnings(manifest):
                print(f"warning: {warning}", file=sys.stderr)
            for warning in metadata_title_warnings(manifest):
                print(f"warning: {warning}", file=sys.stderr)
            print("books.yml is valid")
            return 0

        books = manifest["books"]
        if args.purpose:
            books = [book for book in books if book[args.purpose]]
        if args.command == "export":
            print(json.dumps({"schema_version": manifest["schema_version"], "books": books}))
            return 0

        slugs = [book["slug"] for book in books]
        if args.format == "json":
            print(json.dumps({"book": slugs}, separators=(",", ":")))
        else:
            for slug in slugs:
                print(slug)
        return 0
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
