#!/usr/bin/env bash
#
# generate-xen-sbom.sh - Generate a COMPLETE Xen hypervisor SBOM using the
# unmodified upstream KernelSbom plus the Xen extensions (xen_parsers.py),
# injected at runtime by gen_xen_sbom.py.
#
# Unlike run-xen-poc.sh (the baseline), this expects ZERO unknown-command
# warnings; gen_xen_sbom.py runs with fail-on-unknown enabled.
#
# Prereqs: scripts/fetch-sources.sh, and a built Xen hypervisor:
#   make -C external/xen/xen XEN_TARGET_ARCH=x86_64 defconfig
#   make -C external/xen/xen XEN_TARGET_ARCH=x86_64 -j"$(nproc)"
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SBOM_DIR="${REPO_ROOT}/external/linux/scripts/sbom"
XEN_HV="${REPO_ROOT}/external/xen/xen"
OUT="${REPO_ROOT}/analysis/xen-full"
ROOT_ARTIFACT="${1:-prelink.o}"

[ -f "${SBOM_DIR}/sbom.py" ] || { echo "error: KernelSbom not found; run scripts/fetch-sources.sh" >&2; exit 1; }
[ -f "${XEN_HV}/${ROOT_ARTIFACT}" ] || { echo "error: ${XEN_HV}/${ROOT_ARTIFACT} not found; build the hypervisor first" >&2; exit 1; }

mkdir -p "${OUT}"
echo ">> Generating complete Xen hypervisor SBOM (root=${ROOT_ARTIFACT}), fail-on-unknown enabled"
set +e
python3 "$(dirname "${BASH_SOURCE[0]}")/gen_xen_sbom.py" \
    "${SBOM_DIR}" "${XEN_HV}" "${OUT}" "${ROOT_ARTIFACT}" \
    2> "${OUT}/xen-full.run.log"
rc=$?
set -e

echo ">> exit code: ${rc}"
echo ">> outputs:"
ls -la "${OUT}"/sbom-*.spdx.json "${OUT}/sbom.used-files.txt" 2>/dev/null || true

unknown=$(grep -cE "no matching parser|IfBlock 'then'" "${OUT}/xen-full.run.log" || true)
warns=$(grep -c "WARNING" "${OUT}/xen-full.run.log" || true)
echo ">> unknown-command occurrences: ${unknown}  (target: 0)"
echo ">> total WARNING lines: ${warns}"
if [ "${rc}" -eq 0 ] && [ "${unknown}" -eq 0 ]; then
  echo ">> RESULT: complete SBOM, zero unknown commands."
else
  echo ">> RESULT: incomplete or errored; see ${OUT}/xen-full.run.log"
fi
