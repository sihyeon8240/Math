"""Manifest, Pages PDF staging, and site stylesheet contract tests."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import book_manifest  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "site_pdf_staging", REPO_ROOT / "scripts" / "stage-site-pdfs.py"
)
assert spec and spec.loader
site_pdf_staging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_pdf_staging)


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
            return book_manifest.load_manifest(path, root)

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


class SitePdfStagingTests(unittest.TestCase):
    def stage(self, site_slugs, registered=None, artifacts=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        downloaded = root / "downloaded"
        destination = root / "destination"
        downloaded.mkdir()
        for slug, files in (artifacts or {}).items():
            artifact = downloaded / f"{slug}-pdf"
            artifact.mkdir()
            for name, contents in files.items():
                (artifact / name).write_bytes(contents)
        registered = set(site_slugs) if registered is None else set(registered)
        selection = (registered, set(site_slugs))
        with mock.patch.object(
            site_pdf_staging, "registered_and_site_slugs", return_value=selection
        ):
            site_pdf_staging.stage(downloaded, destination)
        return destination

    def test_only_site_pdf_is_staged_and_named_by_slug(self):
        destination = self.stage(
            {"public"}, {"public", "hidden"},
            {"public": {"book.pdf": b"pdf"}, "hidden": {"book.pdf": b"hidden"}},
        )
        self.assertEqual([path.name for path in destination.iterdir()], ["public.pdf"])
        self.assertEqual((destination / "public.pdf").read_bytes(), b"pdf")

    def test_site_disabled_artifact_contents_are_ignored(self):
        destination = self.stage(set(), {"hidden"}, {"hidden": {"unexpected.txt": b""}})
        self.assertEqual(list(destination.iterdir()), [])

    def test_duplicate_site_artifact_fails(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        downloaded = root / "downloaded"
        destination = root / "destination"
        artifact = downloaded / "public-pdf"
        artifact.mkdir(parents=True)
        (artifact / "book.pdf").write_bytes(b"pdf")
        original_iterdir = Path.iterdir

        def repeated_artifact(path):
            if path == downloaded:
                return iter((artifact, artifact))
            return original_iterdir(path)

        with mock.patch.object(
            site_pdf_staging, "registered_and_site_slugs",
            return_value=({"public"}, {"public"}),
        ), mock.patch.object(Path, "iterdir", repeated_artifact):
            with self.assertRaisesRegex(ValueError, "duplicate PDF artifact slug: public"):
                site_pdf_staging.stage(downloaded, destination)

    def test_missing_site_artifact_fails(self):
        with self.assertRaisesRegex(ValueError, "missing PDF artifact.*public"):
            self.stage({"public"}, {"public"})

    def test_unregistered_pdf_artifact_fails(self):
        with self.assertRaisesRegex(ValueError, "unknown PDF artifact slug: unknown"):
            self.stage(set(), set(), {"unknown": {"book.pdf": b"pdf"}})

    def test_site_artifact_must_contain_only_book_pdf(self):
        with self.assertRaisesRegex(ValueError, "must contain only book.pdf"):
            self.stage({"public"}, {"public"}, {"public": {"book.pdf": b"pdf", "extra": b"x"}})

    def test_empty_site_pdf_fails(self):
        with self.assertRaisesRegex(ValueError, "artifact PDF is empty"):
            self.stage({"public"}, {"public"}, {"public": {"book.pdf": b""}})

    def test_no_site_books_succeeds_with_empty_destination(self):
        destination = self.stage(set(), set())
        self.assertTrue(destination.is_dir())
        self.assertEqual(list(destination.iterdir()), [])


class SiteStylesheetTests(unittest.TestCase):
    def assert_external_stylesheet(self, document_path, asset_path, contracts):
        document = (REPO_ROOT / document_path).read_text(encoding="utf-8")
        stylesheet = REPO_ROOT / asset_path

        self.assertNotIn("<style", document.lower())
        asset_url = "/" + asset_path.relative_to("site").as_posix()
        self.assertIn(f"'{asset_url}' | relative_url", document)
        self.assertTrue(stylesheet.is_file(), f"missing stylesheet: {asset_path}")

        css = stylesheet.read_text(encoding="utf-8")
        for contract in contracts:
            with self.subTest(stylesheet=asset_path, contract=contract):
                self.assertIn(contract, css)

    def test_book_layout_uses_dedicated_external_stylesheet(self):
        self.assert_external_stylesheet(
            Path("site/_layouts/book.html"),
            Path("site/assets/site.css"),
            (
                ":focus-visible", ".book-pdf__viewer",
                ".site-nav__brand", ".site-nav__brand-mark",
                "@media (max-width: 52rem)", "prefers-reduced-motion",
            ),
        )

    def test_homepage_uses_dedicated_external_stylesheet(self):
        self.assert_external_stylesheet(
            Path("site/index.html"),
            Path("site/assets/index.css"),
            (
                ".site-header", ".brand__mark", ".formula-card",
                ".book-grid", ".book-card", ".project-panel",
                "@media (max-width: 52rem)", "@media (max-width: 40rem)",
                "prefers-reduced-motion",
            ),
        )
        homepage = (REPO_ROOT / "site/index.html").read_text(encoding="utf-8")
        self.assertNotIn("'/assets/site.css' | relative_url", homepage)

    def test_pages_use_shared_external_stylesheet(self):
        contracts = (
            ":root", "* { box-sizing: border-box; }", ".page-shell",
            ".status--stable", "prefers-reduced-motion",
        )
        for document_path in (Path("site/index.html"), Path("site/_layouts/book.html")):
            with self.subTest(document=document_path):
                self.assert_external_stylesheet(
                    document_path,
                    Path("site/assets/common.css"),
                    contracts,
                )


if __name__ == "__main__":
    unittest.main()
