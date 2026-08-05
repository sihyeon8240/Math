"""Integration tests for bounded all-book build scheduling."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class BuildAllTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts/build-all.sh", scripts / "build-all.sh")
        (scripts / "books.py").write_text(textwrap.dedent("""\
            import os, pathlib, sys
            command = sys.argv[1]
            if command == "validate":
                print("books.yml is valid")
            elif command == "list":
                purpose = sys.argv[sys.argv.index("--for") + 1]
                pathlib.Path(os.environ["PURPOSE_FILE"]).write_text(purpose)
                print(os.environ.get("TARGETS", ""))
            else:
                raise SystemExit(2)
        """), encoding="utf-8")
        (scripts / "build-book.sh").write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import fcntl, os, pathlib, sys, time
            slug = sys.argv[1]
            with pathlib.Path(os.environ["PID_FILE"]).open("a") as file:
                file.write(str(os.getpid()) + "\\n")
            state = pathlib.Path(os.environ["STATE_FILE"])
            state.touch(exist_ok=True)
            with state.open("r+") as file:
                fcntl.flock(file, fcntl.LOCK_EX)
                values = file.read().split()
                current, maximum = map(int, values or ("0", "0"))
                current += 1
                maximum = max(maximum, current)
                file.seek(0); file.truncate(); file.write(f"{current} {maximum}")
            with pathlib.Path(os.environ["RUN_FILE"]).open("a") as file:
                file.write(slug + "\\n")
            with pathlib.Path(os.environ["EVENT_FILE"]).open("a") as file:
                file.write("start " + slug + "\\n")
            print("console output for " + slug, flush=True)
            delays = dict(item.split(":") for item in os.environ.get("BUILD_DELAYS", "").split(",") if item)
            time.sleep(float(delays.get(slug, os.environ.get("BUILD_DELAY", "0.03"))))
            with state.open("r+") as file:
                fcntl.flock(file, fcntl.LOCK_EX)
                current, maximum = map(int, file.read().split())
                file.seek(0); file.truncate(); file.write(f"{current - 1} {maximum}")
            with pathlib.Path(os.environ["EVENT_FILE"]).open("a") as file:
                file.write("end " + slug + "\\n")
            if slug in os.environ.get("FAIL_BOOKS", "").split(","):
                print("failure output for " + slug, file=sys.stderr)
                raise SystemExit(7)
        """), encoding="utf-8")
        (scripts / "build-book.sh").chmod(0o755)
        self.tmpdir = self.root / "tmp"
        self.tmpdir.mkdir()
        self.env = {
            **os.environ,
            "TARGETS": "alpha\nbeta\ngamma",
            "STATE_FILE": str(self.root / "state"),
            "RUN_FILE": str(self.root / "run"),
            "PURPOSE_FILE": str(self.root / "purpose"),
            "EVENT_FILE": str(self.root / "events"),
            "PID_FILE": str(self.root / "pids"),
            "TMPDIR": str(self.tmpdir),
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_build(self, purpose: str = "build", **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.root / "scripts/build-all.sh"), purpose],
            cwd=self.root, env={**self.env, **env}, capture_output=True,
            text=True, check=False,
        )

    def test_no_targets_succeeds(self) -> None:
        result = self.run_build(TARGETS="", BOOK_BUILD_JOBS="2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No books are enabled for build", result.stdout)

    def test_invalid_jobs_is_usage_error(self) -> None:
        for value in ("", "0", "-1", "abc", "1.5"):
            with self.subTest(value=value):
                result = self.run_build(BOOK_BUILD_JOBS=value)
                self.assertEqual(result.returncode, 2)
                self.assertIn("positive integer", result.stderr)

    def test_success_is_bounded_and_outputs_are_grouped(self) -> None:
        result = self.run_build(BOOK_BUILD_JOBS="2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "state").read_text().split()[1], "2")
        self.assertIn("succeeded: 3", result.stdout)
        self.assertIn("failed: 0", result.stdout)
        for slug in ("alpha", "beta", "gamma"):
            self.assertIn("==> Output: " + slug, result.stdout)
            self.assertIn("console output for " + slug, result.stdout)

    def test_failures_are_aggregated_without_stopping_other_books(self) -> None:
        result = self.run_build(
            BOOK_BUILD_JOBS="2", FAIL_BOOKS="alpha,gamma"
        )
        self.assertEqual(result.returncode, 1)
        self.assertCountEqual(
            (self.root / "run").read_text().splitlines(),
            ["alpha", "beta", "gamma"],
        )
        self.assertIn("failed: 2", result.stdout)
        self.assertIn("  - alpha", result.stdout)
        self.assertIn("  - gamma", result.stdout)
        self.assertIn("failure output for alpha", result.stdout)
        self.assertIn("failure output for gamma", result.stdout)

    def test_finished_worker_starts_next_book_without_waiting_for_batch(self) -> None:
        result = self.run_build(
            BOOK_BUILD_JOBS="2", BUILD_DELAYS="alpha:0.02,beta:0.3,gamma:0.02"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        events = (self.root / "events").read_text().splitlines()
        self.assertLess(events.index("start gamma"), events.index("end beta"))

    def test_check_selects_check_targets_and_removes_temporary_logs(self) -> None:
        result = self.run_build("check", BOOK_BUILD_JOBS="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "purpose").read_text(), "check")
        self.assertEqual(list(self.tmpdir.iterdir()), [])

    def test_termination_stops_children_and_removes_temporary_logs(self) -> None:
        process = subprocess.Popen(
            [str(self.root / "scripts/build-all.sh"), "build"], cwd=self.root,
            env={**self.env, "BOOK_BUILD_JOBS": "2", "BUILD_DELAY": "10"},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        pid_file = self.root / "pids"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if pid_file.exists() and len(pid_file.read_text().splitlines()) >= 2:
                break
            time.sleep(0.01)
        else:
            process.kill()
            self.fail("workers did not start")

        child_pids = [int(value) for value in pid_file.read_text().splitlines()]
        process.terminate()
        process.communicate(timeout=5)
        self.assertEqual(process.returncode, 130)
        self.assertEqual(list(self.tmpdir.iterdir()), [])
        for pid in child_pids:
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)


if __name__ == "__main__":
    unittest.main()
