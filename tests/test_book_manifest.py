"""Manifest normalization, validation, export, and diagnostic tests."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from book_manifest import load_manifest, manifest_warnings  # noqa: E402
import book_manifest as books_module  # noqa: E402


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


class ManifestFixture(unittest.TestCase):
    def make_repository(
        self,
        records: list[dict],
        metadata: dict[str, str] | None = None,
    ) -> tuple[Path, Path]:

        root = Path(self.directory.name)
        for record in records:
            slug = record["slug"]
            book_dir = root / "books" / slug
            book_dir.mkdir(parents=True, exist_ok=True)
            (book_dir / "book.tex").write_text("", encoding="utf-8")
            text = (metadata or {}).get(slug, rf"\newcommand{{\bookslug}}{{{slug}}}" + "\n")
            (book_dir / "metadata.tex").write_text(text, encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "defaults": {"build": True, "check": True, "release": False, "site": False},
            "books": records,
        }
        path = root / "books.yml"
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        return root, path

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.directory.cleanup()


class ManifestMetadataTests(ManifestFixture):
    def base(self, slug: str, **overrides: object) -> dict:
        record = {"slug": slug, "title": slug.title(), "status": "draft", "order": 10}
        record.update(overrides)
        return record

    def load(self, root: Path, path: Path) -> dict:
        return books_module.load_manifest(path, root)

    def test_site_filter_and_order_then_slug(self) -> None:
        records = [
            self.base("zeta", order=20, site=False),
            self.base("beta", order=10, site=True),
            self.base("alpha", order=10, site=True),
        ]
        root, path = self.make_repository(records)
        manifest = self.load(root, path)
        self.assertEqual([book["slug"] for book in manifest["books"]], ["alpha", "beta", "zeta"])

    def test_unknown_status_is_rejected(self) -> None:
        root, path = self.make_repository([self.base("alpha", status="unknown")])
        with self.assertRaisesRegex(ValueError, "invalid status"):
            self.load(root, path)

    def test_matching_bookslug_succeeds(self) -> None:
        root, path = self.make_repository([self.base("alpha")])
        self.load(root, path)

    def test_mismatching_bookslug_fails(self) -> None:
        root, path = self.make_repository([self.base("alpha")], {"alpha": r"\newcommand{\bookslug}{beta}" + "\n"})
        with self.assertRaisesRegex(ValueError, "metadata bookslug"):
            self.load(root, path)

    def test_missing_or_multiple_bookslug_fails(self) -> None:
        for text in ("", r"\newcommand{\bookslug}{alpha}" + "\n" + r"\newcommand{\bookslug}{alpha}" + "\n"):
            with self.subTest(text=text):
                root, path = self.make_repository([self.base("alpha")], {"alpha": text})
                with self.assertRaisesRegex(ValueError, "exactly one bookslug"):
                    self.load(root, path)

    def test_tex_formatted_title_is_advisory_not_fatal(self) -> None:
        record = self.base("analysis", title="Analysis I & II")
        metadata = (
            r"\newcommand{\bookslug}{analysis}"
            "\n"
            r"\title{Analysis \Romannum{1} \& \Romannum{2}}"
            "\n"
            r"\hypersetup{pdftitle={Analysis \Romannum{1} \& \Romannum{2}}}"
            "\n"
        )

        root, path = self.make_repository([record], {"analysis": metadata})
        with mock.patch.object(books_module, "REPO_ROOT", root):
            manifest = books_module.load_manifest(path)
            self.assertEqual(books_module.metadata_title_warnings(manifest), [])


class SiteManifestValidationTests(unittest.TestCase):
    def load(self, *, defaults_build: bool = True, build=None, site=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            book_dir = root / "books" / "alpha"
            book_dir.mkdir(parents=True)
            (book_dir / "book.tex").write_text("", encoding="utf-8")
            (book_dir / "metadata.tex").write_text(
                r"\newcommand{\bookslug}{alpha}" + "\n", encoding="utf-8"
            )
            record = {
                "slug": "alpha", "title": "Alpha", "status": "draft",
                "order": 10, "site": site,
            }
            if build is not None:
                record["build"] = build
            manifest = {
                "schema_version": 1,
                "defaults": {
                    "build": defaults_build, "check": True,
                    "release": False, "site": False,
                },
                "books": [record],
            }
            path = root / "books.yml"
            path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
            return load_manifest(path, root)

    def test_site_and_build_true_succeeds(self):
        self.load(build=True, site=True)

    def test_site_and_build_false_succeeds_when_site_is_false(self):
        self.load(build=False, site=False)

    def test_site_true_and_build_false_fails(self):
        with self.assertRaisesRegex(
            ValueError, "book 'alpha' cannot have site=true when build=false"
        ):
            self.load(build=False, site=True)

    def test_default_build_false_and_site_true_fails(self):
        with self.assertRaisesRegex(ValueError, "site=true when build=false"):
            self.load(defaults_build=False, site=True)

    def test_book_can_override_default_build_for_site(self):
        self.load(defaults_build=False, build=True, site=True)

if __name__ == "__main__":
    unittest.main()
