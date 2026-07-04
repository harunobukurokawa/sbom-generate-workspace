#!/usr/bin/env bash
#
# run-linux-sbom.sh - Reproduce the Linux kernel SPDX-SBOM generation.
#
# Builds the kernel out-of-tree and runs `make sbom`, producing the three
# SPDX 3.0.1 documents in the object tree. Verified with Linux v7.2-rc1,
# x86_64 defconfig, Python 3.10.12 (Python 3.10+ is required by the tool).
#
# Usage:
#   scripts/run-linux-sbom.sh [ARCH] [DEFCONFIG]
#     ARCH       default: host (native x86_64). Set e.g. arm64 for cross build
#                (needs a cross toolchain + CROSS_COMPILE).
#     DEFCONFIG  default: defconfig
#
# Output: external/linux/kernel_build/sbom-{source,build,output}.spdx.json
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINUX="${REPO_ROOT}/external/linux"
OBJ="kernel_build"
DEFCONFIG="${2:-defconfig}"

[ -d "${LINUX}/scripts/sbom" ] || {
  echo "error: ${LINUX}/scripts/sbom not found. Run scripts/fetch-sources.sh first." >&2
  exit 1
}

python3 - <<'PY'
import sys
assert sys.version_info >= (3, 10), f"KernelSbom needs Python 3.10+, found {sys.version.split()[0]}"
print(f"Python {sys.version.split()[0]} OK (>=3.10)")
PY

cd "${LINUX}"
ARCH_ARG=()
[ -n "${1:-}" ] && ARCH_ARG=(ARCH="$1")

echo ">> make ${DEFCONFIG} O=${OBJ}"
make "${ARCH_ARG[@]}" "${DEFCONFIG}" O="${OBJ}"

echo ">> make sbom O=${OBJ} -j$(nproc)"
make "${ARCH_ARG[@]}" sbom O="${OBJ}" -j"$(nproc)"

echo ">> generated documents:"
ls -la "${OBJ}"/sbom-*.spdx.json

echo ">> quick validation:"
python3 - "${OBJ}" <<'PY'
import json, sys, os
obj = sys.argv[1]
for name in ("source", "build", "output"):
    p = os.path.join(obj, f"sbom-{name}.spdx.json")
    if not os.path.exists(p):
        print(f"  sbom-{name}: (not produced)"); continue
    d = json.load(open(p))
    g = d.get("@graph", [])
    ctx = d.get("@context", [""])
    ver = ctx[0] if isinstance(ctx, list) else ctx
    print(f"  sbom-{name}: {len(g):,} elements, context={ver}")
PY
echo ">> done."
