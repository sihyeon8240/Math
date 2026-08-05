# Textbook writing guide

This guide describes the repository's supported authoring interface. It is a
review checklist, not a requirement to print the same headings in every section.

## Creating and assembling a book

Create and register a book from the repository root with:

```sh
scripts/new-book.sh <slug> "<title>"
```

The script copies `common/templates/`, creates the first chapter and section,
and registers the book in `books.yml`. The lower-level `books.py add` command
only registers an existing directory.

Each `books/<slug>/book.tex` is the LaTeX entry point and owns document-wide
setup and the ordered `\include` list. Each chapter directory has an `index.tex`
that declares the chapter and inputs or includes its section files in reading
order.

Name a single-file logical section `NN-section-name.tex`. If it must be split,
keep the same logical number and slug in every source and add consecutive
suffixes beginning with `-a`, for example `02-main-result-a.tex` and
`02-main-result-b.tex`. Put split parts next to each other in suffix order in
`index.tex`; do not use context-dependent names such as `section-part-2`. See
the canonical naming policy in [ARCHITECTURE.md](../ARCHITECTURE.md#naming-conventions).

Write those assembly edges literally as `\include{chapters/01-name/index}` or `\input{01-section}` (a `.tex` suffix is also allowed). Do not generate paths with macros, loops, conditionals, `\csname`, filesystem discovery, or generated lists, and delete obsolete includes rather than commenting them out. The static assembly contract and its rationale are authoritative in [ARCHITECTURE.md](../ARCHITECTURE.md#static-assembly-syntax-contract); the architecture checker depends on it to find ordering errors and orphan files.

A section file declares one section and contains its body. Use standard
`\chapter{Chapter Title}` and `\section{Section Title}` declarations. Do not use
chapter or section as environments. Existing legacy wrappers are migrated only
after output regression checks. Book sources load only `\usepackage{textbook}`.

Files such as `context.tex` containing AI question context are authoring aids,
not PDF inputs. Do not add them to the build graph.

## Metadata

`metadata.tex` remains readable LaTeX metadata. Release automation
requires exactly one `\newcommand{\bookversion}{MAJOR.MINOR.PATCH}` declaration.
A supported SemVer-style prerelease suffix may follow the patch number. Keep
`\bookslug` equal to the registered `books.yml` slug. The manifest controls
automation participation; metadata controls LaTeX/PDF presentation and the
versioned filename. Similarly named title fields remain separately owned; manifest validation compares safely normalizable titles only as advisory warnings.

## Labels

New labels use `<course-prefix>:<type>:<descriptive-name>`. Existing prefixes are
`nt`, `la`, and `an`; common types include `ch`, `sec`, `def`, `thm`, `lem`,
`prop`, `cor`, `ex`, `exc`, `prob`, `eq`, `fig`, and `tab`. Preserve legacy
labels. Only replace a duplicate or broken label and update every reference.

## Theorem environments

The public environments are `theorem`, `lemma`, `proposition`, `corollary`,
`definition`, `example`, `exercise`, `problem`, `solution`, `remark`, and
`proof`. Within each section, theorem through exercise share one numbered
sequence. Problem uses a separate section-scoped sequence. Solution and remark
are unnumbered; proof is the standard `amsthm` environment.

## Shared mathematics commands

Operators are `\Hom \End \Aut \Spec`, `\Ker \im \rank \Span \diag \tr \sgn
\Null`, and `\Real \Imag`. Number systems and aliases are `\R`, `\C`, `\Q`,
`\Z`, `\N`, `\veps`, and `\vnot`; `\vnot` is the empty-set symbol, not negation.

Paired delimiters are `\abs`, `\norm`, `\set`, `\paren`, `\bracket`, `\floor`,
`\ceil`, `\setbuilder`, and `\inner`. Unstarred forms preserve normal size, as
in `\abs{x}`. Starred forms size to contents, as in `\norm*{\frac{x}{y}}` or
`\setbuilder*{x \in \R}{x > 0}`. An explicit size such as `\paren[\big]{...}`
is also available. These names are repository-wide source API.

## Draft annotations

Use `\todo{...}`, `\verify{...}`, and `\sourcecheck{...}` for unfinished prose,
mathematical checks, and provenance checks. They remain visible in PDFs.
Repository checks also report bare uppercase `TODO`, `VERIFY`, and `SOURCECHECK`
markers, including comments, as warnings rather than failures.

## Graphics

Use `\includegraphics` for required body figures, so absence fails the build.
Use `\includeconditionalgraphics` only for genuinely optional/local-only assets;
it emits nothing when absent. The institutional title-page logo is the intended
example. Do not hide a required illustration behind conditional inclusion.

## Bibliographies and source notes

Each book uses BibLaTeX with the Biber backend. Its `references.bib` file is the
authoritative bibliography source; `sorting=none` preserves source order, and
`\nocite{*}` includes the complete source list even when the body has no citations.
Use prose or a footnote when no source-note environment is defined.
