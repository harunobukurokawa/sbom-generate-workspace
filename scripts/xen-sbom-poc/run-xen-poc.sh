#!/usr/bin/env bash
#
# run-xen-poc.sh - Proof of concept: run the *unmodified* Linux KernelSbom tool
# against a built Xen hypervisor (xen/) to demonstrate that the .cmd-graph
# approach is reusable for Xen.
#
# Prereqs:
#   - scripts/fetch-sources.sh  (clones external/linux and external/xen)
#   - Xen hypervisor built:  make -C external/xen/xen XEN_TARGET_ARCH=x86_64 -j"$(nproc)"
#
# Root artifact: prelink.o. The final `xen-syms` is linked by a special two-pass
# symbol-table recipe that does NOT emit a .cmd file, so it cannot be used as a
# root. prelink.o aggregates every built_in.o (common/drivers/lib/xsm/arch) plus
# the arch libs and DOES have a .prelink.o.cmd, so it is the natural PoC root and
# covers the hypervisor core end-to-end.
#
# Because the KernelSbom command parser registry does not yet know Xen-specific
# build commands, we pass --do-not-fail-on-unknown-build-command and
# --write-output-on-error so the run completes and reports completeness.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SBOM_DIR="${REPO_ROOT}/external/linux/scripts/sbom"
XEN_HV="${REPO_ROOT}/external/xen/xen"
OUT="${REPO_ROOT}/analysis/xen-poc"
ROOT_ARTIFACT="${1:-prelink.o}"

[ -f "${SBOM_DIR}/sbom.py" ] || { echo "error: KernelSbom not found; run scripts/fetch-sources.sh" >&2; exit 1; }
[ -f "${XEN_HV}/${ROOT_ARTIFACT}" ] || { echo "error: ${XEN_HV}/${ROOT_ARTIFACT} not found; build the hypervisor first" >&2; exit 1; }

mkdir -p "${OUT}"
cd "${XEN_HV}"

echo ">> Running KernelSbom (unmodified) against Xen hypervisor, root=${ROOT_ARTIFACT}"
set +e
SRCARCH=x86 PYTHONPATH="${SBOM_DIR}" python3 "${SBOM_DIR}/sbom.py" \
    --src-tree "${XEN_HV}" \
    --obj-tree "${XEN_HV}" \
    --roots "${ROOT_ARTIFACT}" \
    --generate-spdx \
    --generate-used-files \
    --prettify-json \
    --do-not-fail-on-unknown-build-command \
    --write-output-on-error \
    --output-directory "${OUT}" \
    --spdxId-prefix "urn:xenproject.org:" \
    --build-type "urn:xenproject.org:Kbuild" \
    --package-license "GPL-2.0-only" \
    --package-version "4.23-unstable" \
    2> "${OUT}/xen-poc.run.log"
rc=$?
set -e

echo ">> exit code: ${rc}"
echo ">> outputs:"
ls -la "${OUT}"/sbom-*.spdx.json "${OUT}/sbom.used-files.txt" 2>/dev/null || true
echo ">> warning/error summary (tail of run log):"
grep -iE "warning|error|unknown" "${OUT}/xen-poc.run.log" | sort | uniq -c | sort -rn | head -20 || true
