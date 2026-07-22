#!/usr/bin/env bash
#
# run-xen-tools-build.sh - Build Xen's tools/libs stack and capture every
# command executed (with its working directory), as input for a future
# tools/libs SBOM collector (worklog/backlog.md B-3).
#
# `xen/tools/` and `xen/libs/` are NOT Kbuild: they use autoconf/automake and
# emit no `.cmd` files, so KernelSbom's dependency-graph approach (used for
# the hypervisor core, see docs/{en,ja}/02-04) does not apply here.
#
# History: an earlier version of this script used `strace -f -e trace=execve`
# (the fallback named in backlog B-3; `bear` needs a system package this
# environment may not have). That approach turned out to be unreliable: with
# only execve traced (not chdir/clone), the working directory of each command
# could only be recovered when its argv happened to contain an absolute path
# (about 18% of real compile/link commands did, in practice). This version
# instead overrides make's SHELL to `bash -x` with a custom PS4 that prints
# $PWD before every command, which is reliable for ~100% of commands and
# needs no extra tooling.
#
# NOTE: run this from your own shell, not from an AI agent's sandboxed tool
# call -- some sandboxes hard-deny writes to any directory literally named
# `config`, which `./configure` needs to create (config/Toplevel.mk etc.).
#
# Known ./configure dependency (Ubuntu 20.04): libyajl-dev
#   sudo apt-get install -y libyajl-dev
# If configure reports other missing packages, install them and re-run this
# script; it re-runs ./configure automatically as long as config/Tools.mk
# is still missing.
#
# Usage:
#   scripts/xen-sbom-poc/run-xen-tools-build.sh
#
# Output:
#   analysis/xen-tools-poc/xen-tools-build.trace.log   (PS4-tagged command trace)
#   analysis/xen-tools-poc/xen-tools-build.stdout.log  (make's normal stdout)
#   external/xen/tools/**/*.o, built binaries, etc. (left in place for the
#   eventual collector to hash and inspect -- do not delete before that's
#   built)
#
# Note: this rebuilds with -j1 (single job), not -j$(nproc). The PS4 trace
# lines for concurrent recipes under -j>1 can interleave mid-line in the
# combined stderr stream, which would corrupt exactly the long final-link
# commands we most want to capture intact. -j1 costs wall-clock time but
# guarantees a cleanly parseable trace.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
XEN="${REPO_ROOT}/external/xen"
OUT_DIR="${REPO_ROOT}/analysis/xen-tools-poc"
TRACE_LOG="${OUT_DIR}/xen-tools-build.trace.log"
STDOUT_LOG="${OUT_DIR}/xen-tools-build.stdout.log"

[ -d "${XEN}/tools" ] || {
  echo "error: ${XEN}/tools not found. Run scripts/fetch-sources.sh xen first." >&2
  exit 1
}

mkdir -p "${OUT_DIR}"

cd "${XEN}"

if [ ! -f config/Tools.mk ]; then
  # config/Tools.mk (not config/Toplevel.mk, which config.status writes
  # early regardless of whether configure goes on to succeed) is what
  # tools/Rules.mk actually checks for. Re-running ./configure after a
  # previously failed attempt (e.g. a missing dependency) is safe/idempotent.
  echo ">> ./configure"
  # --with-system-qemu skips building the bundled qemu-xen device model
  # (needs pixman/glib and is a large separate upstream project with its
  # own SBOM concerns) so this stays focused on tools/libs proper. Drop the
  # flag if you have pixman-1 >= 0.21.8 installed and want full coverage.
  ./configure --with-system-qemu
fi

echo ">> make -C tools clean  (force a full rebuild under the new trace)"
make -C tools clean

echo ">> make tools -j1 with cwd-tagged trace (log: ${TRACE_LOG})"
# $$PWD (not $PWD): command-line variables are make-expanded once before
# being placed in the recipe shell's environment, and make's own expander
# treats a bare "$P" as a (single-letter, here undefined) make variable
# reference -- "$$" is required to survive that pass and reach bash as "$".
make tools -j1 \
  SHELL='/bin/bash' \
  .SHELLFLAGS='-xc' \
  PS4='+++XENSBOM_CWD:$$PWD+++ ' \
  > "${STDOUT_LOG}" \
  2> "${TRACE_LOG}"

echo ">> done."
echo ">> trace log:  ${TRACE_LOG} ($(du -h "${TRACE_LOG}" | cut -f1))"
echo ">> stdout log: ${STDOUT_LOG} ($(du -h "${STDOUT_LOG}" | cut -f1))"
echo ">> next: hand these logs (and the built external/xen/tools tree) to the"
echo "   SBOM collector work (backlog B-3)."
