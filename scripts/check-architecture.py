#!/usr/bin/env python3
"""Validate the policies documented in ARCHITECTURE.md."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from scripts.book_manifest import load_manifest
except ModuleNotFoundError:
    # Direct execution puts scripts/, rather than the repository root, on sys.path.
    from book_manifest import load_manifest


ROOT = Path(__file__).resolve().parent.parent
INCLUDE = re.compile(r"\\(?:include|input)\s*\{([^}]+)\}")
BIB_KEY = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)
CHAPTER_DIRECTORY = re.compile(
    r"^(?P<number>[0-9]{2})-[a-z0-9]+(?:-[a-z0-9]+)*$"
)
SECTION_FILENAME = re.compile(
    r"^(?P<number>[0-9]{2})-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.tex$"
)
GENERIC_SECTION_SLUGS = {"continuation", "misc"}


@dataclass
class Findings:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, value: str) -> None:
        self.errors.append(value)

    def warn(self, value: str) -> None:
        self.warnings.append(value)


@dataclass(frozen=True)
class SectionSource:
    path: Path
    number: int
    slug: str
    part: str | None = None


def parse_section_sources(
    paths: list[Path], chapter_name: str, out: Findings
) -> list[SectionSource]:
    """Parse physical files, retaining every part of a logical section."""
    raw: list[tuple[Path, int, str]] = []
    for path in sorted(paths):
        match = SECTION_FILENAME.fullmatch(path.name)
        if match is None:
            out.error(
                f"chapter {chapter_name}: section filename {path.name} must "
                "match NN-lowercase-hyphenated-name.tex"
            )
            continue
        number = int(match.group("number"))
        slug = match.group("slug")
        if slug in GENERIC_SECTION_SLUGS or re.fullmatch(
            r"(?:section-)?part-[0-9]+", slug
        ):
            out.error(
                f"chapter {chapter_name}: section filename {path.name} uses "
                "a context-dependent name; use the logical section slug"
            )
        raw.append((path, number, slug))

    # Interpret a final one-letter component using the complete chapter set.
    candidate_bases: dict[tuple[int, str], int] = {}
    for _, number, slug in raw:
        base, separator, tail = slug.rpartition("-")
        if separator and len(tail) == 1:
            key = (number, base)
            candidate_bases[key] = candidate_bases.get(key, 0) + 1
    raw_slugs = {(number, slug) for _, number, slug in raw}
    split_bases = {
        key for key, count in candidate_bases.items()
        if count > 1 or key in raw_slugs
    }
    # A lone -a has an unambiguous correction under the split convention;
    # other lone one-letter endings remain valid slug text.
    split_bases.update(
        (number, slug.rsplit("-", 1)[0])
        for _, number, slug in raw
        if slug.endswith("-a")
    )
    parsed: list[SectionSource] = []
    for path, number, slug in raw:
        base, separator, tail = slug.rpartition("-")
        if separator and (number, base) in split_bases and len(tail) == 1:
            parsed.append(SectionSource(path, number, base, tail))
        else:
            parsed.append(SectionSource(path, number, slug))
    return parsed


def check_section_sources(
    chapter_name: str, sources: list[SectionSource], out: Findings
) -> dict[Path, SectionSource]:
    by_number: dict[int, list[SectionSource]] = {}
    for source in sources:
        by_number.setdefault(source.number, []).append(source)

    for number, numbered in sorted(by_number.items()):
        slugs = {source.slug for source in numbered}
        if len(slugs) != 1:
            names = ", ".join(source.path.name for source in numbered)
            out.error(
                f"chapter {chapter_name}: logical section {number:02d} uses "
                f"multiple slugs: {names}"
            )
            continue
        slug = next(iter(slugs))
        plain = [source for source in numbered if source.part is None]
        parts = [source for source in numbered if source.part is not None]
        label = f"{number:02d}-{slug}"
        if plain and parts:
            out.error(
                f"chapter {chapter_name}: logical section {label} mixes an "
                "unsuffixed file with split parts"
            )
        elif parts:
            part_names = sorted(source.part for source in parts)
            if len(set(part_names)) != len(part_names):
                duplicates = sorted(
                    part for part in set(part_names) if part_names.count(part) > 1
                )
                out.error(
                    f"chapter {chapter_name}: split section {label} has "
                    f"duplicate part suffixes: {', '.join(duplicates)}"
                )
            elif len(parts) < 2:
                out.error(
                    f"chapter {chapter_name}: split section {label} must "
                    f"contain at least two parts; rename {parts[0].path.name} "
                    f"to {label}.tex"
                )
            elif part_names[0] != "a":
                out.error(
                    f"chapter {chapter_name}: split section {label} must "
                    f"start at part a; found parts {', '.join(part_names)}"
                )
            else:
                expected = [chr(ord("a") + i) for i in range(len(parts))]
                if part_names != expected:
                    missing = next(part for part in expected if part not in part_names)
                    out.error(
                        f"chapter {chapter_name}: split section {label} has "
                        f"a gap; expected part {missing} before part {part_names[-1]}"
                    )

    actual = sorted(by_number)
    expected = list(range(1, len(actual) + 1))
    if actual != expected:
        actual_text = ", ".join(f"{number:02d}" for number in actual)
        expected_text = ", ".join(f"{number:02d}" for number in expected)
        out.error(
            f"chapter {chapter_name}: logical section numbers are "
            f"{actual_text or '(none)'}; expected {expected_text or '(none)'}"
        )
    return {source.path.resolve(): source for source in sources}


def check_section_include_order(
    chapter: Path,
    ordered_paths: list[Path],
    source_by_path: dict[Path, SectionSource],
    out: Findings,
) -> None:
    ordered = [source_by_path[path.resolve()] for path in ordered_paths
               if path.resolve() in source_by_path]
    keys = [(source.number, source.part or "") for source in ordered]
    if keys != sorted(keys):
        out.error(
            f"chapter {chapter.parent.name}: section inputs in {chapter.name} "
            "must follow logical section number and part suffix order"
        )
    positions: dict[tuple[int, str], list[int]] = {}
    for position, source in enumerate(ordered):
        positions.setdefault((source.number, source.slug), []).append(position)
    for (number, slug), found in positions.items():
        if len(found) > 1 and found != list(range(found[0], found[-1] + 1)):
            out.error(
                f"chapter {chapter.parent.name}: parts of "
                f"{number:02d}-{slug} must be adjacent in index.tex"
            )


def tex_path(base: Path, target: str) -> Path:
    path = base / target
    return path if path.suffix else path.with_suffix(".tex")


def includes(text: str, source: Path, out: Findings) -> list[str]:
    found = INCLUDE.findall(text)
    seen: set[str] = set()
    for target in found:
        if target in seen:
            out.error(f"{source}: duplicate include/input target: {target}")
        seen.add(target)
    return found


def one_macro(
    text: str, name: str, source: Path, out: Findings
) -> str | None:
    values = re.findall(
        rf"\\newcommand\{{\\{name}\}}\{{([^}}]*)\}}", text
    )
    if len(values) != 1:
        out.error(f"{source}: expected exactly one \\{name} declaration")
        return None
    return values[0]


def readme_checks(
    book: dict, path: Path, count: int, out: Findings
) -> None:
    text = path.read_text(encoding="utf-8")
    heading = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    if not heading or heading.group(1) != book["title"]:
        out.warn(f"{path}: title differs from books.yml")
    if f"make book BOOK={book['slug']}" not in text:
        out.warn(f"{path}: build command does not use the registered slug")
    listed = len(re.findall(r"^\s*\d+\.\s+", text, re.MULTILINE))
    if listed != count:
        out.warn(
            f"{path}: lists {listed} chapters; book.tex includes {count}"
        )


def bibliography_checks(book_dir: Path, text: str, out: Findings) -> None:
    required = book_dir / "references.bib"
    if not required.is_file():
        out.error(f"{required}: required bibliography is missing")
        return

    resources = re.findall(r"\\addbibresource\s*\{([^}]+)\}", text)
    for path in sorted(book_dir.rglob("*.bib")):
        if path.relative_to(book_dir).as_posix() not in resources:
            out.warn(f"{path}: unused bibliography file")

    keys: dict[str, Path] = {}
    for resource in resources:
        path = book_dir / resource
        if not path.is_file():
            out.error(f"{path}: configured bibliography does not exist")
            continue
        for key in BIB_KEY.findall(path.read_text(encoding="utf-8")):
            if key in keys:
                out.error(f"{path}: duplicate bibliography key {key!r}")
            keys[key] = path
    if r"\nocite{*}" not in text:
        out.warn(f"{book_dir / 'book.tex'}: \\nocite{{*}} is absent")


def wrapper_checks(book_dir: Path, out: Findings) -> None:
    expected = {
        "title-and-copyright.tex":
            "../../common/templates/title-and-copyright",
        "preface.tex": "../../common/templates/preface",
    }
    for filename, target in expected.items():
        path = book_dir / "frontmatter" / filename
        if not path.is_file():
            out.error(f"{path}: frontmatter wrapper is missing")
            continue
        text = path.read_text(encoding="utf-8")
        content = [
            line
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("%")
        ]
        if target not in INCLUDE.findall(text):
            out.warn(f"{path}: shared template is not included")
        if len(content) > 5 or len(text) > 600:
            out.warn(
                f"{path}: wrapper is no longer thin; possible template drift"
            )


def check_chapter_index(
    chapter: Path, book_dir: Path, out: Findings
) -> None:
    text = chapter.read_text(encoding="utf-8")
    if len(re.findall(r"\\chapter\*?\s*\{", text)) != 1:
        out.error(f"{chapter}: expected one chapter declaration")

    referenced: set[Path] = set()
    ordered_paths: list[Path] = []
    for section in includes(text, chapter, out):
        base = book_dir if section.startswith("chapters/") else chapter.parent
        path = tex_path(base, section)
        ordered_paths.append(path)
        referenced.add(path)
        if not path.is_file():
            out.error(f"{chapter}: target does not exist: {section}")

    section_files = {
        path
        for path in chapter.parent.glob("*.tex")
        if path.name != "index.tex"
    }
    sources = parse_section_sources(
        list(section_files), chapter.parent.name, out
    )
    source_by_path = check_section_sources(chapter.parent.name, sources, out)
    check_section_include_order(chapter, ordered_paths, source_by_path, out)
    for orphan in sorted(section_files - referenced):
        out.error(f"{orphan}: orphan section file")


def chapter_number(directory: Path, out: Findings) -> int | None:
    match = CHAPTER_DIRECTORY.fullmatch(directory.name)
    if match is None:
        out.error(
            f"{directory}: chapter directory name must match "
            "NN-lowercase-hyphenated-name"
        )
        return None
    return int(match.group("number"))


def check_chapter_numbering(
    chapter_root: Path,
    numbered_directories: list[tuple[int, Path]],
    out: Findings,
) -> None:
    by_number: dict[int, list[Path]] = {}
    for number, directory in numbered_directories:
        by_number.setdefault(number, []).append(directory)

    for number, directories in sorted(by_number.items()):
        if len(directories) > 1:
            out.error(
                f"{chapter_root}: duplicate chapter number {number:02d}"
            )

    actual = sorted(by_number)
    expected = list(range(1, len(actual) + 1))
    if actual != expected:
        actual_text = ", ".join(f"{number:02d}" for number in actual)
        expected_text = ", ".join(f"{number:02d}" for number in expected)
        out.error(
            f"{chapter_root}: chapter numbers are {actual_text or '(none)'}; "
            f"expected {expected_text or '(none)'}"
        )


def check_chapter_include_order(
    entry: Path, chapter_targets: list[str], out: Findings
) -> None:
    numbers: list[int] = []
    for target in chapter_targets:
        match = CHAPTER_DIRECTORY.fullmatch(Path(target).parent.name)
        if match is not None:
            numbers.append(int(match.group("number")))

    expected = sorted(numbers)
    if numbers != expected:
        actual_text = ", ".join(f"{number:02d}" for number in numbers)
        expected_text = ", ".join(f"{number:02d}" for number in expected)
        out.error(
            f"{entry}: chapter include order is {actual_text}; "
            f"expected {expected_text}"
        )


def check_book(book: dict, root: Path, out: Findings) -> None:
    book_dir = root / "books" / book["slug"]
    required = [
        book_dir / name for name in ("book.tex", "metadata.tex", "README.md")
    ]
    for path in required:
        if not path.is_file():
            out.error(f"{path}: required file is missing")
    if any(not path.is_file() for path in required):
        return

    metadata_path = book_dir / "metadata.tex"
    metadata = metadata_path.read_text(encoding="utf-8")
    slug = one_macro(metadata, "bookslug", metadata_path, out)
    version = one_macro(metadata, "bookversion", metadata_path, out)
    course = one_macro(metadata, "bookcoursecode", metadata_path, out)
    if slug is not None and slug != book["slug"]:
        out.error(f"{metadata_path}: slug differs from books.yml")
    if version is not None and not re.fullmatch(
        r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version
    ):
        out.error(f"{metadata_path}: invalid version")
    if course is not None and not course.strip():
        out.error(f"{metadata_path}: course code is empty")

    entry = book_dir / "book.tex"
    entry_text = entry.read_text(encoding="utf-8")
    entry_targets = includes(entry_text, entry, out)
    for target in entry_targets:
        if not tex_path(book_dir, target).is_file():
            out.error(f"{entry}: target does not exist: {target}")

    chapter_targets = [
        target
        for target in entry_targets
        if target.startswith("chapters/")
    ]
    referenced_dirs: set[Path] = set()
    for target in chapter_targets:
        chapter = tex_path(book_dir, target)
        referenced_dirs.add(chapter.parent)
        if chapter.name != "index.tex":
            out.error(f"{entry}: chapter target is not index.tex: {target}")
        if chapter.is_file():
            check_chapter_index(chapter, book_dir, out)

    chapter_root = book_dir / "chapters"
    directories = (
        sorted(path for path in chapter_root.iterdir() if path.is_dir())
        if chapter_root.is_dir()
        else []
    )
    numbered_directories: list[tuple[int, Path]] = []
    for directory in directories:
        if not (directory / "index.tex").is_file():
            out.error(f"{directory}: index.tex is missing")
        if directory not in referenced_dirs:
            out.error(f"{directory}: orphan chapter directory")
        number = chapter_number(directory, out)
        if number is not None:
            numbered_directories.append((number, directory))

    check_chapter_numbering(chapter_root, numbered_directories, out)
    check_chapter_include_order(entry, chapter_targets, out)
    readme_checks(book, book_dir / "README.md", len(chapter_targets), out)
    bibliography_checks(book_dir, entry_text, out)
    wrapper_checks(book_dir, out)


def validate_repository(root: Path = ROOT) -> Findings:
    out = Findings()
    if not (root / "ARCHITECTURE.md").is_file():
        out.error("ARCHITECTURE.md is missing")

    try:
        manifest = load_manifest(
            path=root / "books.yml", repository_root=root
        )
    except (OSError, UnicodeError, ValueError) as error:
        out.error(f"books.yml cannot be read: {error}")
        return out

    books = manifest["books"]
    registered = {book["slug"] for book in books}
    books_root = root / "books"
    actual = (
        {path.name for path in books_root.iterdir() if path.is_dir()}
        if books_root.is_dir()
        else set()
    )
    for slug in sorted(actual - registered):
        out.error(f"books/{slug}: orphan book directory")
    for slug in sorted(registered - actual):
        out.error(f"books/{slug}: registered directory is missing")

    for book in books:
        check_book(book, root, out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=ROOT, help=argparse.SUPPRESS
    )
    out = validate_repository(parser.parse_args().root.resolve())
    for value in out.warnings:
        print(f"warning: {value}", file=sys.stderr)
    for value in out.errors:
        print(f"error: {value}", file=sys.stderr)
    if out.errors:
        print(
            f"Architecture checks failed: {len(out.errors)} error(s).",
            file=sys.stderr,
        )
        return 1
    print("Repository architecture checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
