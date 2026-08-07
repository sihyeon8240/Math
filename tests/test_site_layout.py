"""Site HTML and stylesheet contract tests."""
from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

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
