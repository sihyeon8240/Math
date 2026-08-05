"""Tests for non-fatal manifest diagnostics."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from book_manifest import load_manifest, manifest_warnings  # noqa: E402


class ManifestWarningTests(unittest.TestCase):
    def test_suspicious_combinations_are_warnings(self) -> None:
        manifest = {
            "books": [
                {
                    "slug": "archived-a",
                    "status": "archived",
                    "order": 10,
                    "release": True,
                    "site": True,
                },
                {
                    "slug": "draft-b",
                    "status": "draft",
                    "order": 10,
                    "release": True,
                    "site": False,
                },
            ]
        }

        warnings = manifest_warnings(manifest)

        self.assertEqual(len(warnings), 4)
        self.assertTrue(any("duplicate order 10" in warning for warning in warnings))
        self.assertTrue(any("archived but release=true" in warning for warning in warnings))
        self.assertTrue(any("archived but site=true" in warning for warning in warnings))
        self.assertTrue(any("draft but release=true" in warning for warning in warnings))

    def test_current_style_configuration_has_no_warnings(self) -> None:
        manifest = {
            "books": [
                {
                    "slug": "published",
                    "status": "published",
                    "order": 10,
                    "release": True,
                    "site": True,
                },
                {
                    "slug": "draft",
                    "status": "draft",
                    "order": 20,
                    "release": False,
                    "site": False,
                },
            ]
        }

        self.assertEqual(manifest_warnings(manifest), [])

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


class ManifestModuleTests(unittest.TestCase):
    def fixture(self, book: dict[str, object], defaults: dict[str, bool] | None = None):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        slug = str(book.get("slug", "sample"))
        book_dir = root / "books" / slug
        book_dir.mkdir(parents=True)
        (book_dir / "book.tex").write_text("", encoding="utf-8")
        (book_dir / "metadata.tex").write_text(
            rf"\newcommand{{\bookslug}}{{{slug}}}" + "\n", encoding="utf-8"
        )
        manifest_path = root / "books.yml"
        manifest_path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "defaults": defaults or {
                "build": True, "check": False, "release": False, "site": True,
            },
            "books": [book],
        }, sort_keys=False), encoding="utf-8")
        self.addCleanup(temporary.cleanup)
        return root, manifest_path, book_dir

    def test_load_manifest_merges_defaults_and_sorts(self) -> None:
        root, path, _ = self.fixture({
            "slug": "sample", "title": "Sample", "status": "draft", "order": 10,
            "check": True,
        })
        book = load_manifest(path, root)["books"][0]
        self.assertTrue(book["build"])
        self.assertTrue(book["check"])
        self.assertFalse(book["release"])
        self.assertTrue(book["site"])

    def test_load_manifest_rejects_unknown_field_and_non_boolean_flag(self) -> None:
        for override, diagnostic in (
            ({"unknown": 1}, "unknown field"),
            ({"build": "yes"}, "must be boolean"),
        ):
            with self.subTest(override=override):
                book = {
                    "slug": "sample", "title": "Sample", "status": "draft",
                    "order": 10, **override,
                }
                root, path, _ = self.fixture(book)
                with self.assertRaisesRegex(ValueError, diagnostic):
                    load_manifest(path, root)

    def test_load_manifest_rejects_metadata_slug_mismatch(self) -> None:
        root, path, book_dir = self.fixture({
            "slug": "sample", "title": "Sample", "status": "draft", "order": 10,
        })
        (book_dir / "metadata.tex").write_text(
            r"\newcommand{\bookslug}{different}" + "\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "metadata bookslug"):
            load_manifest(path, root)


if __name__ == "__main__":
    unittest.main()
