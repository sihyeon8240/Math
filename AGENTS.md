# Repository instructions for Codex

## Repository purpose

This repository contains LaTeX source for several mathematics textbooks. Each
textbook lives under `books/<slug>/` and uses `book.tex` as its entry point.
Shared LaTeX definitions live under `common/styles/`, with `textbook.sty` as the
shared entry point. `books.yml` is the source of truth for the textbook list and
its build, check, release, and site flags.

## Git workflow

- Use `main` only as the base branch for a task.
- Make changes on the isolated task branch; never commit or push directly to `main`.
- Never merge a pull request or change branch protection, Actions permissions, or secrets.
- Do not push unless the Codex interface explicitly requires it to create or update a task pull request.

## Generated and local-only files

- Do not commit generated PDFs or files under `build/`.
- Do not add ignored LaTeX auxiliary files to Git.
- Do not create placeholders for intentionally absent local-only assets.
- Preserve existing fallback logic for missing local-only files unless explicitly asked to change it.

## Editing scope

- Make the smallest change that satisfies the task.
- Preserve document structure, naming conventions, macros, and mathematical notation.
- Do not edit textbook body content unless the task explicitly requires it.
- Do not modify workflows, the devcontainer, or shared styles unless the task explicitly requires it.
- Name single-file logical sections `NN-section-name.tex`. For split logical
  sections, keep the same number and slug and use consecutive `-a`, `-b`, ...
  suffixes; keep those inputs adjacent in `index.tex`. See `ARCHITECTURE.md`.
- If a shared style changes, consider and validate its effect on every textbook.

## LaTeX validation

The standard compiler is LuaLaTeX through `latexmk`; `latexmkrc` and the scripts
under `scripts/` define the supported command line. Build output belongs under
`build/<slug>/`.

For a single textbook, run:

```bash
make book BOOK=<slug>
python3 scripts/check-log.py build/<slug>/book.log
```

For repository-wide validation, run:

```bash
make check
```

A build is successful only when `latexmk` and the log checker exit successfully.
Warnings that predate the task may be reported, but do not make unrelated
changes solely to silence them.

## Validation cleanup

- Leave generated files only in the ignored `build/` directory.
- Before finishing, run `git status --short` when Git metadata is available.
- Never stage or commit build artifacts.

## Pull request expectations

Prepare a concise summary containing:

1. What changed.
2. Which textbooks or shared files were affected.
3. Which validation commands ran and whether they passed.
4. Any intentionally unresolved warnings or unavailable local-only files.

The repository owner performs final review and merge. GitHub Actions validate
pull requests and `main`; tag workflows create releases only after their own
validation gates pass.
