#!/usr/bin/env python3
"""Select manifest books whose PDF build inputs changed."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

import yaml
from book_manifest import load_manifest

ROOT = Path(__file__).resolve().parent.parent
TEX_REF = re.compile(
    r"\\(?P<command>input|include|addbibresource|bibliography|usepackage|RequirePackage)"
    r"(?:\s*\[[^]]*\])?\s*\{(?P<reference>[^}]+)\}"
)
BUILD_INFRA = {
    "Makefile",
    "latexmkrc",
    "scripts/build-book.sh",
    "scripts/build-all.sh",
    "scripts/check-log.py",
    "scripts/books.py",
    "scripts/book_manifest.py",
}
SITE_FILES = {"scripts/generate-site-data.py", "scripts/stage-site-pdfs.py"}
CI_ONLY_FILES = {"scripts/snapshot-base.sh", "scripts/check-image-tag.sh"}
DOC_FILES = {"README.md", "ARCHITECTURE.md", "CONTRIBUTING.md", "CHANGELOG.md"}


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout


def manifest_at(revision: str | None) -> dict | None:
    if not revision:
        return None
    try:
        text = git_output("show", f"{revision}:books.yml")
    except subprocess.CalledProcessError:
        return None
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "books").mkdir()
        raw = yaml.safe_load(text)
        for record in raw.get("books", []):
            slug = record.get("slug")
            if isinstance(slug, str):
                directory = root / "books" / slug
                directory.mkdir()
                (directory / "book.tex").write_text("", encoding="utf-8")
                (directory / "metadata.tex").write_text(
                    f"\\newcommand{{\\bookslug}}{{{slug}}}\n", encoding="utf-8"
                )
        path = root / "books.yml"
        path.write_text(text, encoding="utf-8")
        try:
            return load_manifest(path, root)
        except ValueError:
            return None


def changed_paths(base: str | None, head: str) -> list[str] | None:
    if not base or set(base) == {"0"}:
        return None
    try:
        output = git_output("diff", "--name-only", "--diff-filter=ACDMRTUXB", base, head)
    except subprocess.CalledProcessError:
        return None
    return [line for line in output.splitlines() if line]


def _without_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def _resolve_tex(reference: str, source: Path, command: str) -> list[Path]:
    result: list[Path] = []
    try:
        relative_source = source.resolve().relative_to(ROOT / "books")
        book_root = ROOT / "books" / relative_source.parts[0]
    except (ValueError, IndexError):
        book_root = source.parent
    for name in (item.strip() for item in reference.split(",")):
        if not name:
            continue
        if command in {"usepackage", "RequirePackage"}:
            suffix = ".sty"
            search_roots = (source.parent, book_root, ROOT / "common" / "styles", ROOT)
        elif command in {"bibliography", "addbibresource"}:
            suffix = ".bib"
            search_roots = (source.parent, book_root, ROOT / "common" / "bibliography", ROOT)
        else:
            suffix = ".tex"
            search_roots = (source.parent, book_root, ROOT, ROOT / "common" / "styles")
        suffix = "" if Path(name).suffix else suffix
        relative = Path(name + suffix)
        for root in search_roots:
            path = root / relative
            if path.is_file():
                result.append(path.resolve())
    return result


def dependencies(slug: str) -> set[str]:
    pending = [(ROOT / "books" / slug / "book.tex").resolve()]
    seen: set[Path] = set()
    while pending:
        source = pending.pop()
        if source in seen or not source.is_file():
            continue
        seen.add(source)
        text = _without_comments(source.read_text(encoding="utf-8", errors="ignore"))
        for match in TEX_REF.finditer(text):
            pending.extend(_resolve_tex(match["reference"], source, match["command"]))
    book_dir = ROOT / "books" / slug
    seen.update(path.resolve() for path in book_dir.rglob("*") if path.is_file())
    return {
        path.relative_to(ROOT).as_posix()
        for path in seen if path.is_relative_to(ROOT)
    }


def plan(paths: list[str] | None, old_manifest: dict | None = None) -> dict:
    current_manifest = load_manifest()
    build_books = [book for book in current_manifest["books"] if book["build"]]
    slugs = [book["slug"] for book in build_books]
    if paths is None:
        selected = slugs
        reason = "comparison unavailable; safe full build"
    else:
        path_set = {PurePosixPath(path).as_posix() for path in paths}
        selected_set: set[str] = set()
        dependency_map = {slug: dependencies(slug) for slug in slugs}
        for slug, inputs in dependency_map.items():
            if path_set & inputs or any(
                path.startswith(f"books/{slug}/")
                and not path.endswith("/README.md")
                for path in path_set
            ):
                selected_set.add(slug)
        if path_set & BUILD_INFRA:
            selected_set.update(slugs)
        if "books.yml" in path_set:
            if old_manifest is None:
                selected_set.update(slugs)
            else:
                old = {book["slug"]: book for book in old_manifest["books"]}
                if old_manifest.get("schema_version") != current_manifest.get("schema_version"):
                    selected_set.update(slugs)
                for book in build_books:
                    previous = old.get(book["slug"])
                    if previous is None or previous.get("build") != book["build"]:
                        selected_set.add(book["slug"])
        known = (
            set().union(*dependency_map.values())
            | BUILD_INFRA
            | SITE_FILES
            | DOC_FILES
            | CI_ONLY_FILES
            | {"books.yml"}
        )
        ignored = (
            "site/",
            "docs/",
            ".github/",
            "tests/",
            "common/templates/",
            "common/bibliography/",
        )
        if any(
            path not in known
            and not path.startswith(ignored)
            and not (
                path.startswith("books/") and path.endswith("/README.md")
            )
            for path in path_set
        ):
            selected_set.update(slugs)
        selected = [slug for slug in slugs if slug in selected_set]
        reason = "changed build dependencies"
    site_changed = paths is None or any(
        path == "books.yml" or path in SITE_FILES or path.startswith("site/")
        for path in (paths or [])
    )
    return {
        "book": selected,
        "count": len(selected),
        "site_changed": site_changed,
        "reason": reason,
    }



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--format", choices=("json", "github"), default="json")
    args = parser.parse_args()
    result = plan(
        None if args.all else changed_paths(args.base, args.head),
        manifest_at(args.base),
    )

    if args.format == "github":
        print("matrix=" + json.dumps({"book": result["book"]}, separators=(",", ":")))
        print(f"count={result['count']}")
        print("site_changed=" + str(result["site_changed"]).lower())
    else:
        print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
