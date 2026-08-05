#!/usr/bin/env python3
"""Validate a PDF snapshot (or legacy artifacts) and stage site-enabled books."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from book_manifest import load_manifest


def registered_and_site_slugs() -> tuple[set[str], set[str]]:
    books = load_manifest()["books"]
    return (
        {book["slug"] for book in books},
        {book["slug"] for book in books if book["site"]},
    )


def stage(downloaded: Path, destination: Path) -> None:
    registered, expected = registered_and_site_slugs()
    artifacts: dict[str, Path] = {}

    if not downloaded.is_dir():
        raise ValueError(f"PDF input directory not found: {downloaded}")

    pdf_dir = downloaded / "pdf"
    if pdf_dir.is_dir():
        for pdf in sorted(pdf_dir.iterdir()):
            if not pdf.is_file() or pdf.suffix != ".pdf":
                raise ValueError(f"unknown snapshot entry: pdf/{pdf.name}")
            slug = pdf.stem
            if slug not in registered:
                raise ValueError(f"unknown snapshot PDF slug: {slug}")
            if slug in expected:
                if pdf.stat().st_size == 0:
                    raise ValueError(f"snapshot PDF is empty: pdf/{pdf.name}")
                artifacts[slug] = pdf
    else:
        # Kept for local compatibility with previously downloaded Actions artifacts.
        for artifact_dir in sorted(downloaded.iterdir()):
            if not artifact_dir.is_dir() or not artifact_dir.name.endswith("-pdf"):
                raise ValueError(f"unknown downloaded artifact: {artifact_dir.name}")
            slug = artifact_dir.name.removesuffix("-pdf")
            if slug not in registered:
                raise ValueError(f"unknown PDF artifact slug: {slug}")
            if slug not in expected:
                continue
            if slug in artifacts:
                raise ValueError(f"duplicate PDF artifact slug: {slug}")
            files = list(artifact_dir.iterdir())
            if len(files) != 1 or files[0].name != "book.pdf" or not files[0].is_file():
                raise ValueError(f"artifact {artifact_dir.name} must contain only book.pdf")
            if files[0].stat().st_size == 0:
                raise ValueError(f"artifact PDF is empty: {artifact_dir.name}/book.pdf")
            artifacts[slug] = files[0]

    missing = sorted(expected - artifacts.keys())
    if missing:
        raise ValueError("missing PDF artifact(s): " + ", ".join(missing))

    destination.mkdir(parents=True, exist_ok=True)
    for entry in destination.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    for slug, source in sorted(artifacts.items()):
        target = destination / f"{slug}.pdf"
        shutil.copyfile(source, target)
        print(f"Staged {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("downloaded", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        stage(args.downloaded, args.destination)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
