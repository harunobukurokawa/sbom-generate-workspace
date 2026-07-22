#!/usr/bin/env bash
#
# run-xen-tools-build.sh - Build Xen's tools/libs stack and capture every
# command executed, as input for a future tools/libs SBOM collector
# (worklog/backlog.md B-3).
#
# `xen/tools/` and `xen/libs/` are NOT Kbuild: they use autoconf/automake and
# emit no `.cmd` files, so KernelSbom's dependency-graph approach (used for
# the hypervisor core, see docs/{en,ja}/02-04) does not apply here. This
# script instead captures the literal build commands with `strace`, which is
# the fallback named in backlog B-3 (the other option, `bear`, needs a
# system package install this environment may not have).
#
# NOTE: run this from your own shell, not from an AI agent's sandboxed tool
# call -- some sandboxes hard-deny writes to any directory literally named
# `config`, which `./configure` needs to create (config/Toplevel.mk etc.).
#
# Usage:
#   scripts/xen-sbom-poc/run-xen-tools-build.sh
#
# Output:
#   analysis/xen-tools-poc/xen-tools-build.strace.log(.gz)
#   external/xen/tools/**/*.o, built binaries, etc. (left in place for the
#   eventual collector to hash and inspect -- do not delete before that's
#   built)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
XEN="${REPO_ROOT}/external/xen"
OUT_DIR="${REPO_ROOT}/analysis/xen-tools-poc"
TRACE_LOG="${OUT_DIR}/xen-tools-build.strace.log"

[ -d "${XEN}/tools" ] || {
  echo "error: ${XEN}/tools not found. Run scripts/fetch-sources.sh xen first." >&2
  exit 1
}

command -v strace >/dev/null || {
  echo "error: strace not found. Install it (e.g. apt-get install strace)." >&2
  exit 1
}

mkdir -p "${OUT_DIR}"

cd "${XEN}"

if [ ! -f config/Toplevel.mk ]; then
  echo ">> ./configure"
  # --with-system-qemu skips building the bundled qemu-xen device model
  # (needs pixman/glib and is a large separate upstream project with its
  # own SBOM concerns) so this stays focused on tools/libs proper. Drop the
  # flag if you have pixman-1 >= 0.21.8 installed and want full coverage.
  ./configure --with-system-qemu
fi

echo ">> strace -f make tools -j$(nproc)  (log: ${TRACE_LOG})"
strace -f -e trace=execve -s 8192 -o "${TRACE_LOG}" \
  make tools -j"$(nproc)"

echo ">> done."
echo ">> trace log: ${TRACE_LOG} ($(du -h "${TRACE_LOG}" | cut -f1))"
echo ">> next: hand this log (and the built external/xen/tools tree) to the"
echo "   SBOM collector work (backlog B-3)."
