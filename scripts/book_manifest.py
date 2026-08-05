#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "books.yml"
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$")
VERSION_MACRO = re.compile(r"\\newcommand\{\\bookversion\}\{([^}]*)\}")
BOOK_SLUG_MACRO = re.compile(r"\\newcommand\{\\bookslug\}\{([^}]*)\}")
TITLE_MACRO = re.compile(r"\\title\s*\{")
PDF_TITLE_FIELD = re.compile(r"pdftitle\s*=\s*\{")
ALLOWED_STATUSES = {
    "draft",
    "review",
    "published",
    "archived",
}
ROOT_FIELDS = {"schema_version", "defaults", "books"}
DEFAULT_FIELDS = {"build", "check", "release", "site"}
BOOK_FIELDS = {
    "slug", "title", "short_title", "status", "order",
    "build", "check", "release", "site",
}


def read_raw_manifest() -> dict[str, Any]:
    try:
        with MANIFEST_PATH.open(encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except FileNotFoundError as error:
        raise ValueError(f"manifest not found: {MANIFEST_PATH}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"invalid YAML in {MANIFEST_PATH}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError("manifest root must be a mapping")
    if not isinstance(data.get("books"), list):
        raise ValueError("'books' must be a list")
    return data


def save_manifest(manifest: dict[str, Any]) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=MANIFEST_PATH.parent,
            prefix=f".{MANIFEST_PATH.name}.", suffix=".tmp", delete=False,
        ) as file:
            temporary_path = Path(file.name)
            yaml.safe_dump(
                manifest, file, allow_unicode=True, sort_keys=False,
                default_flow_style=False,
            )
        load_manifest(temporary_path)
        os.replace(temporary_path, MANIFEST_PATH)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def add_book(slug: str, title: str) -> None:
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError(
            "slug must contain lowercase letters/numbers "
            "separated by single hyphens"
        )

    title = title.strip()
    if not title or "\n" in title:
        raise ValueError("title must be a non-empty single line")

    load_manifest()
    manifest = read_raw_manifest()
    books = manifest["books"]

    if any(book.get("slug") == slug for book in books):
        raise ValueError(f"book is already registered: {slug}")

    orders = [
        book["order"]
        for book in books
        if isinstance(book.get("order"), int)
    ]
    next_order = max(orders, default=0) + 10

    books.append(
        {
            "slug": slug,
            "title": title,
            "status": "draft",
            "order": next_order,
        }
    )

    books.sort(
        key=lambda book: (
            book.get("order", 0),
            book.get("slug", ""),
        )
    )

    save_manifest(manifest)


def _braced_value(text: str, match: re.Match[str]) -> str | None:
    """Return the balanced value whose opening brace ends *match*."""
    start = match.end()
    depth = 1
    for index in range(start, len(text)):
        if text[index] == "{" and (index == 0 or text[index - 1] != "\\"):
            depth += 1
        elif text[index] == "}" and (index == 0 or text[index - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return text[start:index]
    return None


def _plain_tex_title(value: str) -> str:
    roman = {"1": "I", "2": "II", "3": "III"}
    value = re.sub(
        r"\\Romannum\{([123])\}",
        lambda match: roman[match.group(1)],
        value,
    )
    value = value.replace(r"\&", "&")
    value = re.sub(r"\\[A-Za-z@]+\*?", "", value)
    value = value.replace("{", "").replace("}", "")
    return " ".join(value.split())


def metadata_title_warnings(manifest: dict[str, Any]) -> list[str]:
    """Return advisory warnings for reliably comparable title fields."""
    warnings: list[str] = []
    for book in manifest["books"]:
        path = REPO_ROOT / "books" / book["slug"] / "metadata.tex"
        text = path.read_text(encoding="utf-8")
        for label, pattern in ((r"\\title", TITLE_MACRO), ("pdftitle", PDF_TITLE_FIELD)):
            matches = list(pattern.finditer(text))
            values = [_braced_value(text, match) for match in matches]
            if len(values) != 1 or values[0] is None:
                warnings.append(f"book '{book['slug']}' has no uniquely comparable {label}")
                continue
            if _plain_tex_title(values[0]) != book["title"]:
                warnings.append(
                    f"book '{book['slug']}' manifest title differs from {label}; "
                    "verify that the difference is presentational"
                )
    return warnings


def load_manifest(
    path: Path = MANIFEST_PATH,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    if repository_root is None:
        repository_root = REPO_ROOT

    try:
        with path.open(encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except FileNotFoundError:
        raise ValueError(f"manifest not found: {path}")
    except yaml.YAMLError as error:
        raise ValueError(f"invalid YAML in {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a mapping")

    unknown_root_fields = set(data) - ROOT_FIELDS
    if unknown_root_fields:
        raise ValueError(
            "manifest has unknown field(s): "
            + ", ".join(sorted(unknown_root_fields))
        )

    if data.get("schema_version") != 1:
        raise ValueError("unsupported or missing schema_version")

    defaults = data.get("defaults", {})
    books = data.get("books")

    if not isinstance(defaults, dict):
        raise ValueError("'defaults' must be a mapping")

    unknown_default_fields = set(defaults) - DEFAULT_FIELDS
    if unknown_default_fields:
        raise ValueError(
            "defaults has unknown field(s): "
            + ", ".join(sorted(unknown_default_fields))
        )

    for flag, value in defaults.items():
        if not isinstance(value, bool):
            raise ValueError(f"defaults field '{flag}' must be boolean")

    if not isinstance(books, list):
        raise ValueError("'books' must be a list")

    normalized_books: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()

    for index, raw_book in enumerate(books, start=1):
        if not isinstance(raw_book, dict):
            raise ValueError(f"books[{index}] must be a mapping")

        unknown_book_fields = set(raw_book) - BOOK_FIELDS
        if unknown_book_fields:
            raise ValueError(
                f"books[{index}] has unknown field(s): "
                + ", ".join(sorted(unknown_book_fields))
            )

        book = {**defaults, **raw_book}

        slug = book.get("slug")
        title = book.get("title")
        status = book.get("status")
        order = book.get("order")

        if not isinstance(slug, str) or not SLUG_PATTERN.fullmatch(slug):
            raise ValueError(f"books[{index}] has an invalid slug")

        if slug in seen_slugs:
            raise ValueError(f"duplicate book slug: {slug}")
        seen_slugs.add(slug)

        if (
            not isinstance(title, str)
            or not title.strip()
            or "\n" in title
            or "\r" in title
        ):
            raise ValueError(f"book '{slug}' must have a non-empty single-line title")

        short_title = book.get("short_title")
        if short_title is not None and (
            not isinstance(short_title, str)
            or not short_title.strip()
            or "\n" in short_title
            or "\r" in short_title
        ):
            raise ValueError(
                f"book '{slug}' field 'short_title' must be a non-empty "
                "single-line string"
            )

        if status not in ALLOWED_STATUSES:
            raise ValueError(
                f"book '{slug}' has invalid status: {status!r}"
            )

        if not isinstance(order, int) or isinstance(order, bool):
            raise ValueError(f"book '{slug}' must have an integer order")

        for flag in ("build", "check", "release", "site"):
            if not isinstance(book.get(flag), bool):
                raise ValueError(
                    f"book '{slug}' field '{flag}' must be boolean"
                )

        if book["site"] and not book["build"]:
            raise ValueError(
                f"book '{slug}' cannot have site=true when build=false"
            )

        book_dir = repository_root / "books" / slug
        if not (book_dir / "book.tex").is_file():
            raise ValueError(
                f"book '{slug}' is missing books/{slug}/book.tex"
            )

        if not (book_dir / "metadata.tex").is_file():
            raise ValueError(
                f"book '{slug}' is missing books/{slug}/metadata.tex"
            )

        metadata_text = (book_dir / "metadata.tex").read_text(encoding="utf-8")
        metadata_slugs = BOOK_SLUG_MACRO.findall(metadata_text)
        if len(metadata_slugs) != 1:
            raise ValueError(
                f"book '{slug}' must declare exactly one bookslug in metadata.tex"
            )
        if metadata_slugs[0] != slug:
            raise ValueError(
                f"book '{slug}' metadata bookslug is {metadata_slugs[0]!r}"
            )

        normalized_books.append(book)

    data["books"] = sorted(
        normalized_books,
        key=lambda book: (book["order"], book["slug"]),
    )

    return data


def manifest_warnings(manifest: dict[str, Any]) -> list[str]:
    """Return suspicious, non-fatal manifest configurations."""
    warnings: list[str] = []
    orders: dict[int, list[str]] = {}
    for book in manifest["books"]:
        orders.setdefault(book["order"], []).append(book["slug"])
        if book["status"] == "archived" and book["release"]:
            warnings.append(
                f"book '{book['slug']}' is archived but release=true; "
                "archived books are normally excluded from new releases"
            )
        if book["status"] == "archived" and book["site"]:
            warnings.append(
                f"book '{book['slug']}' is archived but site=true; "
                "confirm that it should remain published on the site"
            )
        if book["status"] == "draft" and book["release"]:
            warnings.append(
                f"book '{book['slug']}' is draft but release=true; "
                "draft books are normally excluded from official releases"
            )
    for order, slugs in sorted(orders.items()):
        if len(slugs) > 1:
            warnings.append(
                f"duplicate order {order} is used by {', '.join(slugs)}; "
                "display order will fall back to slug ordering"
            )
    return warnings


def metadata_version(slug: str) -> str:
    manifest = load_manifest()
    if slug not in {book["slug"] for book in manifest["books"]}:
        raise ValueError(f"book is not registered in books.yml: {slug}")
    metadata_path = REPO_ROOT / "books" / slug / "metadata.tex"
    text = metadata_path.read_text(encoding="utf-8", errors="strict")
    versions = VERSION_MACRO.findall(text)
    if len(versions) != 1:
        raise ValueError(
            f"expected exactly one bookversion macro in {metadata_path}; "
            f"found {len(versions)}"
        )
    version = versions[0]
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"invalid bookversion {version!r} in {metadata_path}")
    return version


def require_book(slug: str) -> dict[str, Any]:
    manifest = load_manifest()
    for book in manifest["books"]:
        if book["slug"] == slug:
            return book
    raise ValueError(f"book is not registered in books.yml: {slug}")


