"""Regression tests for workflow shell helpers and inline run blocks."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


class WorkflowShellTests(unittest.TestCase):
    @staticmethod
    def build_workflow():
        return yaml.safe_load(
            (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        )

    def run_pdf_update(self, updated: dict[str, bytes], existing: dict[str, bytes],
                       *, registered=("alpha", "beta"), site=("alpha", "beta")):
        workflow = self.build_workflow()
        publish = next(
            step["run"] for step in workflow["jobs"]["publish"]["steps"]
            if step.get("id") == "publish"
        )
        start = publish.index("mkdir -p snapshot/pdf")
        end = publish.index("printf '%s\\n' \"$GITHUB_SHA\"")
        script = "set -euo pipefail\n" + publish[start:end]

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "snapshot" / "pdf").mkdir(parents=True)
            for name, data in existing.items():
                (root / "snapshot" / "pdf" / name).write_bytes(data)
            if updated:
                (root / "updated-pdfs").mkdir()
                for name, data in updated.items():
                    (root / "updated-pdfs" / name).write_bytes(data)
            (root / "scripts").mkdir()
            (root / "scripts" / "books.py").write_text(
                """#!/usr/bin/env python3
import os
import sys
registered = os.environ["REGISTERED"].split()
site = os.environ["SITE"].split()
if sys.argv[1] == "require":
    with open(os.environ["REQUIRE_LOG"], "a", encoding="utf-8") as log:
        log.write(sys.argv[2] + "\\n")
    raise SystemExit(0 if sys.argv[2] in registered else 1)
if sys.argv[1:] == ["list", "--for", "site"]:
    print(*site, sep="\\n")
    raise SystemExit(0)
raise SystemExit(2)
""", encoding="utf-8",
            )
            require_log = root / "require.log"
            result = subprocess.run(
                ["bash", "-c", script], cwd=root, text=True,
                capture_output=True, check=False,
                env={**os.environ, "REGISTERED": " ".join(registered),
                     "SITE": " ".join(site), "REQUIRE_LOG": str(require_log)},
            )
            snapshot = {
                path.name: path.read_bytes()
                for path in (root / "snapshot" / "pdf").iterdir()
            }
            required = (
                require_log.read_text(encoding="utf-8").splitlines()
                if require_log.exists() else []
            )
            return result, snapshot, required

    def run_snapshot(self, **values: str):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            git = root / "git"
            git.write_text("""#!/usr/bin/env bash
case "$1" in
  fetch) exit "${FETCH_STATUS:-0}" ;;
  show) printf '%s' "${SOURCE_SHA:-}"; exit "${SHOW_STATUS:-0}" ;;
  cat-file) exit "${COMMIT_STATUS:-0}" ;;
  merge-base) exit "${ANCESTOR_STATUS:-0}" ;;
  *) exit 2 ;;
esac
""", encoding="utf-8")
            git.chmod(0o755)
            env = {
                **os.environ, **values, "GITHUB_OUTPUT": str(output),
                "PATH": f"{root}:{os.environ['PATH']}",
            }
            result = subprocess.run(
                [ROOT / "scripts/snapshot-base.sh"], env=env,
                text=True, capture_output=True, check=False,
            )
            return result, output.read_text(encoding="utf-8")

    def test_snapshot_base_valid_sha(self):
        sha = "a" * 40
        result, output = self.run_snapshot(SOURCE_SHA=sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, f"base={sha}\n")

    def test_snapshot_base_failures_emit_explicit_empty_base(self):
        cases = (
            {"FETCH_STATUS": "1"},
            {"SHOW_STATUS": "1"},
            {"SOURCE_SHA": "invalid"},
            {"SOURCE_SHA": "a" * 40, "COMMIT_STATUS": "1"},
            {"SOURCE_SHA": "a" * 40, "ANCESTOR_STATUS": "1"},
        )
        for values in cases:
            with self.subTest(values=values):
                result, output = self.run_snapshot(**values)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output, "base=\n")

    def run_image(self, event: str, *, tag_exists: bool, inputs_changed: bool):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            (root / "git").write_text("""#!/usr/bin/env bash
if [[ "$1" == cat-file ]]; then exit 0; fi
if [[ "$1" == diff ]]; then
  [[ "${INPUTS_CHANGED:-false}" == true ]] && exit 1
  exit 0
fi
exit 2
""", encoding="utf-8")
            (root / "docker").write_text("""#!/usr/bin/env bash
[[ "${TAG_EXISTS:-false}" == true ]]
""", encoding="utf-8")
            (root / "git").chmod(0o755)
            (root / "docker").chmod(0o755)
            env = {
                **os.environ,
                "GITHUB_OUTPUT": str(output),
                "IMAGE_NAME": "ghcr.io/example/latex",
                "RELEASE_TAG": "immutable",
                "TAG_EXISTS": str(tag_exists).lower(),
                "INPUTS_CHANGED": str(inputs_changed).lower(),
                "PATH": f"{root}:{os.environ['PATH']}",
            }
            result = subprocess.run(
                [ROOT / "scripts/check-image-tag.sh", event, "base", "head"],
                cwd=ROOT, env=env, text=True, capture_output=True, check=False,
            )
            return result, output.read_text(encoding="utf-8") if output.exists() else ""

    def test_new_image_tag_builds(self):
        result, output = self.run_image("push", tag_exists=False, inputs_changed=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "exists=false\n")

    def test_existing_tag_with_changed_inputs_fails(self):
        result, output = self.run_image("push", tag_exists=True, inputs_changed=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, "")
        self.assertIn("immutable image tag already exists", result.stderr)
        self.assertIn("bump RELEASE_TAG because image inputs changed", result.stderr)

    def test_existing_tag_with_workflow_only_change_succeeds(self):
        result, output = self.run_image("push", tag_exists=True, inputs_changed=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "exists=true\n")

    def test_dispatch_never_overwrites_existing_tag(self):
        result, output = self.run_image("workflow_dispatch", tag_exists=True, inputs_changed=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "exists=true\n")

    def test_build_image_triggers_cover_tag_and_image_inputs(self):
        text = (ROOT / ".github/workflows/build-image.yml").read_text(encoding="utf-8")
        for path in (
            ".devcontainer/Dockerfile",
            "scripts/check-environment.sh",
            ".github/workflows/build-image.yml",
        ):
            self.assertIn(path, text)
        self.assertRegex(text, r"RELEASE_TAG:\s*texlive-")
        self.assertIn("if: steps.release-tag.outputs.exists != 'true'", text)

    def test_pdf_artifacts_are_downloaded_into_one_flat_directory(self):
        workflow = self.build_workflow()
        download = workflow["jobs"]["publish"]["steps"][1]
        self.assertEqual(download["with"]["pattern"], "*-pdf")
        self.assertEqual(download["with"]["path"], "updated-pdfs")
        self.assertIs(download["with"]["merge-multiple"], True)
        upload = workflow["jobs"]["book"]["steps"][-1]
        self.assertEqual(
            upload["with"]["path"],
            "build/${{ matrix.book }}/${{ matrix.book }}.pdf",
        )

    def test_pdf_update_accepts_zero_one_and_multiple_inputs(self):
        cases = (
            ({}, {"alpha.pdf": b"old-a", "beta.pdf": b"old-b"},
             {"alpha.pdf": b"old-a", "beta.pdf": b"old-b"}, []),
            ({"alpha.pdf": b"new-a"}, {"beta.pdf": b"old-b"},
             {"alpha.pdf": b"new-a", "beta.pdf": b"old-b"}, ["alpha"]),
            ({"alpha.pdf": b"new-a", "beta.pdf": b"new-b"}, {},
             {"alpha.pdf": b"new-a", "beta.pdf": b"new-b"}, ["alpha", "beta"]),
        )
        for updated, existing, expected, required in cases:
            with self.subTest(updated=updated):
                result, snapshot, calls = self.run_pdf_update(updated, existing)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(snapshot, expected)
                self.assertEqual(calls, required)
                self.assertNotIn("*", calls)

    def test_pdf_update_prunes_files_that_are_no_longer_for_site(self):
        result, snapshot, _ = self.run_pdf_update(
            {}, {"alpha.pdf": b"a", "retired.pdf": b"old"},
            registered=("alpha", "retired"), site=("alpha",),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(snapshot, {"alpha.pdf": b"a"})

    def test_pdf_update_rejects_unknown_slug(self):
        result, _, calls = self.run_pdf_update(
            {"unknown.pdf": b"pdf"},
            {"alpha.pdf": b"old-a", "beta.pdf": b"old-b"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ["unknown"])

    def test_pdf_update_rejects_empty_artifact_before_slug_validation(self):
        result, _, calls = self.run_pdf_update(
            {"alpha.pdf": b""},
            {"alpha.pdf": b"old-a", "beta.pdf": b"old-b"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])
        self.assertIn("PDF artifact is missing or empty", result.stderr)

    def test_all_multiline_workflow_shell_blocks_parse(self):
        expression = re.compile(r"\$\{\{.*?\}\}")
        for workflow in sorted((ROOT / ".github/workflows").glob("*.yml")):
            document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
            pending = [document]
            while pending:
                value = pending.pop()
                if isinstance(value, dict):
                    pending.extend(value.values())
                elif isinstance(value, list):
                    pending.extend(value)
                elif isinstance(value, str) and "\n" in value:
                    script = expression.sub("workflow_value", value)
                    result = subprocess.run(
                        ["bash", "-n"], input=script, text=True,
                        capture_output=True, check=False,
                    )
                    self.assertEqual(
                        result.returncode, 0,
                        f"{workflow}: {result.stderr}\n{script}",
                    )


if __name__ == "__main__":
    unittest.main()
