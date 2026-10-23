#!/usr/bin/env bash
#
# export-xen-rfc-patch.sh - (Re)generate the RFC patch that adds `make sbom`
# to the Xen hypervisor build (B-4).
#
# The canonical sources of gen_xen_sbom.py / xen_parsers.py live in this
# directory; this script copies them into <xen>/xen/scripts/sbom/ so the patch
# cannot drift from the code the tests exercise. The Makefile and .gitignore
# edits are expected to already be in the Xen work tree (external/xen).
#
# The patch is built from a throw-away index and commit object: no branch,
# HEAD or index of the Xen checkout is touched. Signed-off-by is deliberately
# NOT added; the author must add it (git am + commit -s) before posting.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
XEN="${1:-${REPO_ROOT}/external/xen}"
OUT="${2:-${REPO_ROOT}/patches/xen}"
SRC="${REPO_ROOT}/scripts/xen-sbom-poc"
MSG="${REPO_ROOT}/patches/xen/0001-commit-message.txt"

mkdir -p "${XEN}/xen/scripts/sbom" "${OUT}"
cp "${SRC}/gen_xen_sbom.py" "${SRC}/xen_parsers.py" "${XEN}/xen/scripts/sbom/"

idx="$(mktemp)"; rm -f "${idx}"
export GIT_INDEX_FILE="${idx}"
trap 'rm -f "${idx}"' EXIT
git -C "${XEN}" read-tree HEAD
git -C "${XEN}" add .gitignore xen/Makefile \
    xen/scripts/sbom/gen_xen_sbom.py xen/scripts/sbom/xen_parsers.py
tree="$(git -C "${XEN}" write-tree)"
commit="$(git -C "${XEN}" commit-tree "${tree}" -p HEAD -F "${MSG}")"
rm -f "${OUT}"/0001-*.patch
git -C "${XEN}" format-patch -1 --subject-prefix="RFC PATCH" -o "${OUT}" "${commit}"
