#!/usr/bin/env bash
#
# fetch-spdx-tools-java.sh - Download the SPDX Java Tools release used by
# validate-spdx.sh as a third, independent validator (the same "Verify"
# engine behind https://tools.spdx.org's Validate page). Requires Java 17+
# to *run* the jar (e.g. `apt-get install openjdk-17-jre-headless`); this
# script only fetches it.
#
# Pinned to v2.0.7 (2026-06-29) rather than "latest": that release predates
# the fix for a known, still-open case-sensitivity bug
# (spdx/tools-java#283) -- see worklog/decisions.md and the caveat in
# validate-spdx.sh for how to interpret a "duplicate ID" error from Verify.
# Bump deliberately, checking that issue's status first.
set -euo pipefail

VERSION="2.0.7"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${REPO_ROOT}/external/spdx-tools-java"
JAR_NAME="tools-java-${VERSION}-jar-with-dependencies.jar"
JAR_PATH="${OUT_DIR}/${JAR_NAME}"

if [ -f "${JAR_PATH}" ]; then
  echo ">> already present: ${JAR_PATH}"
  exit 0
fi

mkdir -p "${OUT_DIR}"
ZIP_URL="https://github.com/spdx/tools-java/releases/download/v${VERSION}/tools-java-${VERSION}.zip"
TMP_ZIP="$(mktemp)"
trap 'rm -f "${TMP_ZIP}"' EXIT

echo ">> downloading ${ZIP_URL}"
curl -sSL -o "${TMP_ZIP}" "${ZIP_URL}"

# The release asset is a zip of the whole Maven module (jar, sources,
# javadoc, ...); only the jar-with-dependencies is needed to run Verify.
python3 -c "
import zipfile
with zipfile.ZipFile('${TMP_ZIP}') as z:
    name = next(n for n in z.namelist() if n.endswith('${JAR_NAME}'))
    with z.open(name) as src, open('${JAR_PATH}', 'wb') as dst:
        dst.write(src.read())
"

echo ">> extracted: ${JAR_PATH}"
