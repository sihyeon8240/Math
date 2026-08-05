#!/usr/bin/env python3
"""Perform a read-only, best-effort health inspection of one textbook."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def main() -> int:
    slug = sys.argv[1] if len(sys.argv) == 2 else ""
    warnings: list[str] = []
    suggestions: list[str] = []

    try:
        manifest = yaml.safe_load(read(ROOT / "books.yml")) or {}
        record = next(
            (
                item
                for item in manifest.get("books", [])
                if item.get("slug") == slug
            ),
            None,
        )

        if not slug:
            warnings.append("usage: python scripts/book-doctor.py <slug>")
        if record is None:
            warnings.append(
                f"book is not registered: {slug or '(missing slug)'}"
            )

        directory = ROOT / "books" / slug
        entry = read(directory / "book.tex")
        metadata = read(directory / "metadata.tex")
        readme = read(directory / "README.md")

        print(f"Book Doctor: {slug or '(none)'}\n" + "=" * 50)

        checks = {
            "Metadata": bool(metadata),
            "README": bool(readme),
            "Book structure": bool(entry),
            "Bibliography": (directory / "references.bib").is_file(),
            "Template usage": (
                "common/templates"
                in read(directory / "frontmatter/title-and-copyright.tex")
                and "common/templates"
                in read(directory / "frontmatter/preface.tex")
            ),
        }

        chapters = re.findall(r"\\include\{(chapters/[^}]+)\}", entry)
        section_files: list[Path] = []

        for target in chapters:
            chapter = directory / (
                target if target.endswith(".tex") else target + ".tex"
            )
            text = read(chapter)

            if not text:
                warnings.append(f"missing chapter target: {target}")

            local: list[Path] = []
            for section in re.findall(
                r"\\(?:input|include)\{([^}]+)\}",
                text,
            ):
                path = (
                    directory / section
                    if section.startswith("chapters/")
                    else chapter.parent / section
                )
                if not path.suffix:
                    path = path.with_suffix(".tex")

                local.append(path)
                section_files.append(path)

                if not path.is_file():
                    warnings.append(
                        f"missing section target: {path.relative_to(directory)}"
                    )

            size = sum(len(read(path).splitlines()) for path in local)
            if size > 3000:
                suggestions.append(
                    f"large chapter: {chapter.parent.name} "
                    f"({size} source lines)"
                )

        content = "\n".join(read(path) for path in section_files)
        bib = read(directory / "references.bib")
        checks.update(
            {
                "Chapter structure": bool(chapters)
                and not any("chapter target" in item for item in warnings),
                "Section structure": bool(section_files)
                and not any("section target" in item for item in warnings),
                "Labels": len(
                    re.findall(r"\\label\{[^}]+\}", content)
                )
                > 0,
                "References": "\\printbibliography" in entry,
            }
        )
        checks["Repository policy compliance"] = bool(record) and all(
            checks.values()
        )

        for path in section_files:
            lines = len(read(path).splitlines())
            if lines > 1800:
                suggestions.append(
                    f"large section: {path.relative_to(directory)} "
                    f"({lines} source lines)"
                )

        todos = len(
            re.findall(
                r"TODO|VERIFY|SOURCECHECK|\\(?:todo|verify|sourcecheck)\{",
                content,
            )
        )
        if todos:
            suggestions.append(
                f"review {todos} unfinished-writing marker(s)"
            )
        if not re.search(r"\\begin\{example\}", content):
            suggestions.append(
                "consider whether worked examples would help this book"
            )
        if len(re.findall(r"@\w+\s*\{", bib)) < 2:
            suggestions.append(
                "bibliography is sparse; verify source coverage"
            )

        definitions = re.findall(
            r"\\begin\{definition\}(.*?)\\end\{definition\}",
            content,
            re.S,
        )
        normalized = [
            re.sub(r"\s+", " ", definition).strip()[:120]
            for definition in definitions
        ]
        if len(normalized) != len(set(normalized)):
            suggestions.append(
                "potential duplicated definition text detected"
            )

        for name, passed in checks.items():
            print(f"{name}: {'OK' if passed else 'CHECK'}")
    except Exception as error:
        warnings.append(f"inspection incomplete: {error}")

    print("\nWarnings")
    print("\n".join(f"- {item}" for item in warnings) or "- None")
    print("\nSuggestions")
    print("\n".join(f"- {item}" for item in suggestions) or "- None")

    score = max(
        0,
        100 - 12 * len(warnings) - 3 * len(suggestions),
    )
    print(
        f"\nHealth Score: {score}/100\n"
        "Advisory only; no files were modified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
