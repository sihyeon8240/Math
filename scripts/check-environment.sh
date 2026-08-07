#!/usr/bin/env bash

set -Eeuo pipefail

################################################################################
# Mathematics Textbooks - Development Environment Check
################################################################################

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

cd "${ROOT_DIR}"

echo
echo "=============================================="
echo " Mathematics Textbooks Environment Check"
echo "=============================================="
echo

################################################################################
# utility
################################################################################

pass() {
    printf "  \033[32m✓\033[0m %s\n" "$1"
}

fail() {
    printf "  \033[31m✗\033[0m %s\n" "$1" >&2
    exit 1
}

check_command() {
    local cmd="$1"

    if command -v "$cmd" >/dev/null 2>&1; then
        pass "$cmd found"
    else
        fail "$cmd not found"
    fi
}

check_tex_file() {
    local file="$1"

    if kpsewhich "$file" >/dev/null 2>&1; then
        pass "$file found"
    else
        fail "$file not found by kpsewhich"
    fi
}

################################################################################
# required commands
################################################################################

echo "[Commands]"

check_command latexmk
check_command lualatex
check_command biber
check_command make
check_command "$PYTHON"
check_command kpsewhich
check_command rg
check_command gs
check_command tree
check_command git
check_command bash

if "$PYTHON" -c 'import yaml' >/dev/null 2>&1; then
    pass "PyYAML import succeeded with $PYTHON"
else
    fail "PyYAML is not importable with selected Python: $PYTHON"
fi

tex_dependencies=(
    fontspec.sty microtype.sty graphicx.sty xcolor.sty enumitem.sty
    hyperref.sty cleveref.sty amsmath.sty amssymb.sty amsthm.sty
    mathtools.sty mathrsfs.sty bm.sty romannum.sty aliascnt.sty
    biblatex.sty
)
for dependency in "${tex_dependencies[@]}"; do
    check_tex_file "$dependency"
done

skip_repository_checks="${CHECK_ENVIRONMENT_SKIP_REPOSITORY:-${CHECK_ENVIRONMENT_TOOLS_ONLY:-0}}"
if [[ "$skip_repository_checks" == 1 ]]; then
    echo
    echo "Toolchain dependencies are ready."
    exit 0
fi

echo

################################################################################
# repository structure
################################################################################

echo "[Repository]"

[[ -f Makefile ]] \
    && pass "Makefile" \
    || fail "Makefile missing"

[[ -f latexmkrc ]] \
    && pass "latexmkrc" \
    || fail "latexmkrc missing"

[[ -d books ]] \
    && pass "books/" \
    || fail "books/ missing"

[[ -d common ]] \
    && pass "common/" \
    || fail "common/ missing"

[[ -f common/styles/textbook.sty ]] \
    && pass "textbook.sty" \
    || fail "common/styles/textbook.sty missing"

echo

################################################################################
# build directory
################################################################################

mkdir -p build

pass "build/ ready"

echo

################################################################################
# versions
################################################################################

echo "[Versions]"

printf "  LuaLaTeX : %s\n" \
    "$(lualatex --version | head -n1)"

printf "  latexmk  : %s\n" \
    "$(latexmk -v | head -n1)"

printf "  Biber    : %s\n" \
    "$(biber --version | head -n1)"

printf "  Python   : %s\n" \
    "$("$PYTHON" --version)"

printf "  Make     : %s\n" \
    "$(make --version | head -n1)"

echo
echo "Environment is ready."
