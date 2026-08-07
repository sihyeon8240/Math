"""Integration tests for the books.py command-line interface."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class BooksCliTests(unittest.TestCase):
    def test_site_export_matches_books_yml(self) -> None:
        script = REPO_ROOT / "scripts" / "books.py"

        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "export",
                "--for",
                "site",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

        payload = json.loads(result.stdout)

        with (REPO_ROOT / "books.yml").open(encoding="utf-8") as file:
            raw_manifest = yaml.safe_load(file)

        defaults = raw_manifest.get("defaults", {})

        normalized_books = [
            {**defaults, **book} for book in raw_manifest["books"]
        ]
        expected_books = [book for book in normalized_books if book["site"]]
        expected_books.sort(key=lambda book: (book["order"], book["slug"]))

        expected_payload = {
            "schema_version": raw_manifest["schema_version"],
            "books": expected_books,
        }
        self.assertEqual(payload, expected_payload)

class ExportFixtureTests(unittest.TestCase):
    @staticmethod
    def book(slug: str, order: int, **overrides: object) -> dict[str, object]:
        record: dict[str, object] = {
            "slug": slug, "title": slug.title(), "status": "draft", "order": order,
        }
        record.update(overrides)
        return record

    def run_export(
        self, defaults: dict[str, bool], books: list[dict[str, object]],
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            repository_root = Path(temporary)
            for book in books:
                slug = str(book["slug"])
                book_directory = repository_root / "books" / slug
                book_directory.mkdir(parents=True)
                (book_directory / "book.tex").write_text("", encoding="utf-8")
                (book_directory / "metadata.tex").write_text(
                    rf"\newcommand{{\bookslug}}{{{slug}}}" + "\n", encoding="utf-8",
                )
            manifest_path = repository_root / "books.yml"
            manifest_path.write_text(
                yaml.safe_dump({
                    "schema_version": 1, "defaults": defaults, "books": books,
                }, sort_keys=False),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "books.py"),
                 "export", "--for", "site", "--format", "json",
                 "--manifest", str(manifest_path)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_export_normalizes_filters_and_sorts_fixture(self) -> None:
        defaults = {
            "build": True, "check": False, "release": False, "site": True,
        }
        books = [
            self.book("zulu", 20, site=False),
            self.book("bravo", 10, build=True, release=True),
            self.book("alpha", 10, short_title="A"),
        ]

        payload = self.run_export(defaults, books)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual([book["slug"] for book in payload["books"]], ["alpha", "bravo"])
        self.assertEqual(payload["books"][0], {
            "build": True, "check": False, "release": False, "site": True,
            "slug": "alpha", "title": "Alpha", "short_title": "A",
            "status": "draft", "order": 10,
        })
        self.assertEqual(payload["books"][1], {
            "build": True, "check": False, "release": True, "site": True,
            "slug": "bravo", "title": "Bravo", "status": "draft", "order": 10,
        })
        self.assertNotIn("short_title", payload["books"][1])

    def test_book_can_enable_site_when_default_is_false(self) -> None:
        defaults = {
            "build": True, "check": True, "release": False, "site": False,
        }
        books = [self.book("hidden", 10), self.book("visible", 20, site=True)]

        payload = self.run_export(defaults, books)

        self.assertEqual([book["slug"] for book in payload["books"]], ["visible"])
        self.assertTrue(payload["books"][0]["site"])


if __name__ == "__main__":
    unittest.main()
