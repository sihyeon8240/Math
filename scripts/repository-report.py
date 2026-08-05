#!/usr/bin/env python3
"""Print a best-effort, informational repository overview."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENVIRONMENTS = {
    "theorems": ("theorem", "lemma", "proposition", "corollary"),
    "definitions": ("definition",),
    "examples": ("example",),
    "exercises": ("exercise", "exercises"),
}
REPORT_FIELDS = (
    ("Version", "version"),
    ("Status", "status"),
    ("Course", "course"),
    ("Chapter count", "chapters"),
    ("Section count", "sections"),
    ("Appendix count", "appendices"),
    ("Bibliography entries", "bibliography"),
    ("Estimated theorem count", "theorems"),
    ("Estimated definition count", "definitions"),
    ("Estimated example count", "examples"),
    ("Estimated exercise count", "exercises"),
    ("Estimated source line count", "lines"),
)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def macro(text: str, name: str) -> str:
    match = re.search(
        rf"\\newcommand\{{\\{name}\}}\{{([^}}]*)\}}",
        text,
    )
    return match.group(1) if match else "unknown"


def count_env(text: str, names: tuple[str, ...]) -> int:
    return sum(text.count(rf"\begin{{{name}}}") for name in names)


def inspect(book: dict) -> dict:
    directory = ROOT / "books" / book["slug"]
    entry = read(directory / "book.tex")
    metadata = read(directory / "metadata.tex")

    chapter_paths = [
        directory / (target if target.endswith(".tex") else target + ".tex")
        for target in re.findall(
            r"\\include\{(chapters/[^}]+)\}",
            entry,
        )
    ]
    appendix_paths = re.findall(
        r"\\include\{(appendices/[^}]+)\}",
        entry,
    )
    sections: list[Path] = []
    chapter_sizes: dict[str, int] = {}

    for chapter in chapter_paths:
        chapter_text = read(chapter)
        chapter_sections = []

        for target in re.findall(
            r"\\(?:input|include)\{([^}]+)\}",
            chapter_text,
        ):
            path = (
                directory / target
                if target.startswith("chapters/")
                else chapter.parent / target
            )
            if not path.suffix:
                path = path.with_suffix(".tex")
            chapter_sections.append(path)

        sections.extend(chapter_sections)
        chapter_sizes[chapter.parent.name] = sum(
            len(read(path).splitlines())
            for path in chapter_sections
        )

    content = "\n".join(read(path) for path in sections)
    lines = len(content.splitlines())
    bibliography = len(
        re.findall(
            r"@\w+\s*\{\s*([^,\s]+)\s*,",
            read(directory / "references.bib"),
            re.I,
        )
    )
    largest_section = max(
        (
            (
                path.relative_to(directory).as_posix(),
                len(read(path).splitlines()),
            )
            for path in sections
        ),
        key=lambda item: item[1],
        default=("none", 0),
    )

    result = {
        "title": book.get("title", book["slug"]),
        "version": macro(metadata, "bookversion"),
        "status": book.get("status", "unknown"),
        "course": macro(metadata, "bookcoursecode"),
        "chapters": len(chapter_paths),
        "sections": len(sections),
        "appendices": len(appendix_paths),
        "bibliography": bibliography,
        "lines": lines,
        "largest_chapter": (
            max(chapter_sizes.items(), key=lambda item: item[1])
            if chapter_sizes
            else ("none", 0)
        ),
        "largest_section": largest_section,
    }
    result.update(
        {
            name: count_env(content, environments)
            for name, environments in ENVIRONMENTS.items()
        }
    )
    return result


def main() -> int:
    try:
        manifest = yaml.safe_load(read(ROOT / "books.yml")) or {}
        defaults = manifest.get("defaults", {})
        books = [
            {**defaults, **book}
            for book in manifest.get("books", [])
        ]
        data = [inspect(book) for book in books]

        print(
            "=" * 50
            + "\nMATHEMATICS TEXTBOOK REPOSITORY"
            + "\nRepository Report\n"
            + "=" * 50
        )
        print(
            f"\nRepository\n\n"
            f"Books: {len(books)}\n"
            f"Buildable: {sum(bool(item.get('build')) for item in books)}\n"
            f"Released: {sum(bool(item.get('release')) for item in books)}\n"
            "Published on site: "
            f"{sum(bool(item.get('site')) for item in books)}"
        )

        for item in data:
            print("\n" + "-" * 50 + f"\n\n{item['title']}")
            for label, key in REPORT_FIELDS:
                print(f"{label}: {item[key]}")

        chapters = sum(item["chapters"] for item in data)
        sections = sum(item["sections"] for item in data)
        lines = sum(item["lines"] for item in data)
        largest_chapter = max(
            (
                (item["title"], *item["largest_chapter"])
                for item in data
            ),
            key=lambda item: item[2],
            default=("none", "none", 0),
        )
        largest_section = max(
            (
                (item["title"], *item["largest_section"])
                for item in data
            ),
            key=lambda item: item[2],
            default=("none", "none", 0),
        )

        print(
            "\n"
            + "=" * 50
            + "\nRepository Totals\n"
            + "=" * 50
        )
        if chapters:
            print(
                f"Chapters: {chapters}\n"
                f"Sections: {sections}\n"
                "Appendices: "
                f"{sum(item['appendices'] for item in data)}\n"
                "Bibliography entries: "
                f"{sum(item['bibliography'] for item in data)}\n"
                f"Source lines: {lines}\n"
                "Average sections per chapter: "
                f"{sections / chapters:.2f}"
            )
        else:
            print("No chapters found")

        print(
            "Theorem density per 1,000 lines: "
            f"{sum(item['theorems'] for item in data) / max(lines, 1) * 1000:.2f}\n"
            "Definition density per 1,000 lines: "
            f"{sum(item['definitions'] for item in data) / max(lines, 1) * 1000:.2f}\n"
            "Largest chapter: "
            f"{largest_chapter[0]} / {largest_chapter[1]} "
            f"({largest_chapter[2]} lines)\n"
            "Largest section: "
            f"{largest_section[0]} / {largest_section[1]} "
            f"({largest_section[2]} lines)\n"
            f"Draft books: {sum(item['status'] == 'draft' for item in data)}\n"
            "Published books: "
            f"{sum(item['status'] == 'published' for item in data)}"
        )
        print(
            "\nMetrics are lightweight source estimates. "
            "This command never modifies files."
        )
    except Exception as error:
        print(f"warning: report is incomplete: {error}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
